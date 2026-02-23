# tapayoka_pi

BLE GATT peripheral firmware for Raspberry Pi. Generates ETH keypair on first boot, advertises wallet address in BLE name, handles signed commands, controls GPIO relay.

## Package: tapayoka-pi (Python, not published to npm)

## Architecture

- **BLE**: bluezero library, GATT server with 3 characteristics (device_info, command, response)
- **Crypto**: eth-account for signing challenges and verifying server signatures
- **GPIO**: RPi.GPIO for relay control with auto-deactivation timer
- **Config**: Environment vars + file-based wallet storage in ~/.tapayoka/

## Commands

```bash
pip install -e ".[dev,gpio]"
python -m src.main
pytest tests/ -v
ruff check src/ tests/
mypy src/ --ignore-missing-imports
docker compose up --build
```

## BLE Protocol

- Service UUID: 000088F4-0000-1000-8000-00805f9b34fb
- Device name: tapayoka-{wallet_address_prefix}
- Commands: SETUP_SERVER, AUTHORIZE, ON, OFF, STATUS
