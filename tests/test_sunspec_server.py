"""Tests for the SunSpec Modbus TCP server."""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.sunspec_emulator.const import (
    SUNSPEC_BASE_ADDR,
    SUNSPEC_END_MARKER,
    SUNSPEC_MODEL_COMMON,
    SUNSPEC_MODEL_INVERTER_3P,
    SUNSPEC_MODEL_METER_3P,
    SUNSPEC_NI_INT16,
    SUNSPEC_NI_UINT16,
    SUNSPEC_STATE_MPPT,
    SUNSPEC_STATE_SLEEPING,
)
from custom_components.sunspec_emulator.sunspec_server import (
    SunSpecServer,
    _str_to_regs,
    _signed_to_uint16,
    _TOTAL_REGS,
    _HEADER_OFFSET,
    _COMMON_ID_OFFSET,
    _COMMON_LEN_OFFSET,
    _COMMON_DATA_OFFSET,
    _COMMON_LENGTH,
    _INV_ID_OFFSET,
    _INV_LEN_OFFSET,
    _INV_DATA_OFFSET,
    _INV_LENGTH,
    _INV_W,
    _INV_W_SF,
    _INV_St,
    _INV_Hz,
    _INV_Hz_SF,
    _INV_WH_HI,
    _INV_WH_LO,
    _MTR_ID_OFFSET,
    _MTR_LEN_OFFSET,
    _MTR_DATA_OFFSET,
    _MTR_LENGTH,
    _MTR_W,
    _MTR_W_SF,
    _END_OFFSET,
)


# --- Helper function tests ---


class TestStrToRegs:
    def test_short_string(self):
        regs = _str_to_regs("AB", 2)
        assert len(regs) == 2
        assert regs[0] == (ord("A") << 8) | ord("B")
        assert regs[1] == 0

    def test_exact_length(self):
        regs = _str_to_regs("ABCD", 2)
        assert regs[0] == (ord("A") << 8) | ord("B")
        assert regs[1] == (ord("C") << 8) | ord("D")

    def test_truncated_string(self):
        regs = _str_to_regs("ABCDEF", 2)
        assert len(regs) == 2

    def test_empty_string(self):
        assert _str_to_regs("", 4) == [0, 0, 0, 0]

    def test_register_count(self):
        for n in (1, 4, 8, 16):
            assert len(_str_to_regs("test", n)) == n


class TestSignedToUint16:
    def test_zero(self):
        assert _signed_to_uint16(0) == 0

    def test_positive(self):
        assert _signed_to_uint16(32767) == 32767

    def test_negative_one(self):
        assert _signed_to_uint16(-1) == 65535

    def test_negative_two(self):
        assert _signed_to_uint16(-2) == 65534

    def test_min_int16(self):
        assert _signed_to_uint16(-32768) == 32768


# --- Register layout tests ---


class TestRegisterLayout:
    @pytest.fixture
    def server(self):
        return SunSpecServer(port=1502, unit_id=1, manufacturer="TestMfg", model_name="TestModel")

    @pytest.fixture
    def regs(self, server):
        block = server._build_register_block()
        all_vals = block.getValues(SUNSPEC_BASE_ADDR - 1, _TOTAL_REGS + 2)
        return all_vals[2:]  # skip padding

    def test_sunspec_header(self, regs):
        assert regs[_HEADER_OFFSET] == 0x5375
        assert regs[_HEADER_OFFSET + 1] == 0x6E53

    def test_common_model_id(self, regs):
        assert regs[_COMMON_ID_OFFSET] == SUNSPEC_MODEL_COMMON

    def test_common_model_length(self, regs):
        assert regs[_COMMON_LEN_OFFSET] == _COMMON_LENGTH

    def test_manufacturer_encoded(self, regs):
        mn_regs = regs[_COMMON_DATA_OFFSET : _COMMON_DATA_OFFSET + 16]
        raw = b"".join(struct.pack(">H", r) for r in mn_regs)
        assert raw.rstrip(b"\x00").decode("utf-8") == "TestMfg"

    def test_model_name_encoded(self, regs):
        md_regs = regs[_COMMON_DATA_OFFSET + 16 : _COMMON_DATA_OFFSET + 32]
        raw = b"".join(struct.pack(">H", r) for r in md_regs)
        assert raw.rstrip(b"\x00").decode("utf-8") == "TestModel"

    def test_inverter_model_id(self, regs):
        assert regs[_INV_ID_OFFSET] == SUNSPEC_MODEL_INVERTER_3P

    def test_inverter_model_length(self, regs):
        assert regs[_INV_LEN_OFFSET] == _INV_LENGTH

    def test_initial_power_zero(self, regs):
        assert regs[_INV_DATA_OFFSET + _INV_W] == 0

    def test_frequency_50hz(self, regs):
        assert regs[_INV_DATA_OFFSET + _INV_Hz] == 500
        assert regs[_INV_DATA_OFFSET + _INV_Hz_SF] == _signed_to_uint16(-1)

    def test_initial_state_sleeping(self, regs):
        assert regs[_INV_DATA_OFFSET + _INV_St] == SUNSPEC_STATE_SLEEPING

    # Meter model tests
    def test_meter_model_id(self, regs):
        assert regs[_MTR_ID_OFFSET] == SUNSPEC_MODEL_METER_3P

    def test_meter_model_length(self, regs):
        assert regs[_MTR_LEN_OFFSET] == _MTR_LENGTH

    def test_meter_initial_power_zero(self, regs):
        assert regs[_MTR_DATA_OFFSET + _MTR_W] == 0

    def test_meter_power_sf_zero(self, regs):
        assert regs[_MTR_DATA_OFFSET + _MTR_W_SF] == _signed_to_uint16(0)

    def test_end_marker(self, regs):
        assert regs[_END_OFFSET] == SUNSPEC_END_MARKER
        assert regs[_END_OFFSET + 1] == 0

    def test_total_register_count(self, regs):
        assert len(regs) == _TOTAL_REGS

    def test_model_chain_contiguous(self, regs):
        """Models are properly chained: header → common → inverter → meter → end."""
        # Common
        assert regs[2] == 1
        common_len = regs[3]
        # Inverter
        inv_start = 2 + 2 + common_len
        assert regs[inv_start] == 103
        inv_len = regs[inv_start + 1]
        # Meter
        mtr_start = inv_start + 2 + inv_len
        assert regs[mtr_start] == 203
        mtr_len = regs[mtr_start + 1]
        # End
        end_start = mtr_start + 2 + mtr_len
        assert regs[end_start] == 0xFFFF


