"""Tests for integration setup and teardown."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sunspec_emulator.const import DOMAIN


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]


async def test_setup_creates_coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator is not None
    assert coordinator.grid_entity == "sensor.grid_power"
    assert coordinator.pv_entity == "sensor.pv_power"
    assert coordinator.server.is_running


async def test_setup_tracks_initial_grid_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    hass.states.async_set("sensor.grid_power", "-800")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_grid_power == -800.0


async def test_setup_tracks_initial_pv_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    hass.states.async_set("sensor.pv_power", "600")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_pv_power == 600.0


async def test_setup_handles_unavailable_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    hass.states.async_set("sensor.grid_power", "unavailable")
    hass.states.async_set("sensor.pv_power", "unavailable")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_grid_power == 0.0
    assert coordinator.reported_pv_power == 0.0


async def test_setup_handles_missing_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_grid_power == 0.0
    assert coordinator.reported_pv_power == 0.0
