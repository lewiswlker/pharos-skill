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

The deploy, settle, and record steps produce real transactions on Atlantic
testnet. Explorer links from a funded run will be listed here:

| Step | Transaction |
| --- | --- |
| Deploy TestUSD (EIP-3009) | _to be added_ |
| Deploy PaymentLedger | _to be added_ |
| Settle payment (transferWithAuthorization) | _to be added_ |
| Record receipt | _to be added_ |
