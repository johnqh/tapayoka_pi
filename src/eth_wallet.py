"""Ethereum wallet management for device identity and signature verification."""

import json
import os
import secrets as stdlib_secrets
import time

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount

from .config import WALLET_DIR, WALLET_KEY_FILE


class EthWallet:
    """Manages device Ethereum keypair for signing and verification."""

    def __init__(self) -> None:
        self._account = self._load_or_create()
        print(f"[Wallet] Device address: {self.address}")

    def _load_or_create(self) -> LocalAccount:
        """Load existing keypair or generate new one on first boot."""
        acct: LocalAccount
        if os.path.exists(WALLET_KEY_FILE):
            with open(WALLET_KEY_FILE) as f:
                data = json.load(f)
            acct = Account.from_key(data["private_key"])
            print("[Wallet] Loaded existing keypair")
            return acct

        # Generate new keypair
        acct = Account.create()
        os.makedirs(WALLET_DIR, exist_ok=True)
        with open(WALLET_KEY_FILE, "w") as f:
            json.dump({"private_key": acct.key.hex(), "address": acct.address}, f)
        os.chmod(WALLET_KEY_FILE, 0o600)
        print(f"[Wallet] Generated new keypair: {acct.address}")
        return acct

    @property
    def address(self) -> str:
        return str(self._account.address)

    @property
    def address_short(self) -> str:
        """Short prefix for BLE device name."""
        return str(self._account.address)[2:10].lower()

    def sign_challenge(self) -> dict[str, object]:
        """Create and sign a challenge proving device identity."""
        challenge = {
            "walletAddress": self.address,
            "timestamp": int(time.time()),
            "nonce": stdlib_secrets.token_hex(16),
        }
        message = json.dumps(challenge, sort_keys=True)
        signed = self._account.sign_message(encode_defunct(text=message))
        return {
            **challenge,
            "signedPayload": message,
            "signature": "0x" + signed.signature.hex(),
        }

    def sign_response(self, data: dict) -> dict:
        """Sign a response data object. Returns an EthSignedMessage dict."""
        message = json.dumps(data)
        signed = self._account.sign_message(encode_defunct(text=message))
        return {
            "walletAddress": self.address,
            "message": message,
            "signature": "0x" + signed.signature.hex(),
        }

    def verify_server_signature(
        self, payload: str, signature: str, server_address: str
    ) -> bool:
        """Verify a message was signed by the server's wallet."""
        try:
            sig_bytes = bytes.fromhex(signature.replace("0x", ""))
            recovered = Account.recover_message(
                encode_defunct(text=payload), signature=sig_bytes
            )
            return bool(recovered.lower() == server_address.lower())
        except Exception as e:
            print(f"[Wallet] Signature verification failed: {e}")
            return False


def verify_signed_response(data: object, signing: dict) -> bool:
    """Verify a signed response: data integrity + signature validity.

    1. Decodes signing["message"] as JSON and compares with data.
    2. Recovers signer from signature and compares with signing["walletAddress"].
    """
    try:
        decoded = json.loads(signing["message"])
        if json.dumps(decoded) != json.dumps(data):
            return False
        sig_bytes = bytes.fromhex(signing["signature"].replace("0x", ""))
        recovered = Account.recover_message(
            encode_defunct(text=signing["message"]), signature=sig_bytes
        )
        return bool(recovered.lower() == signing["walletAddress"].lower())
    except Exception as e:
        print(f"[Wallet] verify_signed_response failed: {e}")
        return False


def verify_signed_payload(
    payload: dict, expected_signer: str | None = None
) -> bool:
    """Verify a SignedData payload envelope: data integrity + signature + optional signer check.

    Args:
        payload: A dict with 'data' and 'signing' fields (SignedData envelope).
        expected_signer: If provided, also verify the signer matches this address.

    Returns:
        True if the envelope is valid (and signer matches, if expected_signer given).
    """
    data = payload.get("data")
    signing = payload.get("signing")

    if not data or not signing:
        return False

    if not verify_signed_response(data, signing):
        return False

    if expected_signer:
        signer = signing.get("walletAddress", "")
        if signer.lower() != expected_signer.lower():
            return False

    return True
