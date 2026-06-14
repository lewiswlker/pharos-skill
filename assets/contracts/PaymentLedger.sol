// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title PaymentLedger - an on-chain spending ledger for x402 payments
/// @notice After an AI agent settles an x402 payment, it records a receipt here.
///         This turns a stream of micropayments into a queryable, auditable
///         on-chain spending history (per-agent budgets, totals, and an audit trail).
/// @dev    Anyone can record their own payments (msg.sender is the payer). The
///         contract never moves funds; it only stores immutable receipts.
contract PaymentLedger {
    struct Receipt {
        address payer;       // who paid (msg.sender)
        address payee;       // who received the payment
        address token;       // ERC-20 used for settlement (e.g. TestUSD)
        uint256 amount;      // amount in token base units
        string resource;     // identifier of the paid resource (e.g. "GET /data")
        bytes32 paymentRef;  // x402 payment nonce / settlement reference
        uint256 timestamp;   // block timestamp of the record
    }

    // payer => receipts
    mapping(address => Receipt[]) private _receiptsByPayer;
    // payer => token => cumulative amount spent
    mapping(address => mapping(address => uint256)) public totalSpent;

    // global, append-only log
    Receipt[] private _allReceipts;

    event PaymentRecorded(
        address indexed payer,
        address indexed payee,
        address indexed token,
        uint256 amount,
        string resource,
        bytes32 paymentRef,
        uint256 receiptId
    );

    /// @notice Record a settled payment. Emits an event and stores the receipt.
    /// @return receiptId Global index of the stored receipt.
    function record(
        address payee,
        address token,
        uint256 amount,
        string calldata resource,
        bytes32 paymentRef
    ) external returns (uint256 receiptId) {
        Receipt memory rcpt = Receipt({
            payer: msg.sender,
            payee: payee,
            token: token,
            amount: amount,
            resource: resource,
            paymentRef: paymentRef,
            timestamp: block.timestamp
        });

        _receiptsByPayer[msg.sender].push(rcpt);
        _allReceipts.push(rcpt);
        totalSpent[msg.sender][token] += amount;

        receiptId = _allReceipts.length - 1;
        emit PaymentRecorded(msg.sender, payee, token, amount, resource, paymentRef, receiptId);
    }

    // --- Views ---

    function receiptCountOf(address payer) external view returns (uint256) {
        return _receiptsByPayer[payer].length;
    }

    function receiptOf(address payer, uint256 index) external view returns (Receipt memory) {
        require(index < _receiptsByPayer[payer].length, "PaymentLedger: index out of range");
        return _receiptsByPayer[payer][index];
    }

    function totalReceipts() external view returns (uint256) {
        return _allReceipts.length;
    }

    function receiptAt(uint256 index) external view returns (Receipt memory) {
        require(index < _allReceipts.length, "PaymentLedger: index out of range");
        return _allReceipts[index];
    }
}
