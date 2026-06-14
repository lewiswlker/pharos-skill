#!/usr/bin/env python3
"""Deploy TestUSD (EIP-3009) and PaymentLedger to the Pharos Atlantic testnet.

Writes the resulting addresses back into .env. The deployer account receives the
initial TestUSD supply so it can act as the demo payer. If PAY_TO_ADDRESS is not
set, a fresh seller address is generated to receive payments.

Usage:
    python scripts/deploy.py

Requires PRIVATE_KEY in .env and the address funded with testnet PHRS for gas.
"""
from __future__ import annotations

from eth_account import Account

import _common as c


def main() -> None:
    w3 = c.get_web3()
    deployer = c.get_account("PRIVATE_KEY")
    balance = w3.eth.get_balance(deployer.address)
    print(f"Deployer : {deployer.address}")
    print(f"Gas (PHRS): {w3.from_wei(balance, 'ether')}")
    if balance == 0:
        raise SystemExit("Deployer has no PHRS for gas. Fund it from the faucet first.")

    # 1. TestUSD with 1,000,000 TUSD minted to the deployer.
    print("\nDeploying TestUSD ...")
    token_abi, token_bin = c.compile_contract("TestUSD.sol", "TestUSD")
    initial_supply = c.to_base_units("1000000")
    token_addr, token_rcpt = c.deploy_contract(w3, deployer, token_abi, token_bin, initial_supply)
    print(f"  TestUSD       : {token_addr}")
    print(f"  tx            : {c.explorer_tx(token_rcpt.transactionHash)}")

    # 2. PaymentLedger.
    print("\nDeploying PaymentLedger ...")
    ledger_abi, ledger_bin = c.compile_contract("PaymentLedger.sol", "PaymentLedger")
    ledger_addr, ledger_rcpt = c.deploy_contract(w3, deployer, ledger_abi, ledger_bin)
    print(f"  PaymentLedger : {ledger_addr}")
    print(f"  tx            : {c.explorer_tx(ledger_rcpt.transactionHash)}")

    # 3. Seller / payee address.
    pay_to = c.env("PAY_TO_ADDRESS")
    if not pay_to:
        seller = Account.create()
        pay_to = seller.address
        print(f"\nGenerated seller (payee) address: {pay_to}")
        print("  (testnet receive-only; its key is intentionally not stored)")

    c.update_env(
        {
            "TUSD_ADDRESS": token_addr,
            "LEDGER_ADDRESS": ledger_addr,
            "PAY_TO_ADDRESS": pay_to,
        }
    )
    print("\nSaved TUSD_ADDRESS / LEDGER_ADDRESS / PAY_TO_ADDRESS to .env.")
    print("Next: start the facilitator and server, then run agent_pay.py.")


if __name__ == "__main__":
    main()
