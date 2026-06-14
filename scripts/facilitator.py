#!/usr/bin/env python3
"""x402 facilitator for the Pharos Atlantic testnet.

Exposes the three endpoints an x402 server needs:
  GET  /supported  -> the schemes/networks this facilitator can settle
  POST /verify     -> validate a signed payment without touching the chain
  POST /settle     -> broadcast the EIP-3009 transferWithAuthorization on-chain

The relayer account (RELAYER_PRIVATE_KEY, or PRIVATE_KEY) pays the gas, so the
payer's transfer is gasless. TESTNET ONLY.
"""
from __future__ import annotations

from urllib.parse import urlparse

from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi import FastAPI
from pydantic import BaseModel
from web3 import Web3

import _common as c

app = FastAPI(title="x402-pharos facilitator")

NETWORK_ID = f"eip155:{c.require_env('PHAROS_CHAIN_ID')}"


class SettleRequest(BaseModel):
    paymentPayload: dict
    paymentRequirements: dict


def _token():
    w3 = c.get_web3()
    return w3, w3.eth.contract(
        address=Web3.to_checksum_address(c.require_env("TUSD_ADDRESS")),
        abi=c.token_abi(),
    )


def _validate(payload: dict, requirements: dict) -> tuple[bool, str, dict]:
    """Return (is_valid, reason, parsed_authorization)."""
    if payload.get("scheme") != requirements.get("scheme", "exact"):
        return False, "scheme mismatch", {}
    if payload.get("network") != NETWORK_ID:
        return False, "network mismatch", {}

    inner = payload.get("payload", {})
    auth = inner.get("authorization", {})
    signature = inner.get("signature")
    if not auth or not signature:
        return False, "missing authorization or signature", {}

    try:
        value = int(auth["value"])
        valid_after = int(auth["validAfter"])
        valid_before = int(auth["validBefore"])
    except (KeyError, ValueError):
        return False, "malformed authorization fields", {}

    required = int(requirements.get("maxAmountRequired", 0))
    if value < required:
        return False, f"amount {value} below required {required}", {}

    pay_to = requirements.get("payTo")
    if pay_to and Web3.to_checksum_address(auth["to"]) != Web3.to_checksum_address(pay_to):
        return False, "payTo mismatch", {}

    w3, token = _token()
    now = w3.eth.get_block("latest")["timestamp"]
    if now <= valid_after:
        return False, "authorization not yet valid", {}
    if now >= valid_before:
        return False, "authorization expired", {}

    # Recover the signer and confirm it matches `from`.
    typed = c.transfer_authorization_typed_data(
        c.require_env("TUSD_ADDRESS"),
        w3.eth.chain_id,
        auth["from"],
        auth["to"],
        value,
        valid_after,
        valid_before,
        auth["nonce"],
    )
    signable = encode_typed_data(full_message=typed)
    signer = Account.recover_message(signable, signature=signature)
    if Web3.to_checksum_address(signer) != Web3.to_checksum_address(auth["from"]):
        return False, "signature does not match 'from'", {}

    # Reject already-used nonces.
    nonce_bytes = Web3.to_bytes(hexstr=auth["nonce"])
    if token.functions.authorizationState(
        Web3.to_checksum_address(auth["from"]), nonce_bytes
    ).call():
        return False, "authorization already used", {}

    return True, "", auth


@app.get("/supported")
def supported() -> dict:
    return {"kinds": [{"scheme": "exact", "network": NETWORK_ID}]}


@app.post("/verify")
def verify(req: SettleRequest) -> dict:
    ok, reason, _ = _validate(req.paymentPayload, req.paymentRequirements)
    return {"isValid": ok, "invalidReason": reason or None}


@app.post("/settle")
def settle(req: SettleRequest) -> dict:
    ok, reason, auth = _validate(req.paymentPayload, req.paymentRequirements)
    if not ok:
        return {"success": False, "error": reason, "network": NETWORK_ID}

    w3, token = _token()
    relayer = c.get_relayer()

    signature = req.paymentPayload["payload"]["signature"]
    sig = Web3.to_bytes(hexstr=signature)
    r, s, v = sig[:32], sig[32:64], sig[64]

    func = token.functions.transferWithAuthorization(
        Web3.to_checksum_address(auth["from"]),
        Web3.to_checksum_address(auth["to"]),
        int(auth["value"]),
        int(auth["validAfter"]),
        int(auth["validBefore"]),
        Web3.to_bytes(hexstr=auth["nonce"]),
        v,
        r,
        s,
    )
    receipt = c.send_tx(w3, relayer, func)
    tx_hash = receipt.transactionHash.hex()
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
    return {
        "success": receipt.status == 1,
        "txHash": tx_hash,
        "network": NETWORK_ID,
        "explorer": c.explorer_tx(receipt.transactionHash),
    }


def main() -> None:
    import uvicorn

    url = urlparse(c.env("FACILITATOR_URL", "http://127.0.0.1:8401"))
    print(f"Facilitator listening on {url.geturl()}  (network {NETWORK_ID})")
    uvicorn.run(app, host=url.hostname or "127.0.0.1", port=url.port or 8401)


if __name__ == "__main__":
    main()
