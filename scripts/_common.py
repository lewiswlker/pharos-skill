"""Shared helpers for the x402-pharos-autopay scripts.

Loads configuration from .env, exposes a configured web3 client, compiles the
self-contained Solidity contracts with py-solc-x, and provides small helpers for
sending transactions and converting token units.

TESTNET ONLY. Never point this at a wallet that holds real funds.
"""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "assets" / "contracts"
ENV_PATH = ROOT / ".env"
SOLC_VERSION = "0.8.20"

load_dotenv(ENV_PATH)

TOKEN_DECIMALS = 6  # TestUSD mirrors USDC


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key)
    return value if value not in (None, "") else default


def require_env(key: str) -> str:
    value = env(key)
    if value is None:
        raise SystemExit(f"Missing required config '{key}'. Set it in .env (see .env.example).")
    return value


def rpc_url() -> str:
    return require_env("PHAROS_RPC_URL")


@functools.lru_cache(maxsize=1)
def get_web3() -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc_url()))
    if not w3.is_connected():
        raise SystemExit(f"Cannot reach Pharos RPC at {rpc_url()}")
    return w3


def get_account(key_env: str = "PRIVATE_KEY") -> Account:
    pk = require_env(key_env)
    return Account.from_key(pk)


def get_relayer() -> Account:
    """The account that submits settlements. Falls back to PRIVATE_KEY."""
    pk = env("RELAYER_PRIVATE_KEY") or require_env("PRIVATE_KEY")
    return Account.from_key(pk)


# --------------------------------------------------------------------------- #
# Units
# --------------------------------------------------------------------------- #
def to_base_units(human_amount: str | float) -> int:
    """Convert a human TUSD amount (e.g. '0.10') to integer base units."""
    from decimal import Decimal

    return int(Decimal(str(human_amount)) * (10 ** TOKEN_DECIMALS))


def to_human(base_units: int) -> str:
    from decimal import Decimal

    return str(Decimal(base_units) / (10 ** TOKEN_DECIMALS))


# --------------------------------------------------------------------------- #
# Compilation
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=8)
def compile_contract(sol_filename: str, contract_name: str) -> tuple[list, str]:
    """Compile one self-contained .sol file and return (abi, bytecode)."""
    from solcx import compile_standard, install_solc, set_solc_version

    install_solc(SOLC_VERSION)
    set_solc_version(SOLC_VERSION)

    source = (CONTRACTS_DIR / sol_filename).read_text()
    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {sol_filename: {"content": source}},
            "settings": {
                "optimizer": {"enabled": True, "runs": 200},
                "outputSelection": {
                    "*": {"*": ["abi", "evm.bytecode.object"]}
                },
            },
        },
        solc_version=SOLC_VERSION,
    )
    contract = compiled["contracts"][sol_filename][contract_name]
    abi = contract["abi"]
    bytecode = contract["evm"]["bytecode"]["object"]
    return abi, bytecode


def token_abi() -> list:
    return compile_contract("TestUSD.sol", "TestUSD")[0]


def ledger_abi() -> list:
    return compile_contract("PaymentLedger.sol", "PaymentLedger")[0]


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
def _raw(signed) -> bytes:
    # web3 v6 uses raw_transaction; older builds used rawTransaction.
    return getattr(signed, "raw_transaction", None) or signed.rawTransaction


def send_tx(w3: Web3, account: Account, func, value: int = 0):
    """Build, sign, send a contract call and wait for the receipt."""
    tx = func.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address, "pending"),
            "chainId": w3.eth.chain_id,
            "gasPrice": w3.eth.gas_price,
            "value": value,
        }
    )
    try:
        tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.3)
    except Exception:
        tx["gas"] = 3_000_000
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(_raw(signed))
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def deploy_contract(w3: Web3, account: Account, abi: list, bytecode: str, *args):
    """Deploy a contract and return (address, receipt)."""
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = contract.constructor(*args).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address, "pending"),
            "chainId": w3.eth.chain_id,
            "gasPrice": w3.eth.gas_price,
        }
    )
    try:
        tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.3)
    except Exception:
        tx["gas"] = 4_000_000
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(_raw(signed))
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt.contractAddress, receipt


def explorer_tx(tx_hash) -> str:
    base = (env("PHAROS_EXPLORER") or "").rstrip("/")
    h = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    if not h.startswith("0x"):
        h = "0x" + h
    return f"{base}/tx/{h}" if base else h


# --------------------------------------------------------------------------- #
# .env writeback
# --------------------------------------------------------------------------- #
def update_env(updates: dict) -> None:
    """Set or append key=value pairs in .env without disturbing other lines."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    remaining = dict(updates)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    for key, value in remaining.items():
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- #
# EIP-712 / EIP-3009 authorization
# --------------------------------------------------------------------------- #
def transfer_authorization_typed_data(
    token_address: str,
    chain_id: int,
    from_addr: str,
    to_addr: str,
    value: int,
    valid_after: int,
    valid_before: int,
    nonce_hex: str,
) -> dict:
    """Build the EIP-712 typed payload for TestUSD.transferWithAuthorization.

    The domain MUST match the contract: name 'TestUSD', version '2'.
    """
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": "TestUSD",
            "version": "2",
            "chainId": chain_id,
            "verifyingContract": Web3.to_checksum_address(token_address),
        },
        "message": {
            "from": Web3.to_checksum_address(from_addr),
            "to": Web3.to_checksum_address(to_addr),
            "value": value,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce_hex,
        },
    }
