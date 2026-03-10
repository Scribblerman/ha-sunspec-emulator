"""SunSpec Emulator - Emulate a SunSpec inverter + meter for PV surplus control."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
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
from .sunspec_server import SunSpecServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SunSpec Emulator from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SunSpecCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.async_stop)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: SunSpecCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SunSpecCoordinator:
    """Coordinates between HA entity states and SunSpec Modbus server."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry

        self.grid_entity: str = entry.data[CONF_GRID_ENTITY]
        self.pv_entity: str = entry.data[CONF_PV_ENTITY]
        self.port: int = int(entry.data.get(CONF_MODBUS_PORT, DEFAULT_PORT))
        self.unit_id: int = int(entry.data.get(CONF_MODBUS_UNIT_ID, DEFAULT_UNIT_ID))
        self.update_interval: int = int(
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        )
        manufacturer: str = entry.data.get(CONF_MANUFACTURER, DEFAULT_MANUFACTURER)
        model_name: str = entry.data.get(CONF_MODEL_NAME, DEFAULT_MODEL_NAME)

        self.server = SunSpecServer(
            port=self.port,
            unit_id=self.unit_id,
            manufacturer=manufacturer,
            model_name=model_name,
        )

        self.reported_pv_power: float = 0.0
        self.reported_grid_power: float = 0.0
        self.cumulative_wh: float = 0.0
        self._last_update: datetime | None = None
        self._unsub_grid: callback | None = None
        self._unsub_pv: callback | None = None
        self._sensor_callbacks: list[callback] = []

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device info for this emulator instance."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.data.get(CONF_NAME, "SunSpec Emulator"),
            manufacturer="SunSpec Emulator",
            model="Virtual Inverter + Meter",
            sw_version="2.0.0",
        )

    async def async_start(self) -> None:
        """Start the server and begin tracking entities."""
        await self.server.start()

        # Track grid power entity
        self._unsub_grid = async_track_state_change_event(
            self.hass, [self.grid_entity], self._handle_grid_state_change
        )

        # Track PV power entity
        self._unsub_pv = async_track_state_change_event(
            self.hass, [self.pv_entity], self._handle_pv_state_change
        )

        # Set initial values
        grid_state = self.hass.states.get(self.grid_entity)
        if grid_state and grid_state.state not in ("unknown", "unavailable"):
            try:
                self._update_grid(float(grid_state.state))
            except (ValueError, TypeError):
                pass

        pv_state = self.hass.states.get(self.pv_entity)
        if pv_state and pv_state.state not in ("unknown", "unavailable"):
            try:
                self._update_pv(float(pv_state.state))
            except (ValueError, TypeError):
                pass

        _LOGGER.info(
            "SunSpec Emulator started: grid='%s', pv='%s', port=%d",
            self.grid_entity,
            self.pv_entity,
            self.port,
        )

    async def async_stop(self, event: Event | None = None) -> None:
        """Stop the server and cleanup."""
        if self._unsub_grid:
            self._unsub_grid()
            self._unsub_grid = None
        if self._unsub_pv:
            self._unsub_pv()
            self._unsub_pv = None

        await self.server.stop()
        _LOGGER.info("SunSpec Emulator stopped")

    @callback
    def _handle_grid_state_change(self, event: Event) -> None:
        """Handle state changes of the grid power entity."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            self._update_grid(0.0)
            return
        try:
            self._update_grid(float(new_state.state))
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Cannot parse grid power from '%s': %s",
                self.grid_entity,
                new_state.state,
            )

    @callback
    def _handle_pv_state_change(self, event: Event) -> None:
        """Handle state changes of the PV power entity."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            self._update_pv(0.0)
            return
        try:
            self._update_pv(float(new_state.state))
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Cannot parse PV power from '%s': %s",
                self.pv_entity,
                new_state.state,
            )

    def _update_grid(self, grid_watts: float) -> None:
        """Update meter with grid power (positive=import, negative=export)."""
        self.reported_grid_power = grid_watts
        self.server.update_meter_power(grid_watts)
        self._notify_sensors()

    def _update_pv(self, pv_watts: float) -> None:
        """Update inverter with PV production (positive=generation)."""
        pv = max(0.0, pv_watts)
        self.reported_pv_power = pv
        self.server.update_power(pv)

        # Accumulate energy (Wh)
        now = datetime.now()
        if self._last_update is not None:
            delta_hours = (now - self._last_update).total_seconds() / 3600.0
            self.cumulative_wh += pv * delta_hours
            self.server.update_cumulative_energy(int(self.cumulative_wh))
        self._last_update = now

        self._notify_sensors()

    def _notify_sensors(self) -> None:
        """Notify registered sensors of updates."""
        for cb in self._sensor_callbacks:
            cb()

    def register_sensor(self, callback_fn) -> None:
        """Register a sensor callback for updates."""
        self._sensor_callbacks.append(callback_fn)

    def unregister_sensor(self, callback_fn) -> None:
        """Unregister a sensor callback."""
        if callback_fn in self._sensor_callbacks:
            self._sensor_callbacks.remove(callback_fn)
