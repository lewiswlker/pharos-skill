# x402-pharos-autopay

[![CI](https://github.com/lewiswlker/pharos-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/lewiswlker/pharos-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

An Agent Skill for paying [x402](https://github.com/coinbase/x402) `HTTP 402`
resources on the Pharos Atlantic testnet. The skill reads the price quote, checks
a spending budget, signs an EIP-3009 transfer authorization, settles it on-chain
through a facilitator, and records the payment in an on-chain ledger.

Built for the Pharos Skill-to-Agent Dual Cascade Hackathon (Phase 1: Skill).

## What it does

When an AI agent calls a paid endpoint it receives an `HTTP 402` response with a
price quote. This skill teaches the agent to:

1. **Decide autonomously** whether to pay, based on configurable budget limits
   (per-call cap and cumulative cap).
2. **Authorize the payment** by signing an EIP-712 `TransferWithAuthorization`
   message (gasless for the agent).
3. **Settle on-chain** through a facilitator that submits the EIP-3009 transfer.
4. **Record the receipt** in an on-chain `PaymentLedger`, building a queryable,
   auditable spending history.

## Features

- Ships its own EIP-3009 test stablecoin (`TestUSD`) and a one-command
  facilitator, so there is nothing external to set up.
- Checks a per-call cap and a cumulative cap before signing, and skips a call
  that would exceed the budget instead of paying it.
- Token deploy, ledger deploy, settlement transfers and ledger records are all
  real transactions on Atlantic testnet.
- The scripts are reused by a full agent in Phase 2.

## Architecture

```
 AI agent (reads SKILL.md)
        │ wants a paid resource
        ▼
   Client ──402 quote──▶ x402 Server (paid endpoints)
   · budget guard            │ verify + settle
   · autonomous decision      ▼
   · signs EIP-712      Facilitator ──transferWithAuthorization──▶ TestUSD (EIP-3009)
        │
        └── records receipt ──▶ PaymentLedger (on-chain spending history)

        Pharos Atlantic testnet · chainId 688689
```

## On-chain run

Deployed and exercised on Pharos Atlantic testnet (chainId 688689):

- TestUSD (EIP-3009): [`0x436Bb3…2f87Bd`](https://atlantic.pharosscan.xyz/address/0x436Bb3948e06A424F93109d76f8a22b8DC2f87Bd)
- PaymentLedger: [`0xe464E3…7A155C`](https://atlantic.pharosscan.xyz/address/0xe464E30a9287A8E48E43148712e30611ad7A155C)

| Step | Transaction |
| --- | --- |
| Deploy TestUSD | [view](https://atlantic.pharosscan.xyz/tx/0x9c448ec298b636f610da256d4fea5920ebed10a16ce5eb13e180dc491671accc) |
| Deploy PaymentLedger | [view](https://atlantic.pharosscan.xyz/tx/0xd869e87d0d5023a21e63f202fbc5e810a7284428b431dfb616920adee2ab08d3) |
| Settle payment (EIP-3009 `transferWithAuthorization`) | [view](https://atlantic.pharosscan.xyz/tx/0x8759f0ee6f4e87f9e939c92465d13fdf8ca58a08a4dd2c25f5cd34ae6647ee63) |
| Record receipt on PaymentLedger | [view](https://atlantic.pharosscan.xyz/tx/0xa7b5d55787999d5517019513d6e124bb62549d50929406ee17819fe71373cf6d) |

The settlement moved 0.10 TUSD from the agent to the seller, with TestUSD
verifying the signature on-chain. The receipt is the first entry in the on-chain
`PaymentLedger`; `totalReceipts()` reports `1` and
`totalSpent(agent, TUSD)` reports `0.10 TUSD`.

## Repository layout

```
SKILL.md                 # capability index for the agent
references/              # step-by-step instructions per capability
assets/
  networks.json          # Pharos network config
  contracts/             # TestUSD.sol (EIP-3009) + PaymentLedger.sol
scripts/                # new_wallet, deploy, facilitator, server, agent client
.env.example            # configuration template (real secrets go in .env)
```

## Quick start

> Full step-by-step instructions live in `references/setup.md`.

```bash
pip install -r requirements.txt
python scripts/new_wallet.py        # create a testnet wallet (key stays local)
# fund the printed address with testnet PHRS from the faucet, then:
python scripts/deploy.py            # deploy TestUSD + PaymentLedger
python scripts/facilitator.py       # start the settlement facilitator (terminal 1)
python scripts/server.py            # start the paid resource server (terminal 2)
python scripts/agent_pay.py /data   # agent pays, settles, records (terminal 3)
# or, after deploy, run the whole flow with one command:
bash scripts/demo.sh
```

## Tests

Two self-checks run offline, with no live chain or testnet funds:

```bash
python tests/test_eip712.py      # signing digest matches the contract; signatures recover
python tests/test_e2e_local.py   # full pay -> settle -> record flow on an in-memory EVM
```

`test_e2e_local.py` deploys the real contracts, settles an EIP-3009 transfer
(the contract verifies the signature itself), checks nonce-replay protection, and
records the payment on the ledger — the same flow that runs on Pharos.

## Security

- Private keys live only in `.env` (git-ignored) and never in code or logs.
- A `pre-commit` hook scans staged changes for keys; enable it once per clone with
  `git config core.hooksPath .githooks`.
- This project targets **testnet only**. Do not use a wallet holding real funds.

## License

MIT. See [LICENSE](./LICENSE).
