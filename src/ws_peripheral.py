"""WebSocket transport for Tapayoka device (local development)."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from .config import BLE_DEVICE_NAME_PREFIX, AppConfig
from .eth_wallet import EthWallet, verify_signed_payload
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
        """Build device info as {data, signing} envelope (mirrors _on_device_info_read)."""
        import secrets as stdlib_secrets
        import time

        server_wallet = self._config.load_server_wallet()
        data = {
            "walletAddress": self._wallet.address,
            "firmwareVersion": "0.1.0",
            "hasServerWallet": bool(server_wallet),
            "timestamp": int(time.time()),
            "nonce": stdlib_secrets.token_hex(16),
        }
        signing = self._wallet.sign_response(data)
        return {"data": data, "signing": signing}

    def _handle_command(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process a command and return response dict (mirrors _on_command_write)."""
        command = data.get("command", "").upper()
        print(f"[WS] Command received: {command}")

        if command == "SETUP_SERVER":
            return self._handle_setup_server(data)
        elif command == "EXECUTE":
            return self._handle_execute(data)
        else:
            return {"status": "ERROR", "message": f"Unknown command: {command}"}

    def _handle_setup_server(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Verify signature and save server wallet address.

        msg format: { command, data, signing } — verify_signed_payload reads
        data/signing directly from the dict.
        """
        if not verify_signed_payload(msg):
            return {"status": "UNAUTHORIZED", "message": "Invalid server signature"}

        server_address = msg.get("signing", {}).get("walletAddress", "")
        if not server_address or not server_address.startswith("0x"):
            return {"status": "ERROR", "message": "Invalid server wallet address"}

        self._config.save_server_wallet(server_address)
        print(f"[WS] Server wallet set: {server_address[:10]}...")
        return {"status": "OK", "message": "Server wallet configured"}

    def _handle_execute(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Execute a server-signed command.

        msg format: { command, data, signing } — verifies the signer matches
        the stored server wallet, then activates the relay.
        """
        server_wallet = self._config.load_server_wallet()
        if not server_wallet:
            return {"status": "ERROR", "message": "No server wallet configured"}

        if not verify_signed_payload(msg, expected_signer=server_wallet):
            return {"status": "UNAUTHORIZED", "message": "Invalid server signature"}

        cmd = msg.get("data", {})
        seconds = cmd.get("seconds", 0)
        offering_type = cmd.get("offeringType", "TRIGGER")
        if offering_type == "TRIGGER":
            self._led.activate(duration_seconds=1)
        else:
            self._led.activate(duration_seconds=seconds)
        print(f"[WS] Execute: {offering_type} for {seconds}s")
        return {"status": "OK", "message": f"Activated for {seconds}s"}

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
