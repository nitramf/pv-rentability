"""Konstanten für PV Profitability."""

DOMAIN = "pv_profitability"

# Config Keys – Anlage
CONF_PLANT_NAME = "plant_name"
CONF_PLANTS = "plants"

# Config Keys – Anlage-Detail (einfache Sensoren)
CONF_INVESTMENT_COSTS = "investment_costs"       # Gesamtinvestition in €
CONF_ADDITIONAL_COSTS = "additional_costs"       # Liste weiterer Ausgaben [{year, amount, description}]
CONF_PRODUCTION_SENSOR = "production_sensor"     # HA-Sensor: kWh erzeugt (kumulativ)
CONF_FEED_IN_SENSOR = "feed_in_sensor"           # HA-Sensor: kWh eingespeist (einfach)
CONF_FEED_IN_TARIFF = "feed_in_tariff"           # Einspeisevergütung €/kWh
CONF_ELECTRICITY_PRICE = "electricity_price"     # Strompreis €/kWh (Eigenverbrauch-Ersparnis)

# Energie-Dashboard-Sensoren (optional, haben Vorrang vor einfachen Sensoren)
# Typische Entities aus dem HA-Energie-Dashboard:
#   sensor.solax_self_used_energy     → direkt gemessener Eigenverbrauch
#   sensor.energy_net_consumption     → Netzbezug
#   sensor.solax_energy_to_grid       → Netzeinspeisung
CONF_ENERGY_SELF_CONSUMPTION_SENSOR = "energy_self_consumption_sensor"
CONF_ENERGY_FROM_GRID_SENSOR = "energy_from_grid_sensor"
CONF_ENERGY_TO_GRID_SENSOR = "energy_to_grid_sensor"

# Config Keys – Jahresabrechnungen
CONF_YEARLY_BILLS = "yearly_bills"

# Sensor-Schlüssel
SENSOR_TOTAL_INVESTMENT = "total_investment"
SENSOR_TOTAL_REVENUE = "total_revenue"
SENSOR_TOTAL_SAVINGS = "total_savings"
SENSOR_NET_BALANCE = "net_balance"
SENSOR_AMORTIZATION_YEAR = "amortization_year"
SENSOR_AMORTIZATION_PERCENT = "amortization_percent"

# Defaults
DEFAULT_FEED_IN_TARIFF = 0.082    # €/kWh (Stand 2024, Q1)
DEFAULT_ELECTRICITY_PRICE = 0.30  # €/kWh
