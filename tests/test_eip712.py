#!/usr/bin/env python3
"""Offline self-check for the EIP-712 / EIP-3009 signing path.

No chain or network access is required beyond solc download. It verifies that:

  1. The contracts compile.
  2. The EIP-712 digest produced by eth_account (what the agent signs) exactly
     matches the digest TestUSD computes on-chain (domain + struct hash). If these
     ever diverge, settlement would revert with "invalid signature".
  3. A signature recovers back to the signer (what the facilitator checks).

Run:
    python tests/test_eip712.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eth_abi import encode
from eth_account import Account
from eth_account.messages import _hash_eip191_message, encode_typed_data
from eth_utils import keccak
from web3 import Web3

import _common as c


def contract_digest(token, chain_id, frm, to, value, va, vb, nonce_hex):
    """Reproduce exactly what TestUSD.sol computes for the signature digest."""
    domain_typehash = keccak(
        text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    )
    domain_separator = keccak(
        encode(
            ["bytes32", "bytes32", "bytes32", "uint256", "address"],
            [domain_typehash, keccak(text="TestUSD"), keccak(text="2"), chain_id,
             Web3.to_checksum_address(token)],
        )
    )
    type_hash = keccak(
        text="TransferWithAuthorization(address from,address to,uint256 value,"
        "uint256 validAfter,uint256 validBefore,bytes32 nonce)"
    )
    struct_hash = keccak(
        encode(
            ["bytes32", "address", "address", "uint256", "uint256", "uint256", "bytes32"],
            [type_hash, Web3.to_checksum_address(frm), Web3.to_checksum_address(to),
             value, va, vb, Web3.to_bytes(hexstr=nonce_hex)],
        )
    )
    return keccak(b"\x19\x01" + domain_separator + struct_hash)


def main() -> None:
    # 1. Contracts compile.
    t_abi, t_bin = c.compile_contract("TestUSD.sol", "TestUSD")
    l_abi, l_bin = c.compile_contract("PaymentLedger.sol", "PaymentLedger")
    assert t_bin and l_bin, "compilation produced empty bytecode"
    print("[ok] contracts compile")

    # Fixed test vector.
    chain_id = 688689
    token = "0x000000000000000000000000000000000000dEaD"
    payer = Account.create()
    to = "0x00000000000000000000000000000000000000Ff"
    value = 100000
    va, vb = 1000, 9999999999
    nonce_hex = "0x" + ("ab" * 32)

    typed = c.transfer_authorization_typed_data(
        token, chain_id, payer.address, to, value, va, vb, nonce_hex
    )
    signable = encode_typed_data(full_message=typed)

    # 2. eth_account digest == on-chain digest.
    lib_digest = _hash_eip191_message(signable)
    sol_digest = contract_digest(token, chain_id, payer.address, to, value, va, vb, nonce_hex)
    assert lib_digest == sol_digest, (
        f"digest mismatch!\n  eth_account: {lib_digest.hex()}\n  contract:    {sol_digest.hex()}"
    )
    print(f"[ok] EIP-712 digest matches contract: 0x{lib_digest.hex()}")

    # 3. Signature recovers to the signer.
    signed = payer.sign_message(signable)
    recovered = Account.recover_message(signable, signature=signed.signature)
    assert recovered == payer.address, f"recover mismatch: {recovered} != {payer.address}"
    print(f"[ok] signature recovers to signer: {recovered}")

    print("\nAll self-checks passed.")


if __name__ == "__main__":
    main()