# --- Server operation tests ---


class TestServerOperations:
    @pytest.fixture
    def server(self):
        return SunSpecServer(port=1502, unit_id=1)

    def test_initial_state(self, server):
        assert not server.is_running

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_start(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        assert server.is_running

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_stop(self, mock_cls, server):
        inst = MagicMock(serve_forever=AsyncMock(), shutdown=AsyncMock())
        mock_cls.return_value = inst
        await server.start()
        await server.stop()
        assert not server.is_running
        inst.shutdown.assert_called_once()

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_double_start_ignored(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        await server.start()
        assert mock_cls.call_count == 1

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_update_power_positive(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        server.update_power(1500.0)
        store = server._context[1]
        val = store.getValues(3, SUNSPEC_BASE_ADDR + _INV_DATA_OFFSET + _INV_W, 1)
        assert val[0] == 1500
        state = store.getValues(3, SUNSPEC_BASE_ADDR + _INV_DATA_OFFSET + _INV_St, 1)
        assert state[0] == SUNSPEC_STATE_MPPT

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_update_power_zero(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        server.update_power(0.0)
        store = server._context[1]
        state = store.getValues(3, SUNSPEC_BASE_ADDR + _INV_DATA_OFFSET + _INV_St, 1)
        assert state[0] == SUNSPEC_STATE_SLEEPING

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_update_power_negative_clamped(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        server.update_power(-500.0)
        store = server._context[1]
        val = store.getValues(3, SUNSPEC_BASE_ADDR + _INV_DATA_OFFSET + _INV_W, 1)
        assert val[0] == 0

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_update_power_rounds(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        server.update_power(1234.7)
        store = server._context[1]
        val = store.getValues(3, SUNSPEC_BASE_ADDR + _INV_DATA_OFFSET + _INV_W, 1)
        assert val[0] == 1235

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_update_meter_power_positive(self, mock_cls, server):
        """Meter reports positive grid power (import)."""
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        server.update_meter_power(800.0)
        store = server._context[1]
        val = store.getValues(3, SUNSPEC_BASE_ADDR + _MTR_DATA_OFFSET + _MTR_W, 1)
        assert val[0] == _signed_to_uint16(800)

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_update_meter_power_negative(self, mock_cls, server):
        """Meter reports negative grid power (export)."""
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        server.update_meter_power(-500.0)
        store = server._context[1]
        val = store.getValues(3, SUNSPEC_BASE_ADDR + _MTR_DATA_OFFSET + _MTR_W, 1)
        assert val[0] == _signed_to_uint16(-500)

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_update_cumulative_energy(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        server.update_cumulative_energy(70000)
        store = server._context[1]
        vals = store.getValues(3, SUNSPEC_BASE_ADDR + _INV_DATA_OFFSET + _INV_WH_HI, 2)
        assert (vals[0] << 16) | vals[1] == 70000

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_update_cumulative_energy_large(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        server.update_cumulative_energy(100000)
        store = server._context[1]
        vals = store.getValues(3, SUNSPEC_BASE_ADDR + _INV_DATA_OFFSET + _INV_WH_HI, 2)
        assert vals[0] == 1
        assert vals[1] == 0x86A0

    def test_update_power_before_start(self, server):
        server.update_power(1000.0)  # no-op, no crash

    def test_update_meter_before_start(self, server):
        server.update_meter_power(500.0)  # no-op, no crash

    @patch("custom_components.sunspec_emulator.sunspec_server.ModbusTcpServer")
    async def test_server_bind_address(self, mock_cls, server):
        mock_cls.return_value = MagicMock(serve_forever=AsyncMock())
        await server.start()
        assert mock_cls.call_args.kwargs["address"] == ("0.0.0.0", 1502)
