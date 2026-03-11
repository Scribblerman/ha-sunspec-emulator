"""Config flow for SunSpec Emulator integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_GRID_ENTITY,
    CONF_MANUFACTURER,
    CONF_MODBUS_PORT,
    CONF_MODBUS_UNIT_ID,
    CONF_MODEL_NAME,
    CONF_PV_ENTITY,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL_NAME,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DEFAULT_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)


class SunSpecEmulatorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SunSpec Emulator."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            for entry in self._async_current_entries():
                if entry.data.get(CONF_MODBUS_PORT) == user_input.get(CONF_MODBUS_PORT, DEFAULT_PORT):
                    errors["base"] = "port_in_use"
                    break

            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "SunSpec Emulator"),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default="SunSpec Emulator"): TextSelector(),
                    vol.Required(CONF_GRID_ENTITY): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor", device_class="power"
                        )
                    ),
                    vol.Required(CONF_PV_ENTITY): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor", device_class="power"
                        )
                    ),
                    vol.Optional(
                        CONF_MODBUS_PORT, default=DEFAULT_PORT
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_MODBUS_UNIT_ID, default=DEFAULT_UNIT_ID
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=247, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=60, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_MANUFACTURER, default=DEFAULT_MANUFACTURER
                    ): TextSelector(),
                    vol.Optional(
                        CONF_MODEL_NAME, default=DEFAULT_MODEL_NAME
                    ): TextSelector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return SunSpecEmulatorOptionsFlow(config_entry)


class SunSpecEmulatorOptionsFlow(OptionsFlow):
    """Handle options flow for SunSpec Emulator."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_GRID_ENTITY,
                        default=current.get(CONF_GRID_ENTITY),
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor", device_class="power"
                        )
                    ),
                    vol.Required(
                        CONF_PV_ENTITY,
                        default=current.get(CONF_PV_ENTITY),
                    ): EntitySelector(
                        EntitySelectorConfig(
                            domain="sensor", device_class="power"
                        )
                    ),
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=current.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=60, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )
