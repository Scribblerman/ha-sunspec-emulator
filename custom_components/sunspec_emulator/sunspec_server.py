"""SunSpec Modbus TCP server emulating a three-phase inverter + meter."""

from __future__ import annotations

import asyncio
import logging
import struct

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext
from pymodbus.server import ModbusTcpServer

try:
    from pymodbus.datastore import ModbusSlaveContext
except ImportError:
    from pymodbus.datastore import ModbusDeviceContext as ModbusSlaveContext

from .const import (
    SUNSPEC_BASE_ADDR,
    SUNSPEC_END_MARKER,
    SUNSPEC_MODEL_COMMON,
    SUNSPEC_MODEL_INVERTER_3P,
    SUNSPEC_NI_INT16,
    SUNSPEC_NI_UINT16,
    SUNSPEC_STATE_MPPT,
    SUNSPEC_STATE_SLEEPING,
)

_LOGGER = logging.getLogger(__name__)

# ── Register layout offsets (relative to SUNSPEC_BASE_ADDR) ──

_HEADER_OFFSET = 0          # 2 regs: "SunS"
_COMMON_ID_OFFSET = 2       # Model 1 header
_COMMON_LEN_OFFSET = 3
_COMMON_DATA_OFFSET = 4     # 66 regs of Model 1 data
_COMMON_LENGTH = 66

# Model 103 (Inverter) starts after header(2) + common(2+66) = 70
_INV_ID_OFFSET = 70
_INV_LEN_OFFSET = 71
_INV_DATA_OFFSET = 72
_INV_LENGTH = 50

# Key fields within Model 103 data (offset from _INV_DATA_OFFSET)
_INV_A = 0       # AC Total Current
_INV_AphA = 1
_INV_AphB = 2
_INV_AphC = 3
_INV_A_SF = 4
_INV_PPVphAB = 5
_INV_PPVphBC = 6
_INV_PPVphCA = 7
_INV_PhVphA = 8
_INV_PhVphB = 9
_INV_PhVphC = 10
_INV_V_SF = 11
_INV_W = 12      # AC Power
_INV_W_SF = 13   # Power Scale Factor
_INV_Hz = 14
_INV_Hz_SF = 15
_INV_VA = 16
_INV_VA_SF = 17
_INV_VAr = 18
_INV_VAr_SF = 19
_INV_PF = 20
_INV_PF_SF = 21
_INV_WH_HI = 22  # Cumulative Energy (high word)
_INV_WH_LO = 23  # Cumulative Energy (low word)
_INV_WH_SF = 24
_INV_DCA = 25
_INV_DCA_SF = 26
_INV_DCV = 27
_INV_DCV_SF = 28
_INV_DCW = 29
_INV_DCW_SF = 30
_INV_TmpCab = 31
_INV_TmpSnk = 32
_INV_TmpTrns = 33
_INV_TmpOt = 34
_INV_Tmp_SF = 35
_INV_St = 36     # Operating State
_INV_StVnd = 37
# 38-49: Event bitfields (6 x uint32 = 12 regs)

# Model 203 (Three-Phase Meter) starts after inverter: 70 + 2 + 50 = 122
_MTR_ID_OFFSET = 122
_MTR_LEN_OFFSET = 123
_MTR_DATA_OFFSET = 124
_MTR_LENGTH = 105

