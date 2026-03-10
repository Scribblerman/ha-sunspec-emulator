"""Sensor platform for SunSpec Emulator."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for SunSpec Emulator."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        SunSpecPVPowerSensor(coordinator, config_entry),
        SunSpecGridPowerSensor(coordinator, config_entry),
    ])


class SunSpecPVPowerSensor(SensorEntity):
    """Sensor showing the PV power reported to the heat pump (inverter model)."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_has_entity_name = True
    _attr_name = "Reported PV Power"
    _attr_icon = "mdi:solar-power-variant"

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_reported_pv_power"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        return self._coordinator.reported_pv_power

    @property
    def available(self) -> bool:
        return self._coordinator.server.is_running

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "source_entity": self._coordinator.pv_entity,
            "modbus_port": self._coordinator.port,
            "server_running": self._coordinator.server.is_running,
            "cumulative_energy_wh": round(self._coordinator.cumulative_wh),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self._coordinator.register_sensor(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(self._handle_coordinator_update)


class SunSpecGridPowerSensor(SensorEntity):
    """Sensor showing the grid power reported to the heat pump (meter model)."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_has_entity_name = True
    _attr_name = "Reported Grid Power"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_reported_grid_power"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        return self._coordinator.reported_grid_power

    @property
    def available(self) -> bool:
        return self._coordinator.server.is_running

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "source_entity": self._coordinator.grid_entity,
            "modbus_port": self._coordinator.port,
            "server_running": self._coordinator.server.is_running,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self._coordinator.register_sensor(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(self._handle_coordinator_update)
