#!/usr/bin/env python3
"""Full-flow self-test on an in-memory EVM (eth-tester).

This deploys the real contracts and exercises the entire payment path the way it
will run on Pharos, without needing a live chain or testnet PHRS:

  1. Deploy TestUSD + PaymentLedger.
  2. Mint TUSD to the payer (agent).
  3. The payer signs an EIP-3009 authorization off-chain (no gas).
  4. The relayer settles it on-chain via transferWithAuthorization. This is the
     strongest check: it proves the contract's own ecrecover ACCEPTS our
     signature and moves the funds.
  5. The payer records the payment in the PaymentLedger.
  6. Assert balances, ledger totals, and the emitted receipt.

Run:
    python tests/test_e2e_local.py
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import EthereumTesterProvider, Web3

import _common as c

VALUE = 100_000  # 0.10 TUSD in base units
RESOURCE = "/data"


def main() -> None:
    w3 = Web3(EthereumTesterProvider())
    deployer = w3.eth.accounts[0]  # tester-managed, funded, also acts as relayer
    chain_id = w3.eth.chain_id

    # 1. Deploy contracts.
    t_abi, t_bin = c.compile_contract("TestUSD.sol", "TestUSD")
    l_abi, l_bin = c.compile_contract("PaymentLedger.sol", "PaymentLedger")

    tx = w3.eth.contract(abi=t_abi, bytecode=t_bin).constructor(0).transact({"from": deployer})
    tusd_addr = w3.eth.wait_for_transaction_receipt(tx).contractAddress
    tusd = w3.eth.contract(address=tusd_addr, abi=t_abi)

    tx = w3.eth.contract(abi=l_abi, bytecode=l_bin).constructor().transact({"from": deployer})
    ledger_addr = w3.eth.wait_for_transaction_receipt(tx).contractAddress
    ledger = w3.eth.contract(address=ledger_addr, abi=l_abi)
    print("[ok] deployed TestUSD + PaymentLedger")

    # 2. Create a payer (agent) with its own key; fund it with gas and TUSD.
    payer = Account.create()
    seller = Account.create().address
    w3.eth.send_transaction({"from": deployer, "to": payer.address, "value": w3.to_wei(1, "ether")})
    w3.eth.wait_for_transaction_receipt(
        tusd.functions.mint(payer.address, VALUE * 10).transact({"from": deployer})
    )
    assert tusd.functions.balanceOf(payer.address).call() == VALUE * 10
    print("[ok] payer funded with gas and TUSD")

    # 3. Payer signs the EIP-3009 authorization off-chain.
    now = w3.eth.get_block("latest")["timestamp"]
    valid_after, valid_before = now - 60, now + 600
    nonce = "0x" + secrets.token_bytes(32).hex()
    typed = c.transfer_authorization_typed_data(
        tusd_addr, chain_id, payer.address, seller, VALUE, valid_after, valid_before, nonce
    )
    signed = payer.sign_message(encode_typed_data(full_message=typed))
    sig = bytes(signed.signature)
    r, s, v = sig[:32], sig[32:64], sig[64]

    # 4. Relayer settles on-chain (the contract verifies the signature itself).
    tx = tusd.functions.transferWithAuthorization(
        payer.address, seller, VALUE, valid_after, valid_before,
        Web3.to_bytes(hexstr=nonce), v, r, s,
    ).transact({"from": deployer})
    w3.eth.wait_for_transaction_receipt(tx)
    assert tusd.functions.balanceOf(seller).call() == VALUE
    assert tusd.functions.balanceOf(payer.address).call() == VALUE * 9
    assert tusd.functions.authorizationState(payer.address, Web3.to_bytes(hexstr=nonce)).call()
    print("[ok] EIP-3009 transferWithAuthorization settled on-chain (contract accepted signature)")

    # Replay must fail (nonce already used).
    try:
        tusd.functions.transferWithAuthorization(
            payer.address, seller, VALUE, valid_after, valid_before,
            Web3.to_bytes(hexstr=nonce), v, r, s,
        ).transact({"from": deployer})
        raise AssertionError("replay should have reverted")
    except Exception as e:
        if "should have reverted" in str(e):
            raise
    print("[ok] replay of a used nonce is rejected")

    # 5. Payer records the payment on the ledger (raw signed tx, payer pays gas).
    func = ledger.functions.record(
        Web3.to_checksum_address(seller), tusd_addr, VALUE, RESOURCE,
        Web3.to_bytes(hexstr=nonce),
    )
    tx = func.build_transaction(
        {
            "from": payer.address,
            "nonce": w3.eth.get_transaction_count(payer.address),
            "gas": 500_000,
            "gasPrice": w3.eth.gas_price,
            "chainId": chain_id,
        }
    )
    raw = c._raw(payer.sign_transaction(tx))
    rcpt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(raw))

    # 6. Verify ledger state and event.
    assert ledger.functions.totalReceipts().call() == 1
    assert ledger.functions.totalSpent(payer.address, tusd_addr).call() == VALUE
    events = ledger.events.PaymentRecorded().process_receipt(rcpt)
    assert events and events[0]["args"]["receiptId"] == 0
    assert events[0]["args"]["amount"] == VALUE
    receipt = ledger.functions.receiptAt(0).call()
    assert receipt[0] == payer.address and receipt[4] == RESOURCE
    print("[ok] payment recorded on PaymentLedger (receipt #0, totals correct)")

    print("\nFull local end-to-end flow passed.")


if __name__ == "__main__":
    main()