# Key fields within Model 203 data (offset from _MTR_DATA_OFFSET)
# See SunSpec Model 203 specification
_MTR_A = 0        # Total AC Current
_MTR_AphA = 1     # Phase A Current
_MTR_AphB = 2     # Phase B Current
_MTR_AphC = 3     # Phase C Current
_MTR_A_SF = 4     # Current SF
_MTR_PhVphA = 5   # Phase A Voltage (Phase-to-Neutral)
_MTR_PhVphB = 6
_MTR_PhVphC = 7
_MTR_PhV = 8      # Average Phase Voltage
_MTR_PPVphAB = 9  # Line Voltage A-B
_MTR_PPVphBC = 10
_MTR_PPVphCA = 11
_MTR_PPV = 12     # Average Line Voltage
_MTR_V_SF = 13    # Voltage SF
_MTR_Hz = 14      # Frequency
_MTR_Hz_SF = 15   # Frequency SF
_MTR_W = 16       # Total Real Power (W) ← KEY REGISTER
_MTR_WphA = 17    # Phase A Power
_MTR_WphB = 18    # Phase B Power
_MTR_WphC = 19    # Phase C Power
_MTR_W_SF = 20    # Power SF
_MTR_VA = 21      # Total Apparent Power
_MTR_VAphA = 22
_MTR_VAphB = 23
_MTR_VAphC = 24
_MTR_VA_SF = 25
_MTR_VAR = 26     # Total Reactive Power
_MTR_VARphA = 27
_MTR_VARphB = 28
_MTR_VARphC = 29
_MTR_VAR_SF = 30
_MTR_PF = 31      # Average Power Factor
_MTR_PFphA = 32
_MTR_PFphB = 33
_MTR_PFphC = 34
_MTR_PF_SF = 35
# Energy accumulators (acc32 each = 2 regs)
_MTR_TotWhExp_HI = 36   # Total Exported Real Energy
_MTR_TotWhExp_LO = 37
_MTR_TotWhExpPhA_HI = 38
_MTR_TotWhExpPhA_LO = 39
_MTR_TotWhExpPhB_HI = 40
_MTR_TotWhExpPhB_LO = 41
_MTR_TotWhExpPhC_HI = 42
_MTR_TotWhExpPhC_LO = 43
_MTR_TotWhImp_HI = 44   # Total Imported Real Energy
_MTR_TotWhImp_LO = 45
_MTR_TotWhImpPhA_HI = 46
_MTR_TotWhImpPhA_LO = 47
_MTR_TotWhImpPhB_HI = 48
_MTR_TotWhImpPhB_LO = 49
_MTR_TotWhImpPhC_HI = 50
_MTR_TotWhImpPhC_LO = 51
_MTR_TotWh_SF = 52      # Energy SF
# Remaining: apparent/reactive energy accumulators (53-104)

# Total register count: header(2) + common(2+66) + inverter(2+50) + meter(2+105) + end(2) = 231
_TOTAL_REGS = 231

# End marker offset: after meter model
_END_OFFSET = _MTR_ID_OFFSET + 2 + _MTR_LENGTH  # 122 + 107 = 229

# SunSpec Model ID for three-phase wye meter
SUNSPEC_MODEL_METER_3P = 203


def _str_to_regs(text: str, num_regs: int) -> list[int]:
    """Encode a string into SunSpec register values (big-endian, null-padded)."""
    encoded = text.encode("utf-8")[: num_regs * 2]
    encoded = encoded.ljust(num_regs * 2, b"\x00")
    regs = []
    for i in range(0, len(encoded), 2):
        regs.append((encoded[i] << 8) | encoded[i + 1])
    return regs


def _signed_to_uint16(value: int) -> int:
    """Convert a signed int16 value to uint16 for Modbus register."""
    return struct.unpack("H", struct.pack("h", value))[0]


