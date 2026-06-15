# Submission — x402-pharos-autopay

Pharos Skill-to-Agent Dual Cascade Hackathon, Phase 1 (Skill).

- Repository: https://github.com/lewiswlker/pharos-skill
- Network: Pharos Atlantic testnet (chainId 688689)
- License: MIT

## What it is

An Agent Skill that lets an AI agent pay for an `HTTP 402` (x402) resource on its
own: it reads the price quote, checks a spending budget, signs an EIP-3009
transfer authorization, settles it on-chain through a facilitator, and records the
payment in an on-chain ledger. The repository ships the contracts, the
facilitator, the paid server, and the paying agent, so the whole flow runs from a
single clone.

## How to verify in two minutes

No chain access or testnet funds are needed for the self-checks:

```bash
pip install -r requirements.txt
python tests/test_eip712.py      # signing digest matches the contract
python tests/test_e2e_local.py   # deploy -> settle -> replay-guard -> record on an in-memory EVM
```

The same two checks run in CI on every push (see the badge in `README.md`).

## Mapping to the judging criteria

### Security

- Private keys live only in `.env` (git-ignored). Scripts print and share only
  public addresses.
- A `pre-commit` hook (`.githooks/pre-commit`) scans staged changes for keys;
  enable it with `git config core.hooksPath .githooks`.
- Testnet only. This is stated in the code, the docs, and `.env.example`; there is
  no mainnet configuration.
- Both Solidity contracts are self-contained, with no external imports or
  inherited libraries, so no third-party contract code sits in the trust path.
- Budget guardrails enforce a per-call cap and a cumulative cap before any
  signature. An over-budget call exits without signing.
- Settlement uses EIP-3009 `transferWithAuthorization`: the signed amount and
  recipient cannot be altered by the facilitator, and a used nonce cannot be
  replayed. Both are checked in `tests/test_e2e_local.py`.
- The scripts only call the local facilitator/server and the configured RPC. They
  do not run arbitrary shell commands or send data anywhere else.

### Originality

- The official `x402-pharos` reference is a TypeScript tutorial that leaves two
  gaps: its sample token does not support EIP-3009, and the facilitator is left
  for the developer to build. This skill fills both with a working EIP-3009
  `TestUSD` and a one-command facilitator.
- It adds an agent-side budget guard and an on-chain `PaymentLedger`, neither of
  which the reference provides.
- It is implemented in Python (web3.py) rather than the TypeScript reference.

### Technical completeness

- The full path is implemented: paid server (402 quote) -> agent decision ->
  EIP-712 signing -> facilitator settlement -> ledger record.
- Two offline self-checks: the EIP-712 digest equals the digest the contract
  computes itself, and a full deploy/settle/replay/record cycle runs on an
  in-memory EVM.
- CI runs both checks on every push.

### Usefulness

- Gives an AI agent a spending wallet with hard limits and an auditable, on-chain
  record of what it paid for.
- Applies to any agent that needs to consume metered or paid HTTP resources
  without a human approving each charge.

### Reusability and composability

- Standard Anthropic Agent Skills layout (`SKILL.md` + `references/` + `assets/`),
  so a compatible agent can load it directly.
- Each capability (setup, pay, budget, ledger) is documented on its own.
- The same scripts compose into a full agent for Phase 2.

### Documentation

- `README.md` (overview and quick start), `SKILL.md` (capability index), and four
  reference guides under `references/` (setup, pay, budget, ledger).

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
| Settle payment (transferWithAuthorization) | [0xb3cea6…68747](https://atlantic.pharosscan.xyz/tx/0xb3cea61ca330239eb76a5b723db6cd9dd4a32a3c2b0c94bc1d9ec9a0dd368747) |
| Record receipt on PaymentLedger | _re-running after a nonce fix_ |

The settlement transaction is an EIP-3009 `transferWithAuthorization` that moved
0.10 TUSD from the agent to the seller, with the contract verifying the agent's
signature itself.
