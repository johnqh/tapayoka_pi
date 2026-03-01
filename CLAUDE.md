# tapayoka_pi

BLE GATT peripheral firmware for Raspberry Pi. Generates ETH keypair on first boot, advertises wallet address in BLE name, handles signed commands, controls GPIO relay.

## Package: tapayoka-pi (Python, not published to npm)

## Architecture

- **BLE**: bluezero library, GATT server with 3 characteristics (device_info, command, response)
- **WebSocket**: Alternative transport for local dev without BLE hardware (`TRANSPORT=ws`)
- **Crypto**: eth-account for signing challenges and verifying server signatures
- **GPIO**: RPi.GPIO for relay control with auto-deactivation timer
- **Config**: Environment vars + file-based wallet storage in ~/.tapayoka/

## Commands

```bash
# On Raspberry Pi (BLE + GPIO)
pip install -e ".[dev,ble,gpio]"
python -m src.main

# Local dev on Mac/Linux (WebSocket, no BLE/GPIO needed)
pip install -e ".[dev,ws]"
TRANSPORT=ws python -m src.main    # starts WebSocket server on ws://0.0.0.0:8765

# Tests & linting
pytest tests/ -v
ruff check src/ tests/
mypy src/ --ignore-missing-imports
docker compose up --build
```

## Transport Modes

Set via `TRANSPORT` env var (default: `ble`).

| Mode | Class | Dependency | Use case |
|------|-------|------------|----------|
| `ble` | `TapayokaPeripheral` | bluezero | Production on Raspberry Pi |
| `ws` | `TapayokaWsPeripheral` | websockets | Local dev/testing without BLE hardware |

Both transports use the same constructor `(wallet, led, config)` and `start()`/`stop()` lifecycle. The WebSocket transport mirrors BLE semantics:

- BLE advertising → `announce` message sent on client connect
- BLE read (device_info char) → client sends `{"type": "read_device_info"}`, server replies with `{"type": "device_info", "data": {...}}`
- BLE write (command char) → client sends `{"type": "command", "data": {"command": "...", ...}}`, server replies with `{"type": "response", "data": {...}}`
- BLE disconnect → WebSocket close triggers safety LED deactivation

## BLE Protocol

- Service UUID: 000088F4-0000-1000-8000-00805f9b34fb
- Device name: tapayoka-{wallet_address_prefix}
- Commands: SETUP_SERVER, AUTHORIZE, ON, OFF, STATUS
