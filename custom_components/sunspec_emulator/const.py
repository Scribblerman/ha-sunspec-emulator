"""Constants for the SunSpec Emulator integration."""

DOMAIN = "sunspec_emulator"

# Config keys
CONF_GRID_ENTITY = "grid_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_MODBUS_PORT = "modbus_port"
CONF_MODBUS_UNIT_ID = "modbus_unit_id"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL_NAME = "model_name"

# Legacy key (kept for migration from v1 config)
CONF_POWER_ENTITY = "power_entity"
CONF_POWER_MODE = "power_mode"
POWER_MODE_GRID = "grid_power"
POWER_MODE_PV = "pv_production"

# Defaults
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_UPDATE_INTERVAL = 5
DEFAULT_MANUFACTURER = "HA SunSpec Emulator"
DEFAULT_MODEL_NAME = "Virtual Inverter"

# SunSpec register base address
SUNSPEC_BASE_ADDR = 40000

# SunSpec model IDs
SUNSPEC_MODEL_COMMON = 1
SUNSPEC_MODEL_INVERTER_3P = 103
SUNSPEC_MODEL_METER_3P = 203
SUNSPEC_END_MARKER = 0xFFFF

# SunSpec "not implemented" sentinel values
SUNSPEC_NI_INT16 = 0x7FFF
SUNSPEC_NI_UINT16 = 0xFFFF
SUNSPEC_NI_ACC32 = 0x00000000

# Operating states
SUNSPEC_STATE_MPPT = 4  # Normal operation (MPPT tracking)
SUNSPEC_STATE_OFF = 1
SUNSPEC_STATE_SLEEPING = 2
