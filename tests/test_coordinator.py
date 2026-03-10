"""Tests for the SunSpecCoordinator with two-entity model."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sunspec_emulator.const import DOMAIN


async def test_grid_power_import(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Positive grid power = importing from grid."""
    hass.states.async_set("sensor.grid_power", "500")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_grid_power == 500.0


async def test_grid_power_export(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Negative grid power = exporting to grid."""
    hass.states.async_set("sensor.grid_power", "-1200")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_grid_power == -1200.0


async def test_pv_power_generation(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Positive PV power = generating."""
    hass.states.async_set("sensor.pv_power", "600")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_pv_power == 600.0


async def test_pv_power_negative_clamped(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Negative PV power is clamped to 0."""
    hass.states.async_set("sensor.pv_power", "-50")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_pv_power == 0.0


async def test_grid_state_change(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Grid power updates on state change."""
    hass.states.async_set("sensor.grid_power", "0")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_grid_power == 0.0

    hass.states.async_set("sensor.grid_power", "-2000")
    await hass.async_block_till_done()
    assert coordinator.reported_grid_power == -2000.0


async def test_pv_state_change(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """PV power updates on state change."""
    hass.states.async_set("sensor.pv_power", "0")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_pv_power == 0.0

    hass.states.async_set("sensor.pv_power", "750")
    await hass.async_block_till_done()
    assert coordinator.reported_pv_power == 750.0


async def test_independent_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Grid and PV entities update independently."""
    hass.states.async_set("sensor.grid_power", "-300")
    hass.states.async_set("sensor.pv_power", "600")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_grid_power == -300.0
    assert coordinator.reported_pv_power == 600.0

    # Only grid changes
    hass.states.async_set("sensor.grid_power", "100")
    await hass.async_block_till_done()
    assert coordinator.reported_grid_power == 100.0
    assert coordinator.reported_pv_power == 600.0  # unchanged


async def test_non_numeric_grid_ignored(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Non-numeric grid state doesn't crash."""
    hass.states.async_set("sensor.grid_power", "-500")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_grid_power == -500.0

    hass.states.async_set("sensor.grid_power", "not_a_number")
    await hass.async_block_till_done()
    assert coordinator.reported_grid_power == -500.0  # unchanged


async def test_unavailable_resets_to_zero(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server,
) -> None:
    """Unavailable entity resets reported value to 0."""
    hass.states.async_set("sensor.pv_power", "600")
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.reported_pv_power == 600.0

    hass.states.async_set("sensor.pv_power", "unavailable")
    await hass.async_block_till_done()
    assert coordinator.reported_pv_power == 0.0
