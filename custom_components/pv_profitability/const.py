"""Konstanten für PV Profitability."""

DOMAIN = "pv_profitability"

# Config Keys – Anlage
CONF_PLANT_NAME = "plant_name"
CONF_PLANTS = "plants"

# Config Keys – Anlage-Detail
CONF_INVESTMENT_COSTS = "investment_costs"       # Gesamtinvestition in €
CONF_ADDITIONAL_COSTS = "additional_costs"       # Liste weiterer Ausgaben [{year, amount, description}]
CONF_PRODUCTION_SENSOR = "production_sensor"     # HA-Sensor: kWh erzeugt (kumulativ oder Jahreswert)
CONF_FEED_IN_SENSOR = "feed_in_sensor"           # HA-Sensor: kWh eingespeist
CONF_FEED_IN_TARIFF = "feed_in_tariff"           # Einspeisevergütung €/kWh
CONF_ELECTRICITY_PRICE = "electricity_price"     # Strompreis €/kWh (für Eigenverbrauch-Ersparnis)

# Config Keys – Jahresabrechnungen
CONF_YEARLY_BILLS = "yearly_bills"               # [{year, electricity_cost, feed_in_revenue}]

# Sensor-Schlüssel
SENSOR_TOTAL_INVESTMENT = "total_investment"
SENSOR_TOTAL_REVENUE = "total_revenue"
SENSOR_TOTAL_SAVINGS = "total_savings"
SENSOR_NET_BALANCE = "net_balance"
SENSOR_AMORTIZATION_YEAR = "amortization_year"
SENSOR_AMORTIZATION_PERCENT = "amortization_percent"

# Defaults
DEFAULT_FEED_IN_TARIFF = 0.082   # €/kWh (Stand 2024, Q1)
DEFAULT_ELECTRICITY_PRICE = 0.30  # €/kWh
