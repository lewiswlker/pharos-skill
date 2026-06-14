// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title TestUSD - an EIP-3009 capable test stablecoin for the Pharos Atlantic testnet
/// @notice Self-contained ERC-20 (no external imports) that implements EIP-3009
///         `transferWithAuthorization` so that an x402 facilitator can settle
///         gasless, signature-authorized transfers on behalf of a payer.
/// @dev    Decimals are 6 to mirror USDC. The EIP-712 domain uses name "TestUSD"
///         and version "2" so it matches the x402 server's money parser config.
///         Minting is intentionally open: this token is for TESTNET demos only.
contract TestUSD {
    // --- ERC-20 metadata ---
    string public constant name = "TestUSD";
    string public constant symbol = "TUSD";
    uint8 public constant decimals = 6;

    // --- ERC-20 state ---
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    // --- EIP-3009 state ---
    // authorizer => nonce => used
    mapping(address => mapping(bytes32 => bool)) public authorizationState;

    // --- EIP-712 domain ---
    bytes32 public immutable DOMAIN_SEPARATOR;

    bytes32 public constant TRANSFER_WITH_AUTHORIZATION_TYPEHASH =
        keccak256(
            "TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)"
        );

    // --- Events ---
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event AuthorizationUsed(address indexed authorizer, bytes32 indexed nonce);

    constructor(uint256 initialSupply) {
        DOMAIN_SEPARATOR = keccak256(
            abi.encode(
                keccak256(
                    "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
                ),
                keccak256(bytes(name)),
                keccak256(bytes("2")),
                block.chainid,
                address(this)
            )
        );
        if (initialSupply > 0) {
            _mint(msg.sender, initialSupply);
        }
    }

    // --- Standard ERC-20 ---

    function transfer(address to, uint256 value) external returns (bool) {
        _transfer(msg.sender, to, value);
        return true;
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        require(allowed >= value, "TestUSD: allowance exceeded");
        if (allowed != type(uint256).max) {
            allowance[from][msg.sender] = allowed - value;
        }
        _transfer(from, to, value);
        return true;
    }

    /// @notice Open faucet mint. TESTNET ONLY - do not reuse this pattern on mainnet.
    function mint(address to, uint256 value) external {
        _mint(to, value);
    }

    // --- EIP-3009 ---

    /// @notice Execute a transfer that was pre-authorized off-chain via an EIP-712 signature.
    /// @dev    The facilitator (any relayer) submits this and pays the gas; the value and
    ///         recipient are fixed by the payer's signature and cannot be altered.
    function transferWithAuthorization(
        address from,
        address to,
        uint256 value,
        uint256 validAfter,
        uint256 validBefore,
        bytes32 nonce,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external {
        require(block.timestamp > validAfter, "TestUSD: authorization not yet valid");
        require(block.timestamp < validBefore, "TestUSD: authorization expired");
        require(!authorizationState[from][nonce], "TestUSD: authorization used");

        bytes32 structHash = keccak256(
            abi.encode(
                TRANSFER_WITH_AUTHORIZATION_TYPEHASH,
                from,
                to,
                value,
                validAfter,
                validBefore,
                nonce
            )
        );
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", DOMAIN_SEPARATOR, structHash));
        address signer = ecrecover(digest, v, r, s);
        require(signer != address(0) && signer == from, "TestUSD: invalid signature");

        authorizationState[from][nonce] = true;
        emit AuthorizationUsed(from, nonce);

        _transfer(from, to, value);
    }

    // --- Internal ---

    function _transfer(address from, address to, uint256 value) internal {
        require(to != address(0), "TestUSD: transfer to zero address");
        uint256 fromBalance = balanceOf[from];
        require(fromBalance >= value, "TestUSD: balance exceeded");
        unchecked {
            balanceOf[from] = fromBalance - value;
            balanceOf[to] += value;
        }
        emit Transfer(from, to, value);
    }

    function _mint(address to, uint256 value) internal {
        require(to != address(0), "TestUSD: mint to zero address");
        totalSupply += value;
        unchecked {
            balanceOf[to] += value;
        }
        emit Transfer(address(0), to, value);
    }
}
