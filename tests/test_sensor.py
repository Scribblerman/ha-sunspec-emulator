"""Tests for the SunSpec Emulator sensor platform."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sunspec_emulator.const import DOMAIN


async def test_both_sensors_created(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Both PV power and grid power sensors are created."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    pv_states = [s for s in hass.states.async_all("sensor") if "reported_pv_power" in s.entity_id]
    grid_states = [s for s in hass.states.async_all("sensor") if "reported_grid_power" in s.entity_id]
    assert len(pv_states) == 1
    assert len(grid_states) == 1


async def test_pv_sensor_reflects_value(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    hass.states.async_set("sensor.pv_power", "800")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    states = [s for s in hass.states.async_all("sensor") if "reported_pv_power" in s.entity_id]
    assert float(states[0].state) == 800.0


async def test_grid_sensor_reflects_value(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    hass.states.async_set("sensor.grid_power", "-500")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    states = [s for s in hass.states.async_all("sensor") if "reported_grid_power" in s.entity_id]
    assert float(states[0].state) == -500.0


async def test_pv_sensor_attributes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    states = [s for s in hass.states.async_all("sensor") if "reported_pv_power" in s.entity_id]
    attrs = states[0].attributes
    assert attrs["source_entity"] == "sensor.pv_power"
    assert attrs["unit_of_measurement"] == "W"
    assert attrs["server_running"] is True


async def test_grid_sensor_attributes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    states = [s for s in hass.states.async_all("sensor") if "reported_grid_power" in s.entity_id]
    attrs = states[0].attributes
    assert attrs["source_entity"] == "sensor.grid_power"
    assert attrs["unit_of_measurement"] == "W"
    assert attrs["server_running"] is True


async def test_sensors_update_on_state_change(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    hass.states.async_set("sensor.grid_power", "0")
    hass.states.async_set("sensor.pv_power", "0")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.grid_power", "-1000")
    hass.states.async_set("sensor.pv_power", "1500")
    await hass.async_block_till_done()

    grid = [s for s in hass.states.async_all("sensor") if "reported_grid_power" in s.entity_id]
    pv = [s for s in hass.states.async_all("sensor") if "reported_pv_power" in s.entity_id]
    assert float(grid[0].state) == -1000.0
    assert float(pv[0].state) == 1500.0
