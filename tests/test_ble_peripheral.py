"""Tests for BLE peripheral command handling."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ble_peripheral import TapayokaPeripheral
from src.config import AppConfig
from src.eth_wallet import EthWallet
from src.led_service import LEDService


@pytest.fixture
def temp_wallet_dir(tmp_path):
    with (
        patch("src.eth_wallet.WALLET_DIR", str(tmp_path)),
        patch("src.eth_wallet.WALLET_KEY_FILE", str(tmp_path / "device_key.json")),
    ):
        yield tmp_path


@pytest.fixture
def peripheral(temp_wallet_dir, tmp_path):
    wallet = EthWallet()
    led = LEDService(pin=17)
    config = AppConfig(
        gpio_pin=17,
        ble_adapter=None,
        data_dir=str(tmp_path),
    )
    return TapayokaPeripheral(wallet, led, config)


class TestOnDeviceInfoRead:
    def test_returns_json_bytes_list(self, peripheral):
        result = peripheral._on_device_info_read({})
        data = json.loads(bytes(result).decode("utf-8"))
        assert "walletAddress" in data
        assert "firmwareVersion" in data
        assert "hasServerWallet" in data
        assert data["firmwareVersion"] == "0.1.0"

    def test_includes_signed_challenge(self, peripheral):
        result = peripheral._on_device_info_read({})
        data = json.loads(bytes(result).decode("utf-8"))
        assert "signature" in data
        assert "signedPayload" in data
        assert "nonce" in data
        assert "timestamp" in data


class TestOnCommandWrite:
    def _make_command(self, command, **kwargs):
        payload = {"command": command, **kwargs}
        return list(json.dumps(payload).encode("utf-8"))

    def test_on_command(self, peripheral):
        peripheral._send_response = MagicMock()
        peripheral._on_command_write(self._make_command("ON"), {})
        peripheral._send_response.assert_called_with("OK", "Activated")

    def test_off_command(self, peripheral):
        peripheral._send_response = MagicMock()
        peripheral._led.activate()
        peripheral._on_command_write(self._make_command("OFF"), {})
        peripheral._send_response.assert_called_with("OK", "Deactivated")
        assert not peripheral._led.is_active

    def test_status_command(self, peripheral):
        peripheral._send_response = MagicMock()
        peripheral._on_command_write(self._make_command("STATUS"), {})
        call_args = peripheral._send_response.call_args
        assert call_args[0][0] == "OK"
        assert "data" in call_args[1] or len(call_args[0]) > 1

    def test_unknown_command(self, peripheral):
        peripheral._send_response = MagicMock()
        peripheral._on_command_write(self._make_command("BOGUS"), {})
        peripheral._send_response.assert_called_with("ERROR", "Unknown command: BOGUS")

    def test_invalid_json(self, peripheral):
        peripheral._send_response = MagicMock()
        peripheral._on_command_write(list(b"not json"), {})
        assert peripheral._send_response.called
        assert peripheral._send_response.call_args[0][0] == "ERROR"

    def test_setup_server_valid(self, peripheral):
        peripheral._send_response = MagicMock()
        cmd = self._make_command("SETUP_SERVER", payload="0x742d35Cc6634C0532925a3b844Bc9e7595f2bD08")
        peripheral._on_command_write(cmd, {})
        peripheral._send_response.assert_called_with("OK", "Server wallet configured")

    def test_setup_server_invalid(self, peripheral):
        peripheral._send_response = MagicMock()
        cmd = self._make_command("SETUP_SERVER", payload="bad-address")
        peripheral._on_command_write(cmd, {})
        peripheral._send_response.assert_called_with("ERROR", "Invalid server wallet address")

    def test_authorize_without_server_wallet(self, peripheral):
        peripheral._send_response = MagicMock()
        cmd = self._make_command("AUTHORIZE", payload="{}", signature="0xabc")
        peripheral._on_command_write(cmd, {})
        peripheral._send_response.assert_called_with("ERROR", "No server wallet configured")


class TestOnDisconnect:
    def test_deactivates_led_on_disconnect(self, peripheral):
        peripheral._led.activate()
        assert peripheral._led.is_active
        peripheral._on_disconnect("adapter", "device")
        assert not peripheral._led.is_active

    def test_no_error_when_led_inactive_on_disconnect(self, peripheral):
        peripheral._on_disconnect("adapter", "device")
        assert not peripheral._led.is_active
