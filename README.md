# SunSpec Emulator for Home Assistant

A Home Assistant custom integration that emulates a **SunSpec-compatible PV inverter and energy meter** via Modbus TCP. This allows heat pumps with SunSpec/PV-Smart support (e.g. **Nibe S320**, S1155, S1255) to receive PV production and grid power data from **any sensor** in Home Assistant.

## Use Case

You have a small PV system (e.g. a balcony power plant / Balkonkraftwerk) whose inverter doesn't support SunSpec — but your heat pump requires a SunSpec-compatible inverter to enable PV surplus heating. This integration bridges that gap by:

1. Reading **PV production** from any HA sensor (e.g. Hoymiles inverter via hoymiles_wifi)
2. Reading **grid power** from any HA sensor (e.g. Shelly Pro 3EM)
3. Emulating a SunSpec inverter (Model 103) + meter (Model 203) on Modbus TCP
4. Your heat pump connects and sees a fully compliant SunSpec device

```
┌─────────────┐     ┌───────────────────┐     ┌──────────────┐
│  Hoymiles   │────▶│                   │     │              │
│  (PV power) │     │  Home Assistant    │────▶│  Nibe S320   │
│             │     │  SunSpec Emulator  │     │  (PV-Smart)  │
│  Shelly 3EM │────▶│  Modbus TCP :502   │     │              │
│ (grid power)│     │                   │     │              │
└─────────────┘     └───────────────────┘     └──────────────┘
```

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu, then **Custom repositories**
3. Add this repository URL, category: **Integration**
4. Search for "SunSpec Emulator" and install
5. Restart Home Assistant

### Manual

1. Copy `custom_components/sunspec_emulator/` to your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **SunSpec Emulator**
3. Configure:

| Setting | Description | Default |
|---------|-------------|---------|
| **Grid Power Entity** | Sensor reporting grid power in Watts (positive = import, negative = export) | *(required)* |
| **PV Power Entity** | Sensor reporting PV production in Watts (positive = generating) | *(required)* |
| **Modbus TCP Port** | Port the virtual SunSpec device listens on | 502 |
| **Modbus Unit ID** | Modbus slave address | 1 |
| **Update Interval** | How often registers are updated (seconds) | 5 |
| **Manufacturer / Model** | Cosmetic fields in SunSpec Common block | HA SunSpec Emulator |

## Heat Pump Setup (Nibe S-Series)

1. Go to menu **7.5.12** (PV / Inverter settings)
2. Enter the **IP address** of your Home Assistant instance
3. Set the **port** to match your configuration (default: 502)
4. The heat pump should show "Intelligenter Inverter angeschlossen" (intelligent inverter connected)
5. **Important:** In menu **4.2.2**, select **"Intel. Zaehler"** (intelligent meter) as the energy meter — otherwise grid power and household consumption will not appear in the energy flow diagram

After this, the Nibe energy flow diagram should show all three values: solar power, grid power, and household consumption.

## SunSpec Protocol Details

The emulator implements the full SunSpec model chain starting at base address **40000**:

| Model | ID | Description | Key Registers |
|-------|-----|-------------|--------------|
| Header | — | "SunS" magic bytes for auto-discovery | 40000-40001 |
| Common (Model 1) | 1 | Device identification (manufacturer, model, serial) | 40002-40069 |
| Inverter (Model 103) | 103 | Three-phase inverter — AC power, frequency, state | 40070-40121 |
| Meter (Model 203) | 203 | Three-phase wye meter — grid power, voltages, energy | 40122-40228 |
| End Marker | 0xFFFF | Signals end of model chain | 40229-40230 |

Key registers:
- **PV Power (W)**: Register 40084 (Model 103, offset 12) — PV production as reported to the heat pump
- **Grid Power (W)**: Register 40140 (Model 203, offset 16) — signed int16, positive = import, negative = export

## Entities

The integration creates two sensor entities:

| Entity | Description |
|--------|-------------|
| **Reported PV Power** | PV power currently being reported via SunSpec (W) |
| **Reported Grid Power** | Grid power currently being reported via SunSpec (W) |

Both sensors include attributes for source entity, server status, and unit of measurement.

## Troubleshooting

### Port 502 requires root privileges
On Linux/HAOS, Home Assistant typically runs with sufficient privileges. If not, use a higher port (e.g. 1502) and configure port forwarding.

### Heat pump shows "Intelligenter Inverter angeschlossen" but no grid data
Go to Nibe menu **4.2.2** and select **"Intel. Zaehler"** as the energy meter source. Without this setting, the heat pump ignores the SunSpec meter model.

### Heat pump doesn't connect
- Verify the HA host IP is reachable from the heat pump's network
- Check firewall rules (the configured port must be open)
- Confirm the Modbus Unit ID matches (default: 1)
- Some heat pumps require a firmware update for PV-Smart support

### Values not updating
- Check that both source sensor entities are available and reporting numeric values
- The integration gracefully handles unavailable entities (reports 0)

## Tested With

- **Heat Pump**: Nibe VVM S320
- **PV Inverter**: Hoymiles HM-800 (via hoymiles_wifi integration)
- **Grid Meter**: Shelly Pro 3EM
- **Home Assistant**: 2024.x on HAOS
- **pymodbus**: 3.12.x

## License

MIT License — see [LICENSE](LICENSE) for details.
