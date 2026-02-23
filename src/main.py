"""Tapayoka Pi - BLE peripheral entry point."""

import signal
import sys

from .ble_peripheral import TapayokaPeripheral
from .config import AppConfig
from .eth_wallet import EthWallet
from .led_service import LEDService


def main() -> None:
    print("=" * 60)
    print("Tapayoka Pi - BLE Peripheral")
    print("=" * 60)

    config = AppConfig()
    wallet = EthWallet()
    led = LEDService(pin=config.gpio_pin)

    server_wallet = config.load_server_wallet()
    if server_wallet:
        print(f"[Config] Server wallet: {server_wallet[:10]}...")
    else:
        print("[Config] No server wallet configured (awaiting setup via BLE)")

    ble = TapayokaPeripheral(wallet, led, config)

    def shutdown(sig: int, frame: object) -> None:
        print("\nShutting down...")
        ble.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    ble.start()


if __name__ == "__main__":
    main()
