"""BLE GATT peripheral for Tapayoka device."""

import json

from bluezero import adapter, peripheral

from .config import (
    BLE_CHAR_COMMAND_UUID,
    BLE_CHAR_DEVICE_INFO_UUID,
    BLE_CHAR_RESPONSE_UUID,
    BLE_DEVICE_NAME_PREFIX,
    BLE_SERVICE_UUID,
    AppConfig,
)
from .eth_wallet import EthWallet
from .led_service import LEDService


class TapayokaPeripheral:
    """BLE GATT peripheral that handles commands and controls relay."""

    def __init__(self, wallet: EthWallet, led: LEDService, config: AppConfig) -> None:
        self._wallet = wallet
        self._led = led
        self._config = config
        self._peripheral: peripheral.Peripheral | None = None

    def _get_adapter_address(self) -> str:
        if self._config.ble_adapter:
            return self._config.ble_adapter
        adapters = list(adapter.Adapter.available())
        if not adapters:
            raise RuntimeError("No BLE adapters found")
        return adapters[0].address

    def _on_connect(self, ble_device: str) -> None:
        print(f"[BLE] Device connected: {ble_device}")

    def _on_disconnect(self, adapter_address: str, device_address: str) -> None:
        print(f"[BLE] Device disconnected: {device_address}")
        if self._led.is_active:
            print("[BLE] Safety deactivation on disconnect")
            self._led.deactivate()

    def _on_device_info_read(self, options: dict) -> list:
        """Return device info including signed challenge."""
        challenge = self._wallet.sign_challenge()
        server_wallet = self._config.load_server_wallet()
        info = {
            **challenge,
            "firmwareVersion": "0.1.0",
            "hasServerWallet": bool(server_wallet),
        }
        data = json.dumps(info).encode("utf-8")
        print(f"[BLE] Device info read: {self._wallet.address[:10]}...")
        return list(data)

    def _on_command_write(self, value: list, options: dict) -> None:
        """Handle incoming BLE commands."""
        try:
            data = json.loads(bytes(value).decode("utf-8"))
            command = data.get("command", "").upper()
            print(f"[BLE] Command received: {command}")

            if command == "SETUP_SERVER":
                self._handle_setup_server(data)
            elif command == "AUTHORIZE":
                self._handle_authorize(data)
            elif command == "ON":
                self._led.activate(duration_seconds=data.get("seconds", 0))
                self._send_response("OK", "Activated")
            elif command == "OFF":
                self._led.deactivate()
                self._send_response("OK", "Deactivated")
            elif command == "STATUS":
                status = {
                    "active": self._led.is_active,
                    "walletAddress": self._wallet.address,
                    "hasServerWallet": bool(self._config.load_server_wallet()),
                }
                self._send_response("OK", data=json.dumps(status))
            else:
                self._send_response("ERROR", f"Unknown command: {command}")

        except (json.JSONDecodeError, ValueError) as e:
            print(f"[BLE] Error parsing command: {e}")
            self._send_response("ERROR", str(e))

    def _handle_setup_server(self, data: dict) -> None:
        address = data.get("payload", "")
        if not address or not address.startswith("0x"):
            self._send_response("ERROR", "Invalid server wallet address")
            return
        self._config.save_server_wallet(address)
        print(f"[BLE] Server wallet set: {address[:10]}...")
        self._send_response("OK", "Server wallet configured")

    def _handle_authorize(self, data: dict) -> None:
        payload = data.get("payload", "")
        signature = data.get("signature", "")
        server_wallet = self._config.load_server_wallet()

        if not server_wallet:
            self._send_response("ERROR", "No server wallet configured")
            return
        if not self._wallet.verify_server_signature(payload, signature, server_wallet):
            self._send_response("UNAUTHORIZED", "Invalid server signature")
            return

        try:
            auth = json.loads(payload)
            seconds = auth.get("seconds", 0)
            service_type = auth.get("serviceType", "TRIGGER")
            if service_type == "TRIGGER":
                self._led.activate(duration_seconds=1)
            else:
                self._led.activate(duration_seconds=seconds)
            print(f"[BLE] Authorized: {service_type} for {seconds}s")
            self._send_response("OK", f"Activated for {seconds}s")
        except (json.JSONDecodeError, KeyError) as e:
            self._send_response("ERROR", f"Invalid payload: {e}")

    def _send_response(self, status: str, message: str = "", data: str = "") -> None:
        response = {"status": status}
        if message:
            response["message"] = message
        if data:
            response["data"] = data
        print(f"[BLE] Response: {status} - {message}")

    def start(self) -> None:
        """Start the BLE peripheral."""
        addr = self._get_adapter_address()
        device_name = f"{BLE_DEVICE_NAME_PREFIX}{self._wallet.address_short}"

        print(f"[BLE] Starting peripheral: {device_name}")
        self._peripheral = peripheral.Peripheral(addr, local_name=device_name)
        self._peripheral.on_connect = self._on_connect
        self._peripheral.on_disconnect = self._on_disconnect

        self._peripheral.add_service(srv_id=1, uuid=BLE_SERVICE_UUID, primary=True)
        self._peripheral.add_characteristic(
            srv_id=1, chr_id=1, uuid=BLE_CHAR_DEVICE_INFO_UUID,
            value=[], notifying=False, flags=["read"],
            read_callback=self._on_device_info_read,
        )
        self._peripheral.add_characteristic(
            srv_id=1, chr_id=2, uuid=BLE_CHAR_COMMAND_UUID,
            value=[], notifying=False, flags=["write"],
            write_callback=self._on_command_write,
        )
        self._peripheral.add_characteristic(
            srv_id=1, chr_id=3, uuid=BLE_CHAR_RESPONSE_UUID,
            value=[], notifying=False, flags=["notify"],
        )

        print("[BLE] Peripheral published, waiting for connections...")
        self._peripheral.publish()

    def stop(self) -> None:
        if self._peripheral:
            self._peripheral.mainloop.quit()
        self._led.cleanup()
        print("[BLE] Peripheral stopped")
