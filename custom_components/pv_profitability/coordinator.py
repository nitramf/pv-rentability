"""DataUpdateCoordinator für PV Profitability."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_PLANTS,
    CONF_INVESTMENT_COSTS,
    CONF_ADDITIONAL_COSTS,
    CONF_PRODUCTION_SENSOR,
    CONF_FEED_IN_SENSOR,
    CONF_FEED_IN_TARIFF,
    CONF_ELECTRICITY_PRICE,
    CONF_YEARLY_BILLS,
    CONF_ENERGY_SELF_CONSUMPTION_SENSOR,
    CONF_ENERGY_FROM_GRID_SENSOR,
    CONF_ENERGY_TO_GRID_SENSOR,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)


@dataclass
class PlantResult:
    """Berechnungsergebnis einer einzelnen Anlage."""
    name: str
    investment: float

    # kWh aus einfachen Sensoren
    produced_kwh: float = 0.0
    fed_in_kwh: float = 0.0

    # kWh aus dem HA-Energie-Dashboard (Vorrang vor einfachen Sensoren)
    energy_self_consumed_kwh: float = 0.0  # direkt gemessener Eigenverbrauch
    energy_from_grid_kwh: float = 0.0      # Netzbezug
    energy_to_grid_kwh: float = 0.0        # Netzeinspeisung

    # €-Ergebnisse
    feed_in_revenue: float = 0.0
    self_consumption_savings: float = 0.0

    @property
    def effective_self_consumed_kwh(self) -> float:
        """
        Eigenverbrauch in kWh – Priorität:
        1. Direkter Eigenverbrauch-Sensor (Energie-Dashboard)
        2. Erzeugt − Netzeinspeisung (Energie-Dashboard)
        3. Erzeugt − Einspeise-Sensor (einfacher Sensor)
        """
        if self.energy_self_consumed_kwh > 0:
            return self.energy_self_consumed_kwh
        if self.energy_to_grid_kwh > 0 and self.produced_kwh > 0:
            return max(0.0, self.produced_kwh - self.energy_to_grid_kwh)
        return max(0.0, self.produced_kwh - self.fed_in_kwh)

    @property
    def effective_fed_in_kwh(self) -> float:
        """Einspeisung – Energie-Dashboard hat Vorrang."""
        if self.energy_to_grid_kwh > 0:
            return self.energy_to_grid_kwh
        return self.fed_in_kwh

    @property
    def total_revenue(self) -> float:
        return self.feed_in_revenue + self.self_consumption_savings

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "investment": round(self.investment, 2),
            "produced_kwh": round(self.produced_kwh, 2),
            "fed_in_kwh": round(self.effective_fed_in_kwh, 2),
            "self_consumed_kwh": round(self.effective_self_consumed_kwh, 2),
            "energy_from_grid_kwh": round(self.energy_from_grid_kwh, 2),
            "feed_in_revenue": round(self.feed_in_revenue, 2),
            "self_consumption_savings": round(self.self_consumption_savings, 2),
            "total_revenue": round(self.total_revenue, 2),
        }


def _bill_benefit(bill: dict) -> float:
    """
    Jahresnutzen aus einem Abrechnungs-Dict.

    Formel:
        Nutzen = Einspeisevergütung
                 + max(0, Stromkosten_ohne_PV − tatsächliche_Stromkosten)

    Die zweite Komponente entspricht der Eigenverbrauchsersparnis:
    Wieviel hätte ich mehr bezahlt, wenn die PV nicht dagewesen wäre?
    """
    if "annual_benefit" in bill and bill["annual_benefit"]:
        return float(bill["annual_benefit"])

    feed_in = float(bill.get("feed_in_revenue_total", bill.get("feed_in_revenue", 0)))
    savings = max(
        0.0,
        float(bill.get("electricity_cost_without_pv", 0))
        - float(bill.get("electricity_cost_total", bill.get("electricity_cost", 0))),
    )
    return feed_in + savings


class PVCoordinator(DataUpdateCoordinator):
    """Koordiniert alle PV-Berechnungen."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry

    # ------------------------------------------------------------------ #
    # Haupt-Update
    # ------------------------------------------------------------------ #
    async def _async_update_data(self) -> dict:
        data = self.entry.data
        plants_cfg: list[dict] = data.get(CONF_PLANTS, [])
        yearly_bills: list[dict] = data.get(CONF_YEARLY_BILLS, [])

        total_investment = 0.0
        plants_detail: list[dict] = []

        for plant in plants_cfg:
            result = self._calc_plant(plant)
            plants_detail.append(result.as_dict())
            total_investment += result.investment

        # Jahresabrechnungen haben Vorrang vor Live-Sensoren,
        # da sie die exakten Netzbetreiber-Daten enthalten.
        if yearly_bills:
            total_revenue = sum(_bill_benefit(b) for b in yearly_bills)
        else:
            total_revenue = sum(p["total_revenue"] for p in plants_detail)

        net_balance = total_revenue - total_investment
        amortization_percent = (
            min(100.0, total_revenue / total_investment * 100)
            if total_investment > 0 else 0.0
        )

        return {
            "total_investment": round(total_investment, 2),
            "total_revenue": round(total_revenue, 2),
            "net_balance": round(net_balance, 2),
            "amortization_percent": round(amortization_percent, 1),
            "amortization_year": self._estimate_amortization_year(
                yearly_bills, total_investment, plants_detail
            ),
            "plants": plants_detail,
            "yearly_bills": yearly_bills,
            "timeline": self._build_timeline(yearly_bills, total_investment, plants_detail),
        }

    # ------------------------------------------------------------------ #
    # Anlage berechnen
    # ------------------------------------------------------------------ #
    def _calc_plant(self, plant: dict) -> PlantResult:
        """
        Liest alle verfügbaren Sensoren und berechnet Einnahmen + Ersparnis.

        Eigenverbrauch-Logik:
        ┌─────────────────────────────────────────────────────────────────┐
        │  Wenn Energie-Dashboard-Sensor vorhanden:                       │
        │    self_consumed = energy_self_consumption_sensor               │
        │  Sonst wenn Netzeinspeisung (Dashboard) bekannt:               │
        │    self_consumed = erzeugt − netzeinspeisung                   │
        │  Sonst (nur einfache Sensoren):                                 │
        │    self_consumed = erzeugt − eingespeist_sensor                │
        │                                                                 │
        │  Eigenverbrauchsersparnis = self_consumed × Strompreis          │
        │  Einspeisevergütung       = eingespeist × Vergütungssatz        │
        └─────────────────────────────────────────────────────────────────┘
        """
        base_cost = float(plant.get(CONF_INVESTMENT_COSTS, 0))
        extra_costs = sum(
            float(c["amount"]) for c in plant.get(CONF_ADDITIONAL_COSTS, [])
        )
        result = PlantResult(
            name=plant.get("plant_name", "Anlage"),
            investment=base_cost + extra_costs,
        )

        feed_in_tariff = float(plant.get(CONF_FEED_IN_TARIFF, 0))
        electricity_price = float(plant.get(CONF_ELECTRICITY_PRICE, 0))

        # Einfache kWh-Sensoren
        result.produced_kwh = self._read_sensor(plant.get(CONF_PRODUCTION_SENSOR, ""))
        result.fed_in_kwh = self._read_sensor(plant.get(CONF_FEED_IN_SENSOR, ""))

        # Energie-Dashboard-Sensoren (optional)
        result.energy_self_consumed_kwh = self._read_sensor(
            plant.get(CONF_ENERGY_SELF_CONSUMPTION_SENSOR, "")
        )
        result.energy_from_grid_kwh = self._read_sensor(
            plant.get(CONF_ENERGY_FROM_GRID_SENSOR, "")
        )
        result.energy_to_grid_kwh = self._read_sensor(
            plant.get(CONF_ENERGY_TO_GRID_SENSOR, "")
        )

        # €-Berechnung auf Basis der besten verfügbaren Daten
        result.feed_in_revenue = result.effective_fed_in_kwh * feed_in_tariff
        result.self_consumption_savings = result.effective_self_consumed_kwh * electricity_price

        _LOGGER.debug(
            "%s | erzeugt=%.1f eingespeist=%.1f eigenverbrauch=%.1f netzbezug=%.1f kWh"
            " | vergütung=%.2f € ersparnis=%.2f €",
            result.name,
            result.produced_kwh,
            result.effective_fed_in_kwh,
            result.effective_self_consumed_kwh,
            result.energy_from_grid_kwh,
            result.feed_in_revenue,
            result.self_consumption_savings,
        )
        return result

    # ------------------------------------------------------------------ #
    # Hilfsfunktionen
    # ------------------------------------------------------------------ #
    def _read_sensor(self, entity_id: str) -> float:
        if not entity_id:
            return 0.0
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown", ""):
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Sensor %s hat keinen numerischen Wert: %s", entity_id, state.state
            )
            return 0.0

    def _estimate_amortization_year(
        self,
        yearly_bills: list[dict],
        total_investment: float,
        plants_detail: list[dict],
    ) -> int | None:
        if total_investment <= 0:
            return None

        if yearly_bills:
            sorted_bills = sorted(yearly_bills, key=lambda b: b["year"])
            cumulative = 0.0
            for bill in sorted_bills:
                cumulative += _bill_benefit(bill)
                if cumulative >= total_investment:
                    return int(bill["year"])
            # Extrapolation: Durchschnitt der letzten 3 Jahre
            recent = sorted_bills[-min(3, len(sorted_bills)):]
            avg = sum(_bill_benefit(b) for b in recent) / len(recent)
            if avg > 0:
                return int(sorted_bills[-1]["year"] + (total_investment - cumulative) / avg)

        # Fallback: Live-Sensoren
        current_year = datetime.datetime.now().year
        annual = sum(p["total_revenue"] for p in plants_detail)
        if annual > 0:
            return int(current_year + total_investment / annual)
        return None

    def _build_timeline(
        self,
        yearly_bills: list[dict],
        total_investment: float,
        plants_detail: list[dict],
    ) -> list[dict]:
        """
        Baut die kumulative Verlaufstabelle für die Amortisationskurve.

        Jeder Eintrag enthält:
        - feed_in_revenue:           Einspeisevergütung (€) dieses Jahres
        - self_consumption_savings:  Eigenverbrauchsersparnis (€) dieses Jahres
        - annual_benefit:            Summe beider Positionen
        - cumulative_revenue:        Kumuliert seit Inbetriebnahme
        - net_balance:               Kumuliert − Investition
        - amortization_pct:          Fortschritt in %
        - forecast:                  True bei extrapolierten Jahren
        """
        timeline = []
        cumulative = 0.0
        sorted_bills = sorted(yearly_bills, key=lambda b: b["year"])

        for bill in sorted_bills:
            benefit = _bill_benefit(bill)
            cumulative += benefit

            feed_in = float(bill.get("feed_in_revenue_total", bill.get("feed_in_revenue", 0)))
            savings = benefit - feed_in  # Eigenverbrauchsersparnis = Gesamtnutzen − Einspeisung

            timeline.append({
                "year": bill["year"],
                "annual_benefit": round(benefit, 2),
                "feed_in_revenue": round(feed_in, 2),
                "self_consumption_savings": round(savings, 2),
                "fed_in_kwh": float(bill.get("fed_in_kwh", 0)),
                "feed_in_tariff_actual": float(bill.get("feed_in_tariff_actual", 0)),
                "cumulative_revenue": round(cumulative, 2),
                "net_balance": round(cumulative - total_investment, 2),
                "amortization_pct": round(
                    min(100.0, cumulative / total_investment * 100)
                    if total_investment > 0 else 0.0, 1
                ),
            })

        # Prognosejahre
        if sorted_bills:
            last_year = sorted_bills[-1]["year"]
            recent = sorted_bills[-min(3, len(sorted_bills)):]
            avg = sum(_bill_benefit(b) for b in recent) / len(recent)
            current_year = datetime.datetime.now().year

            for i in range(1, 31):
                fy = last_year + i
                if fy > current_year + 30:
                    break
                cumulative += avg
                timeline.append({
                    "year": fy,
                    "annual_benefit": round(avg, 2),
                    "feed_in_revenue": None,
                    "self_consumption_savings": None,
                    "cumulative_revenue": round(cumulative, 2),
                    "net_balance": round(cumulative - total_investment, 2),
                    "amortization_pct": round(
                        min(100.0, cumulative / total_investment * 100)
                        if total_investment > 0 else 0.0, 1
                    ),
                    "forecast": True,
                })
                if cumulative >= total_investment:
                    break

        return timeline