class SunSpecServer:
    """Modbus TCP server emulating a SunSpec-compliant inverter + meter."""

    def __init__(
        self,
        port: int = 502,
        unit_id: int = 1,
        manufacturer: str = "HA SunSpec Emulator",
        model_name: str = "Virtual Inverter",
    ) -> None:
        """Initialize the SunSpec server."""
        self._port = port
        self._unit_id = unit_id
        self._manufacturer = manufacturer
        self._model_name = model_name
        self._server: ModbusTcpServer | None = None
        self._context: ModbusServerContext | None = None
        self._cumulative_wh: float = 0.0
        self._running = False

    def _build_register_block(self) -> ModbusSequentialDataBlock:
        """Build the initial SunSpec register map."""
        regs = [0] * _TOTAL_REGS

        # ── SunSpec header: "SunS" (0x5375, 0x6E53) ──
        regs[_HEADER_OFFSET] = 0x5375
        regs[_HEADER_OFFSET + 1] = 0x6E53

        # ── Common Model (Model 1) ──
        regs[_COMMON_ID_OFFSET] = SUNSPEC_MODEL_COMMON
        regs[_COMMON_LEN_OFFSET] = _COMMON_LENGTH

        common = _COMMON_DATA_OFFSET
        regs[common : common + 16] = _str_to_regs(self._manufacturer, 16)
        regs[common + 16 : common + 32] = _str_to_regs(self._model_name, 16)
        regs[common + 32 : common + 40] = _str_to_regs("", 8)  # Options
        regs[common + 40 : common + 48] = _str_to_regs("1.0.0", 8)  # Version
        regs[common + 48 : common + 64] = _str_to_regs("HA-VIRTUAL-001", 16)  # SN
        regs[common + 64] = self._unit_id  # Device Address
        regs[common + 65] = 0  # Pad

        # ── Inverter Model (Model 103 - Three Phase) ──
        regs[_INV_ID_OFFSET] = SUNSPEC_MODEL_INVERTER_3P
        regs[_INV_LEN_OFFSET] = _INV_LENGTH

        inv = _INV_DATA_OFFSET
        # Currents - not implemented
        regs[inv + _INV_A] = SUNSPEC_NI_UINT16
        regs[inv + _INV_AphA] = SUNSPEC_NI_UINT16
        regs[inv + _INV_AphB] = SUNSPEC_NI_UINT16
        regs[inv + _INV_AphC] = SUNSPEC_NI_UINT16
        regs[inv + _INV_A_SF] = _signed_to_uint16(0)
        # Voltages
        regs[inv + _INV_PPVphAB] = 400
        regs[inv + _INV_PPVphBC] = 400
        regs[inv + _INV_PPVphCA] = 400
        regs[inv + _INV_PhVphA] = 230
        regs[inv + _INV_PhVphB] = 230
        regs[inv + _INV_PhVphC] = 230
        regs[inv + _INV_V_SF] = _signed_to_uint16(0)
        # AC Power - initially 0
        regs[inv + _INV_W] = 0
        regs[inv + _INV_W_SF] = _signed_to_uint16(0)
        # Frequency
        regs[inv + _INV_Hz] = 500  # 50.0 Hz with SF=-1
        regs[inv + _INV_Hz_SF] = _signed_to_uint16(-1)
        # Apparent/Reactive/PF - not implemented
        regs[inv + _INV_VA] = SUNSPEC_NI_INT16
        regs[inv + _INV_VA_SF] = _signed_to_uint16(0)
        regs[inv + _INV_VAr] = SUNSPEC_NI_INT16
        regs[inv + _INV_VAr_SF] = _signed_to_uint16(0)
        regs[inv + _INV_PF] = SUNSPEC_NI_INT16
        regs[inv + _INV_PF_SF] = _signed_to_uint16(0)
        # Cumulative energy
        regs[inv + _INV_WH_HI] = 0
        regs[inv + _INV_WH_LO] = 0
        regs[inv + _INV_WH_SF] = _signed_to_uint16(0)
        # DC values - not implemented
        regs[inv + _INV_DCA] = SUNSPEC_NI_UINT16
        regs[inv + _INV_DCA_SF] = _signed_to_uint16(0)
        regs[inv + _INV_DCV] = SUNSPEC_NI_UINT16
        regs[inv + _INV_DCV_SF] = _signed_to_uint16(0)
        regs[inv + _INV_DCW] = SUNSPEC_NI_INT16
        regs[inv + _INV_DCW_SF] = _signed_to_uint16(0)
        # Temperatures - not implemented
        regs[inv + _INV_TmpCab] = SUNSPEC_NI_INT16
        regs[inv + _INV_TmpSnk] = SUNSPEC_NI_INT16
        regs[inv + _INV_TmpTrns] = SUNSPEC_NI_INT16
        regs[inv + _INV_TmpOt] = SUNSPEC_NI_INT16
        regs[inv + _INV_Tmp_SF] = _signed_to_uint16(0)
        # Operating state
        regs[inv + _INV_St] = SUNSPEC_STATE_SLEEPING
        regs[inv + _INV_StVnd] = 0
        # Event bitfields - all zero
        for i in range(38, 50):
            regs[inv + i] = 0

        # ── Meter Model (Model 203 - Three Phase Wye) ──
        regs[_MTR_ID_OFFSET] = SUNSPEC_MODEL_METER_3P
        regs[_MTR_LEN_OFFSET] = _MTR_LENGTH

        mtr = _MTR_DATA_OFFSET
        # Currents - zero (Nibe rejects NI sentinel values)
        regs[mtr + _MTR_A] = 0
        regs[mtr + _MTR_AphA] = 0
        regs[mtr + _MTR_AphB] = 0
        regs[mtr + _MTR_AphC] = 0
        regs[mtr + _MTR_A_SF] = _signed_to_uint16(0)
        # Voltages - defaults
        regs[mtr + _MTR_PhVphA] = 230
        regs[mtr + _MTR_PhVphB] = 230
        regs[mtr + _MTR_PhVphC] = 230
        regs[mtr + _MTR_PhV] = 230
        regs[mtr + _MTR_PPVphAB] = 400
        regs[mtr + _MTR_PPVphBC] = 400
        regs[mtr + _MTR_PPVphCA] = 400
        regs[mtr + _MTR_PPV] = 400
        regs[mtr + _MTR_V_SF] = _signed_to_uint16(0)
        # Frequency
        regs[mtr + _MTR_Hz] = 500  # 50.0 Hz with SF=-1
        regs[mtr + _MTR_Hz_SF] = _signed_to_uint16(-1)
        # Total Real Power (W) - initially 0 (positive=import, negative=export)
        regs[mtr + _MTR_W] = 0
        regs[mtr + _MTR_WphA] = 0
        regs[mtr + _MTR_WphB] = 0
        regs[mtr + _MTR_WphC] = 0
        regs[mtr + _MTR_W_SF] = _signed_to_uint16(0)
        # Apparent/Reactive/PF - zero (Nibe rejects NI sentinel values)
        regs[mtr + _MTR_VA] = 0
        regs[mtr + _MTR_VAphA] = 0
        regs[mtr + _MTR_VAphB] = 0
        regs[mtr + _MTR_VAphC] = 0
        regs[mtr + _MTR_VA_SF] = _signed_to_uint16(0)
        regs[mtr + _MTR_VAR] = 0
        regs[mtr + _MTR_VARphA] = 0
        regs[mtr + _MTR_VARphB] = 0
        regs[mtr + _MTR_VARphC] = 0
        regs[mtr + _MTR_VAR_SF] = _signed_to_uint16(0)
        regs[mtr + _MTR_PF] = 0
        regs[mtr + _MTR_PFphA] = 0
        regs[mtr + _MTR_PFphB] = 0
        regs[mtr + _MTR_PFphC] = 0
        regs[mtr + _MTR_PF_SF] = _signed_to_uint16(0)
        # Energy accumulators - all zero
        for i in range(_MTR_TotWhExp_HI, _MTR_TotWh_SF):
            regs[mtr + i] = 0
        regs[mtr + _MTR_TotWh_SF] = _signed_to_uint16(0)
        # Remaining apparent/reactive energy accumulators (53-104) - zero
        for i in range(53, _MTR_LENGTH):
            regs[mtr + i] = 0

        # ── End marker ──
        regs[_END_OFFSET] = SUNSPEC_END_MARKER
        regs[_END_OFFSET + 1] = 0

        # Prepend two dummy registers to account for Modbus 1-based addressing
        # in pymodbus 3.12+ (ModbusDeviceContext has implicit +1 offset).
        return ModbusSequentialDataBlock(SUNSPEC_BASE_ADDR - 1, [0, 0] + regs)

    async def start(self) -> None:
        """Start the Modbus TCP server."""
        if self._running:
            return

        block = self._build_register_block()
        store = ModbusSlaveContext(hr=block)
        self._context = ModbusServerContext(
            devices={self._unit_id: store}, single=False
        )

        self._server = ModbusTcpServer(
            self._context,
            address=("0.0.0.0", self._port),
        )

        asyncio.create_task(self._server.serve_forever())
        self._running = True
        _LOGGER.info(
            "SunSpec emulator started on port %d (unit ID %d)",
            self._port,
            self._unit_id,
        )

    async def stop(self) -> None:
        """Stop the Modbus TCP server."""
        if self._server and self._running:
            await self._server.shutdown()
            self._running = False
            _LOGGER.info("SunSpec emulator stopped")

    @property
    def is_running(self) -> bool:
        """Return whether the server is running."""
        return self._running

    def update_power(self, power_watts: float) -> None:
        """Update the reported PV AC power (inverter model).

        Args:
            power_watts: PV surplus power in watts (>= 0).
        """
        if not self._context:
            return

        power_w = max(0, int(round(power_watts)))

        inv = _INV_DATA_OFFSET
        store = self._context[self._unit_id]

        # Update inverter AC Power (W) register
        store.setValues(3, SUNSPEC_BASE_ADDR + inv + _INV_W, [power_w])

        # Update operating state
        state = SUNSPEC_STATE_MPPT if power_w > 0 else SUNSPEC_STATE_SLEEPING
        store.setValues(3, SUNSPEC_BASE_ADDR + inv + _INV_St, [state])

        _LOGGER.debug("SunSpec inverter power updated: %d W (state: %d)", power_w, state)

    def update_meter_power(self, grid_watts: float) -> None:
        """Update the meter grid power (positive=import, negative=export).

        Args:
            grid_watts: Grid power in watts. Positive = importing, negative = exporting.
        """
        if not self._context:
            return

        grid_w = int(round(grid_watts))

        mtr = _MTR_DATA_OFFSET
        store = self._context[self._unit_id]

        # Update meter Total Real Power (W) - signed int16
        grid_u16 = _signed_to_uint16(grid_w)
        store.setValues(
            3, SUNSPEC_BASE_ADDR + mtr + _MTR_W, [grid_u16]
        )
        # Distribute equally across phases for consistency
        phase_w = int(round(grid_watts / 3))
        phase_u16 = _signed_to_uint16(phase_w)
        store.setValues(
            3, SUNSPEC_BASE_ADDR + mtr + _MTR_WphA, [phase_u16]
        )
        store.setValues(
            3, SUNSPEC_BASE_ADDR + mtr + _MTR_WphB, [phase_u16]
        )
        store.setValues(
            3, SUNSPEC_BASE_ADDR + mtr + _MTR_WphC, [phase_u16]
        )

        _LOGGER.debug("SunSpec meter power updated: %d W", grid_w)

    def update_cumulative_energy(self, total_wh: int) -> None:
        """Update the cumulative energy counter (Wh)."""
        if not self._context:
            return

        inv = _INV_DATA_OFFSET
        store = self._context[self._unit_id]

        total_wh = max(0, int(total_wh))
        high = (total_wh >> 16) & 0xFFFF
        low = total_wh & 0xFFFF
        store.setValues(
            3, SUNSPEC_BASE_ADDR + inv + _INV_WH_HI, [high, low]
        )
