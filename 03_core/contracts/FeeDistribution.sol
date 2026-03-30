// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title FeeDistribution
 * @author SSID Protocol
 * @notice Distributes incoming fees between platform, creators, and validators
 *         according to configurable ratios per service type.
 * @dev Uses the pull-over-push (withdrawal) pattern to prevent reentrancy and
 *      failed-transfer DoS. All basis-point ratios must sum to 10 000 (100%).
 *
 *      Basis points: 1 bp = 0.01 %, 10 000 bp = 100 %.
 */
contract FeeDistribution {
    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    uint256 public constant BASIS_POINTS = 10_000;

    // -------------------------------------------------------------------------
    // Types
    // -------------------------------------------------------------------------

    /**
     * @notice Split ratios (in basis points) for a given service type.
     *         platformBps + creatorBps + validatorBps MUST equal 10 000.
     */
    struct FeeRatio {
        uint16 platformBps;
        uint16 creatorBps;
        uint16 validatorBps;
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    /// @dev Contract owner
    address public owner;

    /// @dev Platform treasury address — receives platform share
    address public platformTreasury;

    /// @dev serviceType (bytes32 key) → fee split ratios
    mapping(bytes32 => FeeRatio) public feeRatios;

    /// @dev Accumulated withdrawable balances (pull pattern)
    mapping(address => uint256) public pendingWithdrawal;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a fee payment is received and split
    /// @param serviceType  Identifier of the service type
    /// @param payer        Address that sent the fee
    /// @param totalAmount  Total wei received
    event FeeReceived(bytes32 indexed serviceType, address indexed payer, uint256 totalAmount);

    /// @notice Emitted when fee shares are credited to recipients
    /// @param serviceType      Identifier of the service type
    /// @param platformAmount   Amount credited to platform treasury
    /// @param creatorAmount    Amount credited to creator
    /// @param validatorAmount  Amount credited to validator
    /// @param creator          Creator recipient address
    /// @param validator        Validator recipient address
    event FeeDistributed(
        bytes32 indexed serviceType,
        uint256 platformAmount,
        uint256 creatorAmount,
        uint256 validatorAmount,
        address indexed creator,
        address indexed validator
    );

    /// @notice Emitted when an account withdraws its pending balance
    /// @param recipient Address that withdrew
    /// @param amount    Amount withdrawn (wei)
    event Withdrawn(address indexed recipient, uint256 amount);

    /// @notice Emitted when fee ratios are set for a service type
    event FeeRatioSet(bytes32 indexed serviceType, uint16 platformBps, uint16 creatorBps, uint16 validatorBps);

    /// @notice Emitted on ownership transfer
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // -------------------------------------------------------------------------
    // Errors
    // -------------------------------------------------------------------------

    error Unauthorized();
    error InvalidRatioSum(uint256 sum);
    error ZeroAddress();
    error NothingToWithdraw();
    error TransferFailed();
    error UnknownServiceType(bytes32 serviceType);

    // -------------------------------------------------------------------------
    // Modifiers
    // -------------------------------------------------------------------------

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    /**
     * @param initialOwner     Address that owns this contract.
     * @param _platformTreasury Address that receives the platform share of fees.
     */
    constructor(address initialOwner, address _platformTreasury) {
        if (initialOwner == address(0) || _platformTreasury == address(0)) revert ZeroAddress();
        owner             = initialOwner;
        platformTreasury  = _platformTreasury;
        emit OwnershipTransferred(address(0), initialOwner);
    }

    // -------------------------------------------------------------------------
    // Owner management
    // -------------------------------------------------------------------------

    /**
     * @notice Transfer ownership to a new address.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        address previous = owner;
        owner = newOwner;
        emit OwnershipTransferred(previous, newOwner);
    }

    /**
     * @notice Update the platform treasury address.
     */
    function setPlatformTreasury(address _platformTreasury) external onlyOwner {
        if (_platformTreasury == address(0)) revert ZeroAddress();
        platformTreasury = _platformTreasury;
    }

    // -------------------------------------------------------------------------
    // Fee ratio configuration
    // -------------------------------------------------------------------------

    /**
     * @notice Set the fee split ratios for a service type.
     * @param serviceType   A bytes32 identifier for the service (e.g. keccak256("VERIFICATION")).
     * @param platformBps   Platform share in basis points.
     * @param creatorBps    Creator share in basis points.
     * @param validatorBps  Validator share in basis points.
     *                      Sum of three values must equal 10 000.
     */
    function setFeeRatio(
        bytes32 serviceType,
        uint16  platformBps,
        uint16  creatorBps,
        uint16  validatorBps
    ) external onlyOwner {
        uint256 total = uint256(platformBps) + uint256(creatorBps) + uint256(validatorBps);
        if (total != BASIS_POINTS) revert InvalidRatioSum(total);

        feeRatios[serviceType] = FeeRatio(platformBps, creatorBps, validatorBps);
        emit FeeRatioSet(serviceType, platformBps, creatorBps, validatorBps);
    }

    // -------------------------------------------------------------------------
    // Fee distribution
    // -------------------------------------------------------------------------

    /**
     * @notice Accept a fee payment and split it among platform, creator, and validator.
     * @dev The msg.value is split according to the ratios for `serviceType`.
     *      Dust (due to integer division) accrues to the platform share.
     * @param serviceType  Service type key (must have ratios configured).
     * @param creator      Address of the content creator receiving their share.
     * @param validator    Address of the validator receiving their share.
     */
    function distributeFee(
        bytes32 serviceType,
        address creator,
        address validator
    ) external payable {
        FeeRatio memory ratio = feeRatios[serviceType];
        // A ratio with all zeros means it was never configured
        if (ratio.platformBps == 0 && ratio.creatorBps == 0 && ratio.validatorBps == 0) {
            revert UnknownServiceType(serviceType);
        }
        if (creator   == address(0)) revert ZeroAddress();
        if (validator == address(0)) revert ZeroAddress();

        uint256 total = msg.value;

        uint256 creatorAmt    = (total * ratio.creatorBps)   / BASIS_POINTS;
        uint256 validatorAmt  = (total * ratio.validatorBps) / BASIS_POINTS;
        // Dust goes to platform
        uint256 platformAmt   = total - creatorAmt - validatorAmt;

        pendingWithdrawal[platformTreasury] += platformAmt;
        pendingWithdrawal[creator]          += creatorAmt;
        pendingWithdrawal[validator]        += validatorAmt;

        emit FeeReceived(serviceType, msg.sender, total);
        emit FeeDistributed(serviceType, platformAmt, creatorAmt, validatorAmt, creator, validator);
    }

    // -------------------------------------------------------------------------
    // Withdrawal (pull pattern)
    // -------------------------------------------------------------------------

    /**
     * @notice Withdraw all pending balance accrued for the caller.
     * @dev Uses checks-effects-interactions pattern to prevent reentrancy.
     */
    function withdraw() external {
        uint256 amount = pendingWithdrawal[msg.sender];
        if (amount == 0) revert NothingToWithdraw();

        pendingWithdrawal[msg.sender] = 0;

        (bool success, ) = msg.sender.call{value: amount}("");
        if (!success) revert TransferFailed();

        emit Withdrawn(msg.sender, amount);
    }

    /**
     * @notice View the pending withdrawal balance of any address.
     * @param account Address to query.
     * @return balance Amount available for withdrawal.
     */
    function pendingBalance(address account) external view returns (uint256 balance) {
        return pendingWithdrawal[account];
    }

    // -------------------------------------------------------------------------
    // Fallback — reject accidental ETH sends without calldata
    // -------------------------------------------------------------------------

    receive() external payable {
        revert("Use distributeFee");
    }
}
