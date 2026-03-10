"""Tests for the SunSpec Emulator config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sunspec_emulator.const import (
    CONF_GRID_ENTITY,
    CONF_MANUFACTURER,
    CONF_MODBUS_PORT,
    CONF_MODBUS_UNIT_ID,
    CONF_MODEL_NAME,
    CONF_PV_ENTITY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)


async def test_flow_shows_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the config flow shows a form on first step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_flow_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    user_input = {
        "name": "My SunSpec",
        CONF_GRID_ENTITY: "sensor.grid_power",
        CONF_PV_ENTITY: "sensor.pv_power",
        CONF_MODBUS_PORT: 1502,
        CONF_MODBUS_UNIT_ID: DEFAULT_UNIT_ID,
        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
        CONF_MANUFACTURER: DEFAULT_MANUFACTURER,
        CONF_MODEL_NAME: DEFAULT_MODEL_NAME,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My SunSpec"
    assert result["data"][CONF_GRID_ENTITY] == "sensor.grid_power"
    assert result["data"][CONF_PV_ENTITY] == "sensor.pv_power"
    assert result["data"][CONF_MODBUS_PORT] == 1502
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_default_values(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that defaults are applied when optional fields are omitted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    user_input = {
        CONF_GRID_ENTITY: "sensor.shelly_power",
        CONF_PV_ENTITY: "sensor.hoymiles_power",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GRID_ENTITY] == "sensor.shelly_power"
    assert result["data"][CONF_PV_ENTITY] == "sensor.hoymiles_power"


async def test_flow_port_conflict(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that duplicate ports are rejected."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_GRID_ENTITY: "sensor.existing",
            CONF_PV_ENTITY: "sensor.existing_pv",
            CONF_MODBUS_PORT: 502,
        },
        title="Existing",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    user_input = {
        CONF_GRID_ENTITY: "sensor.grid_power",
        CONF_PV_ENTITY: "sensor.pv_power",
        CONF_MODBUS_PORT: 502,
        CONF_MODBUS_UNIT_ID: DEFAULT_UNIT_ID,
        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
        CONF_MANUFACTURER: DEFAULT_MANUFACTURER,
        CONF_MODEL_NAME: DEFAULT_MODEL_NAME,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "port_in_use"}


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_modbus_server
) -> None:
    """Test the options flow allows changing entities."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_GRID_ENTITY: "sensor.new_grid",
            CONF_PV_ENTITY: "sensor.new_pv",
            CONF_UPDATE_INTERVAL: 10,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GRID_ENTITY] == "sensor.new_grid"
    assert result["data"][CONF_PV_ENTITY] == "sensor.new_pv"
