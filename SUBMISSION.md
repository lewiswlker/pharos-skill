# Submission — x402-pharos-autopay

Pharos Skill-to-Agent Dual Cascade Hackathon, Phase 1 (Skill).

- Repository: https://github.com/lewiswlker/pharos-skill
- Network: Pharos Atlantic testnet (chainId 688689)
- License: MIT

## What this submission ships

An Agent Skill that lets an AI agent pay for an `HTTP 402` (x402) resource on
its own: it reads the price quote, checks a spending budget, signs an EIP-3009
transfer authorization, settles it on-chain through a facilitator, and records
the payment in an on-chain ledger. The repository ships the contracts, the
facilitator, the paid server, and the paying agent, so the whole flow runs from
a single clone.

The repository layout follows the Anthropic Agent Skills format:

- `SKILL.md` — capability index loaded by the agent
- `references/` — per-capability instructions (`setup`, `pay`, `budget`, `ledger`)
- `assets/contracts/` — `TestUSD.sol` (EIP-3009) and `PaymentLedger.sol`
- `assets/networks.json` — Pharos network configuration
- `scripts/` — wallet, deploy, facilitator, server, paying agent

## How to verify

Two offline self-checks need no chain access or testnet funds:

```bash
pip install -r requirements.txt
python tests/test_eip712.py      # signing digest matches the contract
python tests/test_e2e_local.py   # deploy -> settle -> replay-guard -> record on an in-memory EVM
```

Both run in CI on every push (see the badge in `README.md`).

To exercise the live testnet flow, follow `references/setup.md` and then run
`bash scripts/demo.sh`. The transactions in the next section were produced this
way.

## On-chain activity

Deployed and exercised on Pharos Atlantic testnet (chainId 688689).

Contracts:

- TestUSD (EIP-3009): `0x436Bb3948e06A424F93109d76f8a22b8DC2f87Bd`
- PaymentLedger: `0xe464E30a9287A8E48E43148712e30611ad7A155C`

Transactions:

| Step | Transaction |
| --- | --- |
| Deploy TestUSD (EIP-3009) | [0x9c448e…1accc](https://atlantic.pharosscan.xyz/tx/0x9c448ec298b636f610da256d4fea5920ebed10a16ce5eb13e180dc491671accc) |
| Deploy PaymentLedger | [0xd869e8…b08d3](https://atlantic.pharosscan.xyz/tx/0xd869e87d0d5023a21e63f202fbc5e810a7284428b431dfb616920adee2ab08d3) |
| Settle payment (transferWithAuthorization) | [0x8759f0…7ee63](https://atlantic.pharosscan.xyz/tx/0x8759f0ee6f4e87f9e939c92465d13fdf8ca58a08a4dd2c25f5cd34ae6647ee63) |
| Record receipt on PaymentLedger | [0xa7b5d5…73cf6d](https://atlantic.pharosscan.xyz/tx/0xa7b5d55787999d5517019513d6e124bb62549d50929406ee17819fe71373cf6d) |

The settlement transaction is an EIP-3009 `transferWithAuthorization` that
moved 0.10 TUSD from the agent to the seller; the TestUSD contract verifies the
agent's signature itself. The record transaction is the first entry in the
on-chain `PaymentLedger`: `totalReceipts() = 1`, and
`totalSpent(agent, TUSD) = 0.10`.

## Security and testnet notes

- Private keys live only in `.env` (git-ignored). Scripts share only public
  addresses.
- A `pre-commit` hook (`.githooks/pre-commit`) scans staged changes for keys;
  enable it with `git config core.hooksPath .githooks`.
- The Solidity contracts are self-contained, with no external imports.
- Settlement uses EIP-3009 `transferWithAuthorization`. The signed amount and
  recipient cannot be altered by the facilitator, and a used nonce cannot be
  replayed; both properties are checked in `tests/test_e2e_local.py`.
- Budgets are enforced before signing: an over-budget call exits without
  producing a signature.
- This project targets **testnet only**. Do not use a wallet that holds real
  funds.
