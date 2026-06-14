#!/usr/bin/env python3
"""Generate a fresh TESTNET-ONLY wallet and store its private key in .env.

Security model:
  - The key is generated locally with OS entropy and NEVER leaves this machine.
  - The private key is written only to .env, which is git-ignored.
  - Only the public address is printed to the console.

Usage:
    python scripts/new_wallet.py          # generate; refuses to overwrite an existing key
    python scripts/new_wallet.py --force  # overwrite an existing PRIVATE_KEY in .env

WARNING: Never use a wallet that holds real funds. This is for the Pharos
Atlantic testnet only.
"""
import secrets
import sys
from pathlib import Path

try:
    from eth_account import Account
except ImportError:
    sys.exit("Missing dependency. Run: pip install -r requirements.txt")

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
EXAMPLE_PATH = Path(__file__).resolve().parent.parent / ".env.example"


def read_env(path: Path) -> dict:
    data = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            data[k.strip()] = v.strip()
    return data


def main() -> None:
    force = "--force" in sys.argv

    existing = read_env(ENV_PATH)
    if existing.get("PRIVATE_KEY") and not force:
        print("A PRIVATE_KEY already exists in .env.")
        print("Refusing to overwrite. Re-run with --force only if you are sure.")
        sys.exit(1)

    # Seed the base .env from .env.example on first run so config keys are present.
    if not ENV_PATH.exists() and EXAMPLE_PATH.exists():
        ENV_PATH.write_text(EXAMPLE_PATH.read_text())
        existing = read_env(ENV_PATH)

    acct = Account.create(secrets.token_bytes(32))
    private_key = acct.key.hex()
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    # Update or append PRIVATE_KEY in .env without touching other lines.
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("PRIVATE_KEY="):
            lines[i] = f"PRIVATE_KEY={private_key}"
            found = True
            break
    if not found:
        lines.append(f"PRIVATE_KEY={private_key}")
    ENV_PATH.write_text("\n".join(lines) + "\n")

    print("New testnet wallet generated.")
    print(f"  Address : {acct.address}")
    print(f"  Stored  : {ENV_PATH} (PRIVATE_KEY, git-ignored)")
    print()
    print("Next steps:")
    print("  1. Share ONLY the address above to receive testnet PHRS from the faucet.")
    print("  2. Never share or commit the private key.")


if __name__ == "__main__":
    main()
