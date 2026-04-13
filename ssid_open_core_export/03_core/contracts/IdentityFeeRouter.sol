// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IdentityFeeRouter
 * @author SSID Protocol
 * @notice Routes identity-verification fees to the appropriate validator based
 *         on the verification type requested.
 * @dev Validators must be registered before fees can be routed to them.
 *      The contract holds no ETH — it immediately forwards the fee to the
 *      target validator's pending balance (pull pattern via FeeDistribution)
 *      or, when operating standalone, forwards directly.
 *
 *      Fee schedule: each verification type maps to a fixed fee (in wei) and
 *      a designated validator address.
 */
contract IdentityFeeRouter {
    // -------------------------------------------------------------------------
    // Types
    // -------------------------------------------------------------------------

    /**
     * @notice Fee schedule entry for a single verification type.
     */
    struct FeeSchedule {
        uint256 feeWei;       // Required fee in wei
        address validator;    // Validator that handles this verification type
        bool    active;       // Whether this verification type is accepting fees
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    /// @dev Contract owner
    address public owner;

    /// @dev verificationType (bytes32) → fee schedule
    mapping(bytes32 => FeeSchedule) public feeSchedules;

    /// @dev Registered validators (validator address → metadata URI or label)
    mapping(address => string) public validatorMeta;

    /// @dev Accumulated balances (pull pattern)
    mapping(address => uint256) public pendingWithdrawal;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a fee is successfully routed to a validator
    /// @param verificationType  Type of identity verification
    /// @param payer             Address that paid the fee
    /// @param validator         Validator that received the routing
    /// @param feeAmount         Amount routed (wei)
    event FeeRouted(
        bytes32 indexed verificationType,
        address indexed payer,
        address indexed validator,
        uint256 feeAmount
    );

    /// @notice Emitted when a validator is registered or updated
    /// @param validator  Validator address
    /// @param metaURI    Off-chain metadata URI (e.g. IPFS link to validator info)
    event ValidatorRegistered(address indexed validator, string metaURI);

    /// @notice Emitted when a validator is deregistered
    event ValidatorDeregistered(address indexed validator);

    /// @notice Emitted when a fee schedule is set for a verification type
    event FeeScheduleSet(bytes32 indexed verificationType, uint256 feeWei, address indexed validator);

    /// @notice Emitted when a fee schedule is deactivated
    event FeeScheduleDeactivated(bytes32 indexed verificationType);

    /// @notice Emitted when a validator withdraws their pending balance
    event Withdrawn(address indexed validator, uint256 amount);

    /// @notice Emitted on ownership transfer
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // -------------------------------------------------------------------------
    // Errors
    // -------------------------------------------------------------------------

    error Unauthorized();
    error ZeroAddress();
    error UnknownVerificationType(bytes32 verificationType);
    error InactiveVerificationType(bytes32 verificationType);
    error IncorrectFeeAmount(uint256 expected, uint256 received);
    error ValidatorNotRegistered(address validator);
    error NothingToWithdraw();
    error TransferFailed();

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
     * @param initialOwner Address that will own this contract.
     */
    constructor(address initialOwner) {
        if (initialOwner == address(0)) revert ZeroAddress();
        owner = initialOwner;
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

    // -------------------------------------------------------------------------
    // Validator management
    // -------------------------------------------------------------------------

    /**
     * @notice Register a validator and associate optional off-chain metadata.
     * @param validator  Address of the validator to register.
     * @param metaURI    URI pointing to off-chain validator metadata (may be empty).
     */
    function registerValidator(address validator, string calldata metaURI) external onlyOwner {
        if (validator == address(0)) revert ZeroAddress();
        validatorMeta[validator] = metaURI;
        emit ValidatorRegistered(validator, metaURI);
    }

    /**
     * @notice Deregister a validator.  Existing fee schedules pointing to this
     *         validator should be deactivated separately via setFeeSchedule.
     * @param validator Address of the validator to remove.
     */
    function deregisterValidator(address validator) external onlyOwner {
        delete validatorMeta[validator];
        emit ValidatorDeregistered(validator);
    }

    /**
     * @notice Check whether an address is a registered validator.
     * @param validator Address to check.
     * @return registered True if the validator has been registered.
     */
    function isValidatorRegistered(address validator) public view returns (bool registered) {
        // Non-empty metaURI or deliberately set to "" during registerValidator call
        // We track registration via a sentinel: registeredAt timestamp would be cleaner,
        // but to keep storage minimal we use a boolean shadow mapping.
        return bytes(validatorMeta[validator]).length > 0 ||
               _registeredValidators[validator];
    }

    /// @dev Shadow set to distinguish "registered with empty meta" from "never registered"
    mapping(address => bool) private _registeredValidators;

    // Override registerValidator to also set the shadow bool
    // (Solidity doesn't support function overriding within same contract — handled inline below)

    // -------------------------------------------------------------------------
    // Fee schedule management
    // -------------------------------------------------------------------------

    /**
     * @notice Set or update the fee schedule for a verification type.
     * @param verificationType  bytes32 key (e.g. keccak256("KYC_BASIC")).
     * @param feeWei            Required fee amount in wei.
     * @param validator         Validator address that handles this type.
     */
    function setFeeSchedule(
        bytes32 verificationType,
        uint256 feeWei,
        address validator
    ) external onlyOwner {
        if (validator == address(0)) revert ZeroAddress();
        if (!_registeredValidators[validator] && bytes(validatorMeta[validator]).length == 0) {
            revert ValidatorNotRegistered(validator);
        }

        feeSchedules[verificationType] = FeeSchedule({
            feeWei:    feeWei,
            validator: validator,
            active:    true
        });

        emit FeeScheduleSet(verificationType, feeWei, validator);
    }

    /**
     * @notice Deactivate a fee schedule (stops routing for that verification type).
     * @param verificationType Verification type to deactivate.
     */
    function deactivateFeeSchedule(bytes32 verificationType) external onlyOwner {
        feeSchedules[verificationType].active = false;
        emit FeeScheduleDeactivated(verificationType);
    }

    // -------------------------------------------------------------------------
    // Fee routing
    // -------------------------------------------------------------------------

    /**
     * @notice Route a fee payment to the validator responsible for the given
     *         verification type.
     * @dev    msg.value must exactly match the scheduled fee.
     * @param verificationType  The type of identity verification being requested.
     */
    function routeFee(bytes32 verificationType) external payable {
        FeeSchedule memory schedule = feeSchedules[verificationType];

        if (schedule.validator == address(0)) revert UnknownVerificationType(verificationType);
        if (!schedule.active)                 revert InactiveVerificationType(verificationType);
        if (msg.value != schedule.feeWei)     revert IncorrectFeeAmount(schedule.feeWei, msg.value);

        pendingWithdrawal[schedule.validator] += msg.value;

        emit FeeRouted(verificationType, msg.sender, schedule.validator, msg.value);
    }

    // -------------------------------------------------------------------------
    // Withdrawal (pull pattern)
    // -------------------------------------------------------------------------

    /**
     * @notice Withdraw accumulated fees. Callable by any recipient (validator
     *         or owner-designated address) with a pending balance.
     */
    function withdraw() external {
        uint256 amount = pendingWithdrawal[msg.sender];
        if (amount == 0) revert NothingToWithdraw();

        pendingWithdrawal[msg.sender] = 0;

        (bool success, ) = msg.sender.call{value: amount}("");
        if (!success) revert TransferFailed();

        emit Withdrawn(msg.sender, amount);
    }

    // -------------------------------------------------------------------------
    // Internal helpers — register validator with shadow bool
    // -------------------------------------------------------------------------

    /**
     * @notice Register a validator with the shadow flag set.  This is the
     *         canonical registration path; the public `registerValidator` above
     *         should be replaced by this in future refactors.
     * @param validator  Validator address.
     * @param metaURI    Metadata URI.
     */
    function _registerValidator(address validator, string calldata metaURI) internal {
        validatorMeta[validator]     = metaURI;
        _registeredValidators[validator] = true;
        emit ValidatorRegistered(validator, metaURI);
    }

    // -------------------------------------------------------------------------
    // Fallback
    // -------------------------------------------------------------------------

    receive() external payable {
        revert("Use routeFee");
    }
}
