#!/usr/bin/env python3
"""Autonomous x402 paying agent.

Calls a paid resource, and when it gets an HTTP 402:
  1. Reads the price quote.
  2. Applies budget guardrails (per-call cap + cumulative cap) and decides
     autonomously whether to pay.
  3. Signs an EIP-712 / EIP-3009 transfer authorization (gasless).
  4. Resends the request with the X-PAYMENT header and receives the data.
  5. Records the settled payment on-chain in the PaymentLedger.

Usage:
    python scripts/agent_pay.py            # pay for the default /data resource
    python scripts/agent_pay.py /data

TESTNET ONLY.
"""
from __future__ import annotations

import base64
import json
import secrets
import sys
from decimal import Decimal
from pathlib import Path

import requests
from eth_account.messages import encode_typed_data
from web3 import Web3

import _common as c

SPENT_PATH = c.ROOT / ".spent.json"


def load_spent() -> dict:
    if SPENT_PATH.exists():
        try:
            return json.loads(SPENT_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_spent(spent: dict) -> None:
    SPENT_PATH.write_text(json.dumps(spent, indent=2) + "\n")


def budget_ok(token: str, price_base: int) -> tuple[bool, str]:
    per_call = c.to_base_units(c.env("BUDGET_PER_CALL", "0.50"))
    total_cap = c.to_base_units(c.env("BUDGET_TOTAL", "5.00"))
    if price_base > per_call:
        return False, (
            f"price {c.to_human(price_base)} exceeds per-call cap "
            f"{c.to_human(per_call)} TUSD"
        )
    already = int(load_spent().get(token.lower(), 0))
    if already + price_base > total_cap:
        return False, (
            f"price {c.to_human(price_base)} would exceed total budget "
            f"{c.to_human(total_cap)} TUSD (already spent {c.to_human(already)})"
        )
    return True, ""


def build_payment(agent, requirements: dict, chain_id: int, now: int) -> tuple[dict, str]:
    token = requirements["asset"]
    value = int(requirements["maxAmountRequired"])
    nonce = "0x" + secrets.token_bytes(32).hex()
    valid_after = now - 60
    valid_before = now + int(requirements.get("maxTimeoutSeconds", 600))

    typed = c.transfer_authorization_typed_data(
        token, chain_id, agent.address, requirements["payTo"],
        value, valid_after, valid_before, nonce,
    )
    signed = agent.sign_message(encode_typed_data(full_message=typed))
    signature = signed.signature.hex()
    if not signature.startswith("0x"):
        signature = "0x" + signature

    payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": requirements["network"],
        "payload": {
            "signature": signature,
            "authorization": {
                "from": agent.address,
                "to": requirements["payTo"],
                "value": str(value),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce,
            },
        },
    }
    return payload, nonce


def record_on_ledger(w3, agent, requirements: dict, resource: str, nonce: str):
    ledger = w3.eth.contract(
        address=Web3.to_checksum_address(c.require_env("LEDGER_ADDRESS")),
        abi=c.ledger_abi(),
    )
    func = ledger.functions.record(
        Web3.to_checksum_address(requirements["payTo"]),
        Web3.to_checksum_address(requirements["asset"]),
        int(requirements["maxAmountRequired"]),
        resource,
        Web3.to_bytes(hexstr=nonce),
    )
    receipt = c.send_tx(w3, agent, func)
    events = ledger.events.PaymentRecorded().process_receipt(receipt)
    receipt_id = events[0]["args"]["receiptId"] if events else None
    return receipt, receipt_id


def main() -> None:
    resource = sys.argv[1] if len(sys.argv) > 1 else "/data"
    server = c.env("SERVER_URL", "http://127.0.0.1:8402").rstrip("/")
    url = f"{server}{resource}"

    w3 = c.get_web3()
    agent = c.get_account("PRIVATE_KEY")
    chain_id = w3.eth.chain_id
    print(f"Agent: {agent.address}")

    # 1. Ask for the resource.
    first = requests.get(url, timeout=30)
    if first.status_code != 402:
        print(f"Resource returned {first.status_code} (no payment required).")
        print(first.text)
        return

    requirements = first.json()["accepts"][0]
    token = requirements["asset"]
    price_base = int(requirements["maxAmountRequired"])
    print(f"402 quote: {c.to_human(price_base)} TUSD for {resource} -> {requirements['payTo']}")

    # 2. Budget guard + autonomous decision.
    ok, reason = budget_ok(token, price_base)
    if not ok:
        print(f"DECISION: skip payment. {reason}")
        sys.exit(2)
    print("DECISION: within budget, paying.")

    # 3. Sign the EIP-3009 authorization.
    now = w3.eth.get_block("latest")["timestamp"]
    payload, nonce = build_payment(agent, requirements, chain_id, now)
    header = base64.b64encode(json.dumps(payload).encode()).decode()

    # 4. Resend with payment; server verifies + settles on-chain.
    paid = requests.get(url, headers={"X-PAYMENT": header}, timeout=180)
    if paid.status_code != 200:
        print(f"Payment failed ({paid.status_code}): {paid.text}")
        sys.exit(1)

    settle = json.loads(base64.b64decode(paid.headers.get("X-PAYMENT-RESPONSE", "")))
    print("Data received:", json.dumps(paid.json()))
    print(f"Settlement tx: {settle.get('explorer', settle.get('txHash'))}")

    # 5. Record the payment on-chain.
    print("Recording receipt on PaymentLedger ...")
    rcpt, receipt_id = record_on_ledger(w3, agent, requirements, resource, nonce)
    print(f"Ledger receipt #{receipt_id}: {c.explorer_tx(rcpt.transactionHash)}")

    # 6. Update local spend tracker.
    spent = load_spent()
    spent[token.lower()] = int(spent.get(token.lower(), 0)) + price_base
    save_spent(spent)
    print(f"Cumulative spend: {c.to_human(spent[token.lower()])} TUSD")


if __name__ == "__main__":
    main()
