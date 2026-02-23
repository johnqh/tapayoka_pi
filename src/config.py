"""Configuration management for Tapayoka Pi."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

# BLE UUIDs (must match tapayoka_types)
BLE_SERVICE_UUID = "000088F4-0000-1000-8000-00805f9b34fb"
BLE_CHAR_DEVICE_INFO_UUID = "00000E32-0000-1000-8000-00805f9b34fb"
BLE_CHAR_COMMAND_UUID = "00000E33-0000-1000-8000-00805f9b34fb"
BLE_CHAR_RESPONSE_UUID = "00000E34-0000-1000-8000-00805f9b34fb"
BLE_DEVICE_NAME_PREFIX = "tapayoka-"

# Paths
WALLET_DIR = os.path.expanduser("~/.tapayoka")
WALLET_KEY_FILE = os.path.join(WALLET_DIR, "device_key.json")
SERVER_WALLET_FILE = os.path.join(WALLET_DIR, "server_wallet.txt")


@dataclass
class AppConfig:
    """Application configuration loaded from environment."""

    server_wallet_address: str = field(
        default_factory=lambda: os.getenv("SERVER_WALLET_ADDRESS", "")
    )
    gpio_pin: int = field(default_factory=lambda: int(os.getenv("GPIO_PIN", "17")))
    ble_adapter: str = field(default_factory=lambda: os.getenv("BLE_ADAPTER", ""))
    kiosk_state_file: str = field(
        default_factory=lambda: os.getenv("KIOSK_STATE_FILE", "/var/www/html/state.json")
    )

    def load_server_wallet(self) -> str:
        """Load server wallet address from file or env."""
        if self.server_wallet_address:
            return self.server_wallet_address
        try:
            with open(SERVER_WALLET_FILE) as f:
                addr = f.read().strip()
                if addr:
                    self.server_wallet_address = addr
                    return addr
        except FileNotFoundError:
            pass
        return ""

    def save_server_wallet(self, address: str) -> None:
        """Save server wallet address to file."""
        os.makedirs(WALLET_DIR, exist_ok=True)
        with open(SERVER_WALLET_FILE, "w") as f:
            f.write(address)
        self.server_wallet_address = address
