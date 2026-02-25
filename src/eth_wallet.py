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
            "signature": signed.signature.hex(),
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
