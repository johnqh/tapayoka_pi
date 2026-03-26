"""Tests for BLE peripheral command handling."""

import json
from unittest.mock import MagicMock, patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from src.ble_peripheral import TapayokaPeripheral
from src.config import AppConfig
from src.eth_wallet import EthWallet
from src.led_service import LEDService


def _make_signed_setup_server_command(server_account):
    """Build a SETUP_SERVER command with valid data + signing from a server account."""
    data = {"walletAddress": server_account.address}
    message = json.dumps(data)
    signed = server_account.sign_message(encode_defunct(text=message))
    signing = {
        "walletAddress": server_account.address,
        "message": message,
        "signature": "0x" + signed.signature.hex(),
    }
    payload = {"command": "SETUP_SERVER", "data": data, "signing": signing}
    return list(json.dumps(payload).encode("utf-8"))


@pytest.fixture
def temp_wallet_dir(tmp_path):
    with (
        patch("src.eth_wallet.WALLET_DIR", str(tmp_path)),
        patch("src.eth_wallet.WALLET_KEY_FILE", str(tmp_path / "device_key.json")),
        patch("src.config.WALLET_DIR", str(tmp_path)),
        patch("src.config.SERVER_WALLET_FILE", str(tmp_path / "server_wallet.txt")),
    ):
        yield tmp_path


@pytest.fixture
def peripheral(temp_wallet_dir, tmp_path):
    wallet = EthWallet()
    led = LEDService(pin=17)
    config = AppConfig(
        gpio_pin=17,
        ble_adapter="",
    )
    return TapayokaPeripheral(wallet, led, config)


class TestOnDeviceInfoRead:
    def test_returns_envelope_with_data_and_signing(self, peripheral):
        result = peripheral._on_device_info_read({})
        envelope = json.loads(bytes(result).decode("utf-8"))
        assert "data" in envelope
        assert "signing" in envelope
        data = envelope["data"]
        assert "walletAddress" in data
        assert "firmwareVersion" in data
        assert "hasServerWallet" in data
        assert "timestamp" in data
        assert "nonce" in data
        assert data["firmwareVersion"] == "0.1.0"

    def test_signing_is_valid_eth_signed_message(self, peripheral):
        result = peripheral._on_device_info_read({})
        envelope = json.loads(bytes(result).decode("utf-8"))
        signing = envelope["signing"]
        assert "walletAddress" in signing
        assert "message" in signing
        assert "signature" in signing
        assert signing["walletAddress"] == envelope["data"]["walletAddress"]


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
        server_account = Account.create()
        cmd = _make_signed_setup_server_command(server_account)
        peripheral._on_command_write(cmd, {})
        peripheral._send_response.assert_called_with("OK", "Server wallet configured")

    def test_setup_server_missing_signing(self, peripheral):
        peripheral._send_response = MagicMock()
        cmd = self._make_command("SETUP_SERVER", payload="bad-address")
        peripheral._on_command_write(cmd, {})
        peripheral._send_response.assert_called_with("ERROR", "Missing data or signing")

    def test_setup_server_invalid_signature(self, peripheral):
        peripheral._send_response = MagicMock()
        data = {"walletAddress": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD08"}
        signing = {
            "walletAddress": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD08",
            "message": json.dumps(data),
            "signature": "0x" + "00" * 65,
        }
        cmd_payload = {"command": "SETUP_SERVER", "data": data, "signing": signing}
        cmd = list(json.dumps(cmd_payload).encode("utf-8"))
        peripheral._on_command_write(cmd, {})
        peripheral._send_response.assert_called_with("UNAUTHORIZED", "Invalid server signature")

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
