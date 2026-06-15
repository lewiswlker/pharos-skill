# Setup

Prepare a wallet and deploy the contracts on the Pharos Atlantic testnet.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

This pulls in `web3`, `eth-account`, `py-solc-x` (which downloads solc 0.8.20 on
first compile), `fastapi`, `uvicorn`, and `requests`.

## 2. Configure

```bash
cp .env.example .env
```

`.env` already contains the public Pharos testnet RPC, chain id, and explorer.
You only need to add a private key (next step) — addresses are filled in by the
deploy script.

## 3. Create a testnet wallet

```bash
python scripts/new_wallet.py
```

- Generates a fresh key locally and writes it to `.env` as `PRIVATE_KEY`.
- The key never leaves your machine and is git-ignored.
- The command prints only the public address.

> Never use a wallet that holds real funds. This is testnet only.

## 4. Get testnet PHRS for gas

Send the printed address to the Pharos faucet and request testnet **PHRS**.
Deploying contracts and recording payments costs a small amount of gas.

## 5. Deploy the contracts

> Already have `TUSD_ADDRESS` and `LEDGER_ADDRESS` in `.env`? The contracts are
> already deployed. Skip this step and continue with `pay.md`.

```bash
python scripts/deploy.py
```

This deploys:

- **TestUSD** — an EIP-3009 stablecoin; 1,000,000 TUSD is minted to your wallet so
  it can act as the demo payer.
- **PaymentLedger** — the on-chain spend ledger.

It also generates a seller (payee) address if `PAY_TO_ADDRESS` is empty, then
writes `TUSD_ADDRESS`, `LEDGER_ADDRESS`, and `PAY_TO_ADDRESS` back to `.env`.

Both deployment transactions are printed with explorer links.

## Next

Continue with `pay.md` to run an end-to-end payment.
