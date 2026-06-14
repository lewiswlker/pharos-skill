# Pay for a 402 resource

End-to-end flow: the agent requests a paid resource, pays autonomously, and the
payment settles and is recorded on-chain.

## Prerequisites

Complete `setup.md` first (wallet funded with PHRS, contracts deployed,
`.env` populated).

## Start the services

In separate terminals:

```bash
python scripts/facilitator.py    # default http://127.0.0.1:8401
python scripts/server.py         # default http://127.0.0.1:8402
```

## Run the agent

```bash
python scripts/agent_pay.py /data
```

Expected output:

```
Agent: 0x...
402 quote: 0.10 TUSD for /data -> 0x<seller>
DECISION: within budget, paying.
Data received: {"asset": "PHRS/USD", "price": 0.0123, ...}
Settlement tx: https://atlantic.pharosscan.xyz/tx/0x...
Recording receipt on PaymentLedger ...
Ledger receipt #0: https://atlantic.pharosscan.xyz/tx/0x...
Cumulative spend: 0.10 TUSD
```

## What just happened

1. **Quote** — the server replied `402` with x402 payment requirements
   (`scheme: exact`, `network: eip155:688689`, amount, `payTo`, `asset`).
2. **Decision** — the agent checked the price against its budget (`budget.md`).
3. **Authorization** — the agent signed an EIP-712 `TransferWithAuthorization`
   message for TestUSD. It pays no gas to do this.
4. **Settlement** — the server forwarded the signed payment to the facilitator,
   which called `transferWithAuthorization` on-chain (EIP-3009). TUSD moved from
   the agent to the seller.
5. **Delivery** — the server returned the data plus an `X-PAYMENT-RESPONSE`
   header containing the settlement transaction.
6. **Record** — the agent wrote a receipt to the `PaymentLedger` contract.

## The X-PAYMENT header

The agent base64-encodes this JSON into the `X-PAYMENT` request header:

```json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "eip155:688689",
  "payload": {
    "signature": "0x...",
    "authorization": {
      "from": "0x<agent>",
      "to": "0x<seller>",
      "value": "100000",
      "validAfter": "...",
      "validBefore": "...",
      "nonce": "0x..."
    }
  }
}
```

`value` is in TUSD base units (6 decimals), so `100000` = 0.10 TUSD.

## Troubleshooting

- `authorization expired` — your clock or the chain time drifted; the agent uses
  on-chain block time, so just retry.
- `amount below required` — the server price is higher than what was signed;
  re-run so the agent re-reads the quote.
- `settlement failed` — confirm the facilitator's relayer has PHRS for gas.
