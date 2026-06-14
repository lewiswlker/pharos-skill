#!/usr/bin/env python3
"""A paid resource server that speaks x402.

GET /data
  - Without a valid X-PAYMENT header  -> 402 + payment requirements (the quote)
  - With a valid X-PAYMENT header      -> verifies + settles via the facilitator,
                                          then returns the data plus an
                                          X-PAYMENT-RESPONSE header (settlement tx)

This is the resource an autonomous agent learns to pay for. TESTNET ONLY.
"""
from __future__ import annotations

import base64
import json
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import _common as c

app = FastAPI(title="x402-pharos paid server")

NETWORK_ID = f"eip155:{c.require_env('PHAROS_CHAIN_ID')}"
RESOURCE = "/data"


def payment_requirements() -> dict:
    price = c.to_base_units(c.env("RESOURCE_PRICE", "0.10"))
    return {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": NETWORK_ID,
                "maxAmountRequired": str(price),
                "resource": RESOURCE,
                "description": "Premium market data sample",
                "mimeType": "application/json",
                "payTo": c.require_env("PAY_TO_ADDRESS"),
                "maxTimeoutSeconds": 120,
                "asset": c.require_env("TUSD_ADDRESS"),
                "extra": {"name": "TestUSD", "version": "2"},
            }
        ],
    }


def _facilitator(path: str, body: dict) -> dict:
    base = c.env("FACILITATOR_URL", "http://127.0.0.1:8401").rstrip("/")
    resp = requests.post(f"{base}{path}", json=body, timeout=180)
    resp.raise_for_status()
    return resp.json()


# The actual premium payload returned after payment.
DATA = {
    "asset": "PHRS/USD",
    "price": 0.0123,
    "source": "x402-pharos-autopay demo feed",
}


@app.get("/data")
def data(request: Request):
    header = request.headers.get("X-PAYMENT")
    requirements = payment_requirements()["accepts"][0]

    if not header:
        return JSONResponse(status_code=402, content=payment_requirements())

    try:
        payload = json.loads(base64.b64decode(header))
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid X-PAYMENT header"})

    body = {"paymentPayload": payload, "paymentRequirements": requirements}

    verify = _facilitator("/verify", body)
    if not verify.get("isValid"):
        return JSONResponse(
            status_code=402,
            content={"error": "payment invalid", "reason": verify.get("invalidReason")},
        )

    settle = _facilitator("/settle", body)
    if not settle.get("success"):
        return JSONResponse(
            status_code=502,
            content={"error": "settlement failed", "reason": settle.get("error")},
        )

    receipt_header = base64.b64encode(json.dumps(settle).encode()).decode()
    return JSONResponse(
        status_code=200,
        content=DATA,
        headers={"X-PAYMENT-RESPONSE": receipt_header},
    )


def main() -> None:
    import uvicorn

    url = urlparse(c.env("SERVER_URL", "http://127.0.0.1:8402"))
    print(f"Paid server listening on {url.geturl()}  (resource {RESOURCE})")
    uvicorn.run(app, host=url.hostname or "127.0.0.1", port=url.port or 8402)


if __name__ == "__main__":
    main()
