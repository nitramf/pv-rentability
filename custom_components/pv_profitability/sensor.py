"""Sensor-Entitäten für PV Profitability."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PVCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren beim Setup registrieren."""
    coordinator: PVCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        PVSensor(coordinator, entry, "total_investment", "Gesamtinvestition", "€", "mdi:cash-minus"),
        PVSensor(coordinator, entry, "total_revenue", "Gesamteinnahmen", "€", "mdi:cash-plus"),
        PVSensor(coordinator, entry, "net_balance", "Netto-Saldo", "€", "mdi:cash-sync"),
        PVSensor(coordinator, entry, "amortization_percent", "Amortisation", "%", "mdi:percent"),
        PVAmortizationYearSensor(coordinator, entry),
        PVTimelineSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class PVSensor(CoordinatorEntity, SensorEntity):
    """Einfacher numerischer PV-Sensor."""

    def __init__(
        self,
        coordinator: PVCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unit: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_name = f"PV {name}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = SensorStateClass.MEASUREMENT
        if unit == "€":
            self._attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get(self._key)
        return None

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {
            "plants": self.coordinator.data.get("plants", []),
            "timeline": self.coordinator.data.get("timeline", []),
        }


class PVAmortizationYearSensor(CoordinatorEntity, SensorEntity):
    """Sensor: Geschätztes Amortisationsjahr."""

    def __init__(self, coordinator: PVCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "PV Amortisationsjahr"
        self._attr_unique_id = f"{entry.entry_id}_amortization_year"
        self._attr_icon = "mdi:calendar-check"

    @property
    def native_value(self):
        if self.coordinator.data:
            return self.coordinator.data.get("amortization_year")
        return None


class PVTimelineSensor(CoordinatorEntity, SensorEntity):
    """Sensor: Verlaufsdaten als JSON-Attribut für die Lovelace-Karte."""

    def __init__(self, coordinator: PVCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "PV Verlaufsdaten"
        self._attr_unique_id = f"{entry.entry_id}_timeline"
        self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self) -> str:
        """Anzahl der Datenpunkte im Verlauf."""
        if self.coordinator.data:
            return len(self.coordinator.data.get("timeline", []))
        return 0

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {
            "timeline": self.coordinator.data.get("timeline", []),
            "yearly_bills": self.coordinator.data.get("yearly_bills", []),
            "total_investment": self.coordinator.data.get("total_investment"),
            "amortization_year": self.coordinator.data.get("amortization_year"),
        }
