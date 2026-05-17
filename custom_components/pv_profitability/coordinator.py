"""DataUpdateCoordinator für PV Profitability."""
from __future__ import annotations

import logging
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
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)


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

    async def _async_update_data(self) -> dict:
        """Daten aus HA-Sensoren lesen und Rentabilität berechnen."""
        data = self.entry.data
        plants: list[dict] = data.get(CONF_PLANTS, [])
        yearly_bills: list[dict] = data.get(CONF_YEARLY_BILLS, [])

        # ---- Gesamtinvestition (Anlage-Kosten + Zusatzausgaben) --------
        total_investment = 0.0
        plants_detail = []

        for plant in plants:
            base_cost = float(plant.get(CONF_INVESTMENT_COSTS, 0))
            extra_costs = sum(
                float(c["amount"]) for c in plant.get(CONF_ADDITIONAL_COSTS, [])
            )
            plant_investment = base_cost + extra_costs

            # Sensor-Wert lesen (erzeugte kWh, kumulativ)
            produced_kwh = self._read_sensor(plant.get(CONF_PRODUCTION_SENSOR, ""))
            fed_in_kwh = self._read_sensor(plant.get(CONF_FEED_IN_SENSOR, ""))
            self_consumed_kwh = max(0.0, produced_kwh - fed_in_kwh)

            feed_in_tariff = float(plant.get(CONF_FEED_IN_TARIFF, 0))
            electricity_price = float(plant.get(CONF_ELECTRICITY_PRICE, 0))

            # Einnahmen aus Einspeisung + Ersparnis durch Eigenverbrauch
            feed_in_revenue = fed_in_kwh * feed_in_tariff
            self_consumption_savings = self_consumed_kwh * electricity_price

            plants_detail.append(
                {
                    "name": plant.get("plant_name", "Anlage"),
                    "investment": plant_investment,
                    "produced_kwh": produced_kwh,
                    "fed_in_kwh": fed_in_kwh,
                    "self_consumed_kwh": self_consumed_kwh,
                    "feed_in_revenue": feed_in_revenue,
                    "self_consumption_savings": self_consumption_savings,
                    "total_revenue": feed_in_revenue + self_consumption_savings,
                }
            )
            total_investment += plant_investment

        # ---- Jahresabrechnungen summieren --------------------------------
        # Neues Format: annual_benefit = Einspeisevergütung + Stromersparnis
        # Altes Format (Fallback): feed_in_revenue + electricity_cost
        total_bill_benefit = sum(
            float(b.get("annual_benefit")
                  or float(b.get("feed_in_revenue_total", 0))
                  + max(0.0,
                        float(b.get("electricity_cost_without_pv", 0))
                        - float(b.get("electricity_cost_total", b.get("electricity_cost", 0))))
                  )
            for b in yearly_bills
        )

        # ---- Laufende Sensor-Einnahmen (falls keine Jahresrechnung) ------
        sensor_revenue = sum(p["total_revenue"] for p in plants_detail)

        # Kombiniert: wenn Jahresabrechnungen vorhanden, diese bevorzugen
        if yearly_bills:
            total_revenue = total_bill_benefit
        else:
            total_revenue = sensor_revenue

        net_balance = total_revenue - total_investment
        amortization_percent = min(
            100.0,
            (total_revenue / total_investment * 100) if total_investment > 0 else 0.0,
        )

        # ---- Amortisationsjahr schätzen ----------------------------------
        amortization_year = self._estimate_amortization_year(
            yearly_bills, total_investment, plants_detail
        )

        # ---- Jahres-Verlaufsdaten für die Karte -------------------------
        timeline = self._build_timeline(yearly_bills, total_investment, plants_detail)

        return {
            "total_investment": round(total_investment, 2),
            "total_revenue": round(total_revenue, 2),
            "net_balance": round(net_balance, 2),
            "amortization_percent": round(amortization_percent, 1),
            "amortization_year": amortization_year,
            "plants": plants_detail,
            "yearly_bills": yearly_bills,
            "timeline": timeline,
        }

    def _read_sensor(self, entity_id: str) -> float:
        """Liest einen HA-Sensor und gibt seinen Wert als float zurück."""
        if not entity_id:
            return 0.0
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown", ""):
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("Sensor %s hat keinen numerischen Wert: %s", entity_id, state.state)
            return 0.0

    def _estimate_amortization_year(
        self,
        yearly_bills: list[dict],
        total_investment: float,
        plants_detail: list[dict],
    ) -> int | None:
        """Schätzt das Kalenderjahr, in dem die Investition amortisiert ist."""
        if total_investment <= 0:
            return None

        if yearly_bills:
            sorted_bills = sorted(yearly_bills, key=lambda b: b["year"])
            cumulative = 0.0
            for bill in sorted_bills:
                cumulative += float(
                    bill.get("annual_benefit")
                    or float(bill.get("feed_in_revenue_total", 0))
                    + max(0.0,
                          float(bill.get("electricity_cost_without_pv", 0))
                          - float(bill.get("electricity_cost_total", bill.get("electricity_cost", 0))))
                )
                if cumulative >= total_investment:
                    return int(bill["year"])

            # Extrapolation mit Durchschnitt der letzten 3 Jahre
            if len(sorted_bills) >= 1:
                recent = sorted_bills[-min(3, len(sorted_bills)):]
                avg_annual = sum(
                    float(b.get("annual_benefit")
                          or float(b.get("feed_in_revenue_total", 0))
                          + max(0.0,
                                float(b.get("electricity_cost_without_pv", 0))
                                - float(b.get("electricity_cost_total", b.get("electricity_cost", 0))))
                          )
                    for b in recent
                ) / len(recent)
                if avg_annual > 0:
                    remaining = total_investment - cumulative
                    years_left = remaining / avg_annual
                    return int(sorted_bills[-1]["year"] + years_left)

        # Fallback: Sensor-basierte Jahresschätzung
        import datetime
        current_year = datetime.datetime.now().year
        total_annual = sum(p["total_revenue"] for p in plants_detail)
        if total_annual > 0:
            years_needed = total_investment / total_annual
            return int(current_year + years_needed)

        return None

    def _build_timeline(
        self,
        yearly_bills: list[dict],
        total_investment: float,
        plants_detail: list[dict],
    ) -> list[dict]:
        """Erstellt eine kumulative Verlaufstabelle für die Amortisationskurve."""
        timeline = []
        cumulative = 0.0
        sorted_bills = sorted(yearly_bills, key=lambda b: b["year"])

        for bill in sorted_bills:
            revenue = float(
                bill.get("annual_benefit")
                or float(bill.get("feed_in_revenue_total", 0))
                + max(0.0,
                      float(bill.get("electricity_cost_without_pv", 0))
                      - float(bill.get("electricity_cost_total", bill.get("electricity_cost", 0))))
            )
            cumulative += revenue
            timeline.append(
                {
                    "year": bill["year"],
                    "annual_revenue": round(revenue, 2),
                    "cumulative_revenue": round(cumulative, 2),
                    "net_balance": round(cumulative - total_investment, 2),
                    "amortization_pct": round(
                        min(100.0, cumulative / total_investment * 100)
                        if total_investment > 0
                        else 0.0,
                        1,
                    ),
                }
            )

        # Prognosejahre extrapolieren (bis zur Amortisation, max. 10 weitere Jahre)
        if sorted_bills:
            import datetime
            last_year = sorted_bills[-1]["year"]
            recent = sorted_bills[-min(3, len(sorted_bills)):]
            avg_annual = sum(
                float(b.get("annual_benefit")
                      or float(b.get("feed_in_revenue_total", 0))
                      + max(0.0,
                            float(b.get("electricity_cost_without_pv", 0))
                            - float(b.get("electricity_cost_total", b.get("electricity_cost", 0))))
                      )
                for b in recent
            ) / len(recent)

            current_year = datetime.datetime.now().year
            for i in range(1, 11):
                forecast_year = last_year + i
                if forecast_year > current_year + 25:
                    break
                cumulative += avg_annual
                timeline.append(
                    {
                        "year": forecast_year,
                        "annual_revenue": round(avg_annual, 2),
                        "cumulative_revenue": round(cumulative, 2),
                        "net_balance": round(cumulative - total_investment, 2),
                        "amortization_pct": round(
                            min(100.0, cumulative / total_investment * 100)
                            if total_investment > 0
                            else 0.0,
                            1,
                        ),
                        "forecast": True,
                    }
                )
                if cumulative >= total_investment:
                    break

        return timeline
