"""Tests for ETH wallet functionality."""

import json
from unittest.mock import patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from src.eth_wallet import EthWallet


@pytest.fixture
def temp_wallet_dir(tmp_path):
    with (
        patch("src.eth_wallet.WALLET_DIR", str(tmp_path)),
        patch("src.eth_wallet.WALLET_KEY_FILE", str(tmp_path / "device_key.json")),
    ):
        yield tmp_path


def test_wallet_creates_new_keypair(temp_wallet_dir):
    wallet = EthWallet()
    assert wallet.address.startswith("0x")
    assert len(wallet.address) == 42


def test_wallet_loads_existing_keypair(temp_wallet_dir):
    wallet1 = EthWallet()
    addr1 = wallet1.address
    wallet2 = EthWallet()
    assert wallet2.address == addr1


def test_sign_challenge(temp_wallet_dir):
    wallet = EthWallet()
    challenge = wallet.sign_challenge()
    assert "walletAddress" in challenge
    assert "timestamp" in challenge
    assert "nonce" in challenge
    assert "signature" in challenge
    assert "signedPayload" in challenge


def test_verify_server_signature(temp_wallet_dir):
    wallet = EthWallet()
    server = Account.create()
    payload = json.dumps({"orderId": "test-123", "seconds": 60})
    signed = server.sign_message(encode_defunct(text=payload))
    assert wallet.verify_server_signature(payload, signed.signature.hex(), server.address)


def test_verify_server_signature_wrong_address(temp_wallet_dir):
    wallet = EthWallet()
    server = Account.create()
    payload = json.dumps({"orderId": "test-123"})
    signed = server.sign_message(encode_defunct(text=payload))
    wrong_server = Account.create()
    assert not wallet.verify_server_signature(
        payload, signed.signature.hex(), wrong_server.address
    )
