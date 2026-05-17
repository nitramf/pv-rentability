"""Config Flow für PV Profitability."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_PLANT_NAME,
    CONF_PLANTS,
    CONF_INVESTMENT_COSTS,
    CONF_ADDITIONAL_COSTS,
    CONF_PRODUCTION_SENSOR,
    CONF_FEED_IN_SENSOR,
    CONF_FEED_IN_TARIFF,
    CONF_ELECTRICITY_PRICE,
    CONF_YEARLY_BILLS,
    DEFAULT_FEED_IN_TARIFF,
    DEFAULT_ELECTRICITY_PRICE,
)


class PVProfitabilityConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for PV Profitability."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Erster Schritt: Name der Anlage + Grunddaten."""
        errors = {}

        if user_input is not None:
            # Erste Anlage als Liste anlegen
            plants = [
                {
                    CONF_PLANT_NAME: user_input[CONF_PLANT_NAME],
                    CONF_INVESTMENT_COSTS: user_input[CONF_INVESTMENT_COSTS],
                    CONF_PRODUCTION_SENSOR: user_input[CONF_PRODUCTION_SENSOR],
                    CONF_FEED_IN_SENSOR: user_input.get(CONF_FEED_IN_SENSOR, ""),
                    CONF_FEED_IN_TARIFF: user_input[CONF_FEED_IN_TARIFF],
                    CONF_ELECTRICITY_PRICE: user_input[CONF_ELECTRICITY_PRICE],
                    CONF_ADDITIONAL_COSTS: [],
                }
            ]
            data = {
                CONF_PLANTS: plants,
                CONF_YEARLY_BILLS: [],
            }
            return self.async_create_entry(
                title=user_input[CONF_PLANT_NAME],
                data=data,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_PLANT_NAME, default="Hauptanlage"): str,
                vol.Required(CONF_INVESTMENT_COSTS): vol.Coerce(float),
                vol.Required(CONF_PRODUCTION_SENSOR): str,
                vol.Optional(CONF_FEED_IN_SENSOR, default=""): str,
                vol.Required(
                    CONF_FEED_IN_TARIFF, default=DEFAULT_FEED_IN_TARIFF
                ): vol.Coerce(float),
                vol.Required(
                    CONF_ELECTRICITY_PRICE, default=DEFAULT_ELECTRICITY_PRICE
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PVOptionsFlow(config_entry)


class PVOptionsFlow(config_entries.OptionsFlow):
    """Options Flow: weitere Anlagen, Ausgaben und Jahresabrechnungen."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._plants = list(config_entry.data.get(CONF_PLANTS, []))
        self._yearly_bills = list(config_entry.data.get(CONF_YEARLY_BILLS, []))
        self._menu_choice = None
        self._pending_bill: dict = {}

    async def async_step_init(self, user_input=None):
        """Hauptmenü der Optionen."""
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "manage_plants": "Anlagen verwalten",
                "add_yearly_bill": "Jahresabrechnung hinzufügen",
                "finish": "Speichern & Schließen",
            },
        )

    # ------------------------------------------------------------------ #
    # Anlagen verwalten
    # ------------------------------------------------------------------ #
    async def async_step_manage_plants(self, user_input=None):
        """Anlage hinzufügen oder bestehende anpassen."""
        return self.async_show_menu(
            step_id="manage_plants",
            menu_options={
                "add_plant": "Neue Anlage hinzufügen",
                "add_cost": "Zusatzausgabe zu einer Anlage hinzufügen",
                "finish": "Zurück / Speichern",
            },
        )

    async def async_step_add_plant(self, user_input=None):
        """Neue Anlage anlegen."""
        if user_input is not None:
            self._plants.append(
                {
                    CONF_PLANT_NAME: user_input[CONF_PLANT_NAME],
                    CONF_INVESTMENT_COSTS: user_input[CONF_INVESTMENT_COSTS],
                    CONF_PRODUCTION_SENSOR: user_input[CONF_PRODUCTION_SENSOR],
                    CONF_FEED_IN_SENSOR: user_input.get(CONF_FEED_IN_SENSOR, ""),
                    CONF_FEED_IN_TARIFF: user_input[CONF_FEED_IN_TARIFF],
                    CONF_ELECTRICITY_PRICE: user_input[CONF_ELECTRICITY_PRICE],
                    CONF_ADDITIONAL_COSTS: [],
                }
            )
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_PLANT_NAME): str,
                vol.Required(CONF_INVESTMENT_COSTS): vol.Coerce(float),
                vol.Required(CONF_PRODUCTION_SENSOR): str,
                vol.Optional(CONF_FEED_IN_SENSOR, default=""): str,
                vol.Required(
                    CONF_FEED_IN_TARIFF, default=DEFAULT_FEED_IN_TARIFF
                ): vol.Coerce(float),
                vol.Required(
                    CONF_ELECTRICITY_PRICE, default=DEFAULT_ELECTRICITY_PRICE
                ): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="add_plant", data_schema=schema)

    async def async_step_add_cost(self, user_input=None):
        """Zusatzausgabe (z. B. Reparatur) zu einer bestehenden Anlage."""
        if user_input is not None:
            idx = user_input["plant_index"]
            self._plants[idx][CONF_ADDITIONAL_COSTS].append(
                {
                    "year": user_input["year"],
                    "amount": user_input["amount"],
                    "description": user_input["description"],
                }
            )
            return await self.async_step_init()

        plant_names = {
            str(i): p[CONF_PLANT_NAME] for i, p in enumerate(self._plants)
        }
        schema = vol.Schema(
            {
                vol.Required("plant_index"): vol.In(plant_names),
                vol.Required("year"): vol.Coerce(int),
                vol.Required("amount"): vol.Coerce(float),
                vol.Required("description", default="Wartung / Reparatur"): str,
            }
        )
        return self.async_show_form(step_id="add_cost", data_schema=schema)

    # ------------------------------------------------------------------ #
    # Jahresabrechnungen  (zweistufig)
    # ------------------------------------------------------------------ #
    async def async_step_add_yearly_bill(self, user_input=None):
        """Schritt 1: Stromabrechnung des Versorgers eintragen."""
        if user_input is not None:
            # Zwischenspeichern, weiter zu Schritt 2
            self._pending_bill = {
                "year": int(user_input["year"]),
                "grid_kwh_purchased": float(user_input.get("grid_kwh_purchased", 0.0)),
                "electricity_cost_total": float(user_input["electricity_cost_total"]),
                "electricity_cost_without_pv": float(
                    user_input.get("electricity_cost_without_pv", 0.0)
                ),
            }
            return await self.async_step_add_feed_in_bill()

        schema = vol.Schema(
            {
                vol.Required("year"): vol.Coerce(int),
                # Bezogene kWh aus dem Netz laut Zähler
                vol.Optional("grid_kwh_purchased", default=0.0): vol.Coerce(float),
                # Tatsächlich bezahlte Stromrechnung (€)
                vol.Required("electricity_cost_total", default=0.0): vol.Coerce(float),
                # Geschätzte Kosten ohne PV (optional, für Ersparnis-Berechnung)
                vol.Optional("electricity_cost_without_pv", default=0.0): vol.Coerce(float),
            }
        )
        return self.async_show_form(
            step_id="add_yearly_bill",
            data_schema=schema,
            description_placeholders={
                "hint": "Schritt 1 von 2: Daten aus der Stromrechnung deines Versorgers"
            },
        )

    async def async_step_add_feed_in_bill(self, user_input=None):
        """Schritt 2: Einspeisevergütungs-Abrechnung des Netzbetreibers eintragen."""
        if user_input is not None:
            fed_in_kwh = float(user_input.get("fed_in_kwh", 0.0))
            feed_in_tariff_actual = float(user_input.get("feed_in_tariff_actual", 0.0))
            # Betrag aus Abrechnung hat Vorrang; sonst aus kWh × Tarif berechnen
            feed_in_revenue = float(user_input.get("feed_in_revenue_total", 0.0))
            if feed_in_revenue == 0.0 and fed_in_kwh > 0 and feed_in_tariff_actual > 0:
                feed_in_revenue = round(fed_in_kwh * feed_in_tariff_actual, 2)

            year = self._pending_bill["year"]
            self._yearly_bills = [b for b in self._yearly_bills if b["year"] != year]
            self._yearly_bills.append(
                {
                    **self._pending_bill,
                    "fed_in_kwh": fed_in_kwh,
                    "feed_in_tariff_actual": feed_in_tariff_actual,
                    "feed_in_revenue_total": feed_in_revenue,
                    # Gesamteinnahmen/-ersparnisse dieses Jahres für die Amortisationsrechnung:
                    # Einspeisevergütung + Ersparnis gegenüber Kosten ohne PV
                    "annual_benefit": round(
                        feed_in_revenue
                        + max(
                            0.0,
                            self._pending_bill["electricity_cost_without_pv"]
                            - self._pending_bill["electricity_cost_total"],
                        ),
                        2,
                    ),
                }
            )
            self._pending_bill = {}
            return await self.async_step_init()

        schema = vol.Schema(
            {
                # Eingespeiste kWh laut Abrechnung des Netzbetreibers
                vol.Optional("fed_in_kwh", default=0.0): vol.Coerce(float),
                # Vergütungssatz €/kWh (steht auf der Abrechnung)
                vol.Optional("feed_in_tariff_actual", default=0.0): vol.Coerce(float),
                # Ausgezahlter Gesamtbetrag (€) – überschreibt kWh × Tarif wenn angegeben
                vol.Optional("feed_in_revenue_total", default=0.0): vol.Coerce(float),
            }
        )
        return self.async_show_form(
            step_id="add_feed_in_bill",
            data_schema=schema,
            description_placeholders={
                "hint": "Schritt 2 von 2: Daten aus der Einspeisevergütungs-Abrechnung des Netzbetreibers"
            },
        )

    # ------------------------------------------------------------------ #
    # Abschluss
    # ------------------------------------------------------------------ #
    async def async_step_finish(self, user_input=None):
        """Speichern und Options-Flow abschließen."""
        new_data = dict(self.config_entry.data)
        new_data[CONF_PLANTS] = self._plants
        new_data[CONF_YEARLY_BILLS] = self._yearly_bills
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data
        )
        return self.async_create_entry(title="", data={})
