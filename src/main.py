"""Tapayoka Pi - peripheral entry point."""

import os
import signal
import sys

from .config import AppConfig
from .eth_wallet import EthWallet
from .kiosk_server import start_kiosk_server
from .kiosk_state import generate_deep_link, update_kiosk_state
from .led_service import LEDService


def main() -> None:
    transport = os.getenv("TRANSPORT", "ble").lower()

    print("=" * 60)
    print(f"Tapayoka Pi - {transport.upper()} Peripheral")
    print("=" * 60)

    config = AppConfig()
    wallet = EthWallet()
    led = LEDService(pin=config.gpio_pin)

    # Start kiosk HTTP server (background thread)
    device_name = f"tapayoka-{wallet.address_short}"
    start_kiosk_server(state_dir=config.kiosk_state_dir, port=config.kiosk_port)

    deep_link = generate_deep_link(
        transport=transport,
        wallet_address=wallet.address,
        device_name=device_name,
        state_dir=config.kiosk_state_dir,
    )
    state_file = os.path.join(config.kiosk_state_dir, "state.json")
    update_kiosk_state(state_file, status="QR", qr_url=deep_link, message="Scan to connect")
    print(f"[Kiosk] QR deep link: {deep_link}")

    server_wallet = config.load_server_wallet()
    if server_wallet:
        print(f"[Config] Server wallet: {server_wallet[:10]}...")
    else:
        print(f"[Config] No server wallet configured (awaiting setup via {transport.upper()})")

    if transport == "ws":
        from .ws_peripheral import TapayokaWsPeripheral

        peripheral = TapayokaWsPeripheral(wallet, led, config)
    else:
        from .ble_peripheral import TapayokaPeripheral

        peripheral = TapayokaPeripheral(wallet, led, config)

    def shutdown(sig: int, frame: object) -> None:
        print("\nShutting down...")
        peripheral.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    peripheral.start()


if __name__ == "__main__":
    main()
