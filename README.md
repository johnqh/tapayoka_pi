# tapayoka_pi

BLE GATT peripheral firmware for Raspberry Pi. Generates ETH keypair on first boot, advertises wallet address in BLE name, handles signed commands, and controls GPIO relay.

## Setup

```bash
# On Raspberry Pi (production: BLE + GPIO)
pip install -e ".[dev,ble,gpio]"
python -m src.main

# Local dev on Mac/Linux (WebSocket, no BLE/GPIO needed)
pip install -e ".[dev,ws]"
TRANSPORT=ws python -m src.main    # starts WebSocket server on ws://0.0.0.0:8765
```

## Architecture

- **BLE**: bluezero library, GATT server with 3 characteristics (device_info, command, response)
- **WebSocket**: Alternative transport for local dev without BLE hardware
- **Crypto**: eth-account for signing challenges and verifying server signatures
- **GPIO**: RPi.GPIO for relay control with auto-deactivation timer
- **Config**: Environment vars + file-based wallet storage in `~/.tapayoka/`

## BLE Protocol

- Service UUID: `000088F4-0000-1000-8000-00805f9b34fb`
- Device name: `tapayoka-{wallet_address_prefix}`
- Commands: `SETUP_SERVER`, `AUTHORIZE`, `ON`, `OFF`, `STATUS`

## Transport Modes

| Mode | Class | Dependency | Use case |
|------|-------|------------|----------|
| `ble` | `TapayokaPeripheral` | bluezero | Production on Raspberry Pi |
| `ws` | `TapayokaWsPeripheral` | websockets | Local dev/testing |

## Development

```bash
pytest tests/ -v                   # Run tests
ruff check src/ tests/             # Linting
mypy src/ --ignore-missing-imports # Type checking
docker compose up --build          # Docker deployment
```

## Related Packages

- `tapayoka_pi_pico` -- MicroPython variant for Pico W
- `tapayoka_api` -- Backend API server
- `tapayoka_buyer_app_rn` -- Buyer app that communicates via BLE
- `tapayoka_vendor_app_rn` -- Vendor app for device setup via BLE

## License

BUSL-1.1
