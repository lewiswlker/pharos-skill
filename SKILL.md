---
name: x402-pharos-autopay
description: >-
  Use when an AI agent must autonomously pay for HTTP resources that respond with
  HTTP 402 (the x402 protocol) on the Pharos network. The skill reads the price
  quote, enforces spending budgets, signs an EIP-3009 transfer authorization,
  settles it on-chain through a facilitator, and records every payment in an
  on-chain ledger. Covers wallet setup, contract deployment, running the
  facilitator/server, and querying spend history.
version: 0.1.0
requires:
  anyBins:
  - python3
metadata:
  network: pharos-atlantic-testnet
  chainId: 688689
  protocol: x402 (exact scheme, EIP-3009 settlement)
---

# x402-pharos-autopay

This skill lets an agent turn an `HTTP 402 Payment Required` response into a
completed, on-chain, budget-checked micropayment on the Pharos Atlantic testnet —
with no API keys and no human in the loop.

## When to use it

- An endpoint returns `402` with an x402 price quote and the agent needs the data.
- You need to give an agent a spending wallet with hard budget limits.
- You need an auditable, on-chain record of what an agent paid for.

## How it works

```
agent ──GET──▶ server ──402 + quote──▶ agent
agent: budget guard → decide → sign EIP-712 (EIP-3009) authorization
agent ──GET + X-PAYMENT──▶ server ──/verify,/settle──▶ facilitator ──tx──▶ TestUSD
agent ──record()──▶ PaymentLedger        (all on chainId 688689)
```

The payer only signs; the facilitator pays gas and broadcasts, so payments are
gasless for the agent. Settlement uses EIP-3009 `transferWithAuthorization`, so
the signed amount and recipient cannot be tampered with.

## Capabilities

| Task | Read |
| --- | --- |
| Install deps, create a wallet, deploy contracts | `references/setup.md` |
| Pay for a 402 resource end-to-end | `references/pay.md` |
| Configure and reason about budget guardrails | `references/budget.md` |
| Inspect on-chain spend history | `references/ledger.md` |

## Components

| File | Role |
| --- | --- |
| `assets/contracts/TestUSD.sol` | EIP-3009 test stablecoin (decimals 6, EIP-712 version "2") |
| `assets/contracts/PaymentLedger.sol` | On-chain, append-only spending ledger |
| `assets/networks.json` | Pharos network configuration |
| `scripts/new_wallet.py` | Create a testnet-only wallet (key stays local) |
| `scripts/deploy.py` | Deploy TestUSD + PaymentLedger |
| `scripts/facilitator.py` | x402 facilitator: `/verify`, `/settle`, `/supported` |
| `scripts/server.py` | Paid resource server that emits 402 quotes |
| `scripts/agent_pay.py` | Autonomous paying agent (budget → sign → settle → record) |

## Quick reference

```bash
pip install -r requirements.txt
python scripts/new_wallet.py          # fund the printed address with testnet PHRS
python scripts/deploy.py              # deploy contracts, write addresses to .env
python scripts/facilitator.py &       # terminal 1
python scripts/server.py &            # terminal 2
python scripts/agent_pay.py /data     # terminal 3: pay, settle, record
```

## Safety

- Testnet only. Never use a wallet holding real funds.
- Private keys live solely in `.env` (git-ignored). Only addresses are shared.
- Budgets are enforced before signing; an over-budget call is skipped, not paid.
