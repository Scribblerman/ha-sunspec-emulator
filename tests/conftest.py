"""Common fixtures for SunSpec Emulator tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    yield


@pytest.fixture
def mock_config_data() -> dict:
    """Return a default config data dict."""
    return {
        "name": "SunSpec Emulator",
        CONF_GRID_ENTITY: "sensor.grid_power",
        CONF_PV_ENTITY: "sensor.pv_power",
        CONF_MODBUS_PORT: DEFAULT_PORT,
        CONF_MODBUS_UNIT_ID: DEFAULT_UNIT_ID,
        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
        CONF_MANUFACTURER: DEFAULT_MANUFACTURER,
        CONF_MODEL_NAME: DEFAULT_MODEL_NAME,
    }


@pytest.fixture
def mock_config_entry(hass, mock_config_data) -> MockConfigEntry:
    """Create and register a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_data,
        title="SunSpec Emulator",
        unique_id="test_sunspec_emulator",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_modbus_server() -> Generator[MagicMock]:
    """Mock the ModbusTcpServer to avoid binding real ports."""
    with patch(
        "custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer"
    ) as mock_cls:
        server_instance = MagicMock()
        server_instance.serve_forever = AsyncMock()
        server_instance.shutdown = AsyncMock()
        mock_cls.return_value = server_instance
        yield mock_cls


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for config flow tests."""
    with patch(
        "custom_components.sunspec_emulator.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
