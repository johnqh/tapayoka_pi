"""Tapayoka Pi - peripheral entry point."""

import os
import signal
import sys

from .config import AppConfig
from .eth_wallet import EthWallet
from .led_service import LEDService


def main() -> None:
    transport = os.getenv("TRANSPORT", "ble").lower()

    print("=" * 60)
    print(f"Tapayoka Pi - {transport.upper()} Peripheral")
    print("=" * 60)

    config = AppConfig()
    wallet = EthWallet()
    led = LEDService(pin=config.gpio_pin)

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
