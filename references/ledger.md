# On-chain spend ledger

`PaymentLedger.sol` turns a stream of x402 micropayments into a queryable,
auditable on-chain history. After each settlement the agent calls `record(...)`,
which stores an immutable receipt and emits a `PaymentRecorded` event.

## What a receipt holds

```solidity
struct Receipt {
    address payer;       // who paid
    address payee;       // who received it
    address token;       // settlement token (TestUSD)
    uint256 amount;      // base units
    string  resource;    // e.g. "/data"
    bytes32 paymentRef;  // the x402 authorization nonce
    uint256 timestamp;   // block time
}
```

## Reading the ledger

Any web3 client can query the contract at `LEDGER_ADDRESS`. Examples with
`web3.py`:

```python
import _common as c
from web3 import Web3

w3 = c.get_web3()
ledger = w3.eth.contract(
    address=Web3.to_checksum_address(c.require_env("LEDGER_ADDRESS")),
    abi=c.ledger_abi(),
)

# Cumulative spend by this agent in TestUSD
agent = c.get_account("PRIVATE_KEY").address
token = c.require_env("TUSD_ADDRESS")
print(c.to_human(ledger.functions.totalSpent(agent, token).call()), "TUSD")

# Total receipts and the most recent one
n = ledger.functions.totalReceipts().call()
print("receipts:", n)
if n:
    print(ledger.functions.receiptAt(n - 1).call())

# All receipts for this payer
count = ledger.functions.receiptCountOf(agent).call()
for i in range(count):
    print(ledger.functions.receiptOf(agent, i).call())
```

## Available views

| View | Returns |
| --- | --- |
| `totalSpent(payer, token)` | Cumulative amount a payer spent in a token |
| `totalReceipts()` | Global receipt count |
| `receiptAt(index)` | Receipt from the global log |
| `receiptCountOf(payer)` | Number of receipts for a payer |
| `receiptOf(payer, index)` | A specific receipt for a payer |

## Events

Index off `PaymentRecorded(payer, payee, token, amount, resource, paymentRef, receiptId)`
to build dashboards or reconcile against the local budget tracker.
