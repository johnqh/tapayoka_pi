"""WebSocket transport for Tapayoka device (local development)."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from .config import BLE_DEVICE_NAME_PREFIX, AppConfig
from .eth_wallet import EthWallet
from .kiosk_state import update_kiosk_state
from .led_service import LEDService


class TapayokaWsPeripheral:
    """WebSocket server that mirrors BLE peripheral semantics."""

    def __init__(self, wallet: EthWallet, led: LEDService, config: AppConfig) -> None:
        self._wallet = wallet
        self._led = led
        self._config = config
        self._server: Any = None

    @property
    def device_name(self) -> str:
        return f"{BLE_DEVICE_NAME_PREFIX}{self._wallet.address_short}"

    # ---------- handlers ----------

    def _build_device_info(self) -> dict[str, Any]:
        """Build device info response (mirrors _on_device_info_read)."""
        challenge = self._wallet.sign_challenge()
        server_wallet = self._config.load_server_wallet()
        info = {
            **challenge,
            "firmwareVersion": "0.1.0",
            "hasServerWallet": bool(server_wallet),
        }
        info["signing"] = self._wallet.sign_response(info)
        return info

    def _handle_command(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process a command and return response dict (mirrors _on_command_write)."""
        command = data.get("command", "").upper()
        print(f"[WS] Command received: {command}")

        if command == "SETUP_SERVER":
            return self._handle_setup_server(data)
        elif command == "AUTHORIZE":
            return self._handle_authorize(data)
        elif command == "ON":
            self._led.activate(duration_seconds=data.get("seconds", 0))
            return {"status": "OK", "message": "Activated"}
        elif command == "OFF":
            self._led.deactivate()
            return {"status": "OK", "message": "Deactivated"}
        elif command == "STATUS":
            status_data = {
                "active": self._led.is_active,
                "walletAddress": self._wallet.address,
                "hasServerWallet": bool(self._config.load_server_wallet()),
            }
            return {"status": "OK", "data": json.dumps(status_data)}
        else:
            return {"status": "ERROR", "message": f"Unknown command: {command}"}

    def _handle_setup_server(self, data: dict[str, Any]) -> dict[str, Any]:
        address = data.get("payload", "")
        if not address or not address.startswith("0x"):
            return {"status": "ERROR", "message": "Invalid server wallet address"}
        self._config.save_server_wallet(address)
        print(f"[WS] Server wallet set: {address[:10]}...")
        return {"status": "OK", "message": "Server wallet configured"}

    def _handle_authorize(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = data.get("payload", "")
        signature = data.get("signature", "")
        server_wallet = self._config.load_server_wallet()

        if not server_wallet:
            return {"status": "ERROR", "message": "No server wallet configured"}
        if not self._wallet.verify_server_signature(payload, signature, server_wallet):
            return {"status": "UNAUTHORIZED", "message": "Invalid server signature"}

        try:
            auth = json.loads(payload)
            seconds = auth.get("seconds", 0)
            service_type = auth.get("serviceType", "TRIGGER")
            if service_type == "TRIGGER":
                self._led.activate(duration_seconds=1)
            else:
                self._led.activate(duration_seconds=seconds)
            print(f"[WS] Authorized: {service_type} for {seconds}s")
            return {"status": "OK", "message": f"Activated for {seconds}s"}
        except (json.JSONDecodeError, KeyError) as e:
            return {"status": "ERROR", "message": f"Invalid payload: {e}"}

    # ---------- WebSocket connection handler ----------

    async def _handle_connection(self, ws: Any) -> None:
        from websockets.exceptions import ConnectionClosed

        remote = ws.remote_address
        print(f"[WS] Client connected: {remote}")
        state_file = os.path.join(self._config.kiosk_state_dir, "state.json")
        update_kiosk_state(state_file, status="CONNECTED", message="Connected")

        # Send announce (replaces BLE advertising/discovery)
        await ws.send(json.dumps({
            "type": "announce",
            "data": {
                "deviceName": self.device_name,
                "walletAddress": self._wallet.address,
            },
        }))

        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    msg_type = msg.get("type", "")

                    if msg_type == "read_device_info":
                        info = self._build_device_info()
                        await ws.send(json.dumps({"type": "device_info", "data": info}))

                    elif msg_type == "command":
                        result = self._handle_command(msg.get("data", {}))
                        await ws.send(json.dumps({"type": "response", "data": result}))

                    else:
                        await ws.send(json.dumps({
                            "type": "response",
                            "data": {"status": "ERROR", "message": f"Unknown type: {msg_type}"},
                        }))

                except json.JSONDecodeError as e:
                    await ws.send(json.dumps({
                        "type": "response",
                        "data": {"status": "ERROR", "message": str(e)},
                    }))

        except ConnectionClosed:
            pass
        finally:
            print(f"[WS] Client disconnected: {remote}")
            update_kiosk_state(state_file, status="QR", message="Scan to connect")
            if self._led.is_active:
                print("[WS] Safety deactivation on disconnect")
                self._led.deactivate()

    # ---------- lifecycle ----------

    def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """Start the WebSocket server (blocking)."""
        print(f"[WS] Starting WebSocket peripheral on ws://{host}:{port}")
        asyncio.run(self._serve(host, port))

    async def _serve(self, host: str, port: int) -> None:
        import websockets

        async with websockets.serve(self._handle_connection, host, port) as server:
            self._server = server
            print(f"[WS] Peripheral published: {self.device_name}")
            await asyncio.Future()  # run forever

    def stop(self) -> None:
        self._led.cleanup()
        print("[WS] Peripheral stopped")
