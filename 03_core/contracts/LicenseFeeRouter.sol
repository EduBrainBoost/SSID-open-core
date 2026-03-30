// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title LicenseFeeRouter
 * @author SSID Protocol
 * @notice Routes license fees: 2% to the system pool (via FeeDistribution),
 *         1% directly to the module developer. Non-custodial design — fees are
 *         forwarded instantly and never held by this contract.
 * @dev Integration points:
 *      - LicenseRegistry: developer address lookup per moduleKey
 *      - FeeDistribution: receives the system share (2%)
 *
 *      Fee math (basis points of the incoming amount):
 *        systemBps   = 200  (2.00%)
 *        developerBps = 100  (1.00%)
 *        remainder is returned to the caller (97%)
 *
 *      This contract is intentionally minimal. It holds no ETH between
 *      transactions and maintains no balances.
 */

// Minimal interface for LicenseRegistry — avoids importing the full contract
interface ILicenseRegistry {
    struct ModuleLicense {
        string  moduleId;
        address developer;
        uint16  feeBps;
        bool    active;
        uint256 registeredAt;
    }

    function getLicense(bytes32 moduleKey)
        external
        view
        returns (ModuleLicense memory);
}

// Minimal interface for FeeDistribution — system share deposit
interface IFeeDistribution {
    function distributeFee(
        bytes32 serviceType,
        address creator,
        address validator
    ) external payable;
}

contract LicenseFeeRouter {
    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    uint256 public constant BASIS_POINTS   = 10_000;
    uint256 public constant SYSTEM_BPS     = 200;     // 2%
    uint256 public constant DEVELOPER_BPS  = 100;     // 1%

    /// @dev Service type key used when forwarding to FeeDistribution
    bytes32 public constant LICENSE_SERVICE_TYPE = keccak256("LICENSE_FEE");

    // -------------------------------------------------------------------------
    // Immutable references
    // -------------------------------------------------------------------------

    /// @notice LicenseRegistry used for developer address lookups
    ILicenseRegistry public immutable licenseRegistry;

    /// @notice FeeDistribution contract that receives the system share
    address public immutable feeDistribution;

    /// @notice Contract owner (can update configuration in future versions)
    address public immutable owner;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a license fee is successfully routed
    /// @param moduleKey      keccak256 of the module identifier
    /// @param payer          Address that paid the fee
    /// @param totalAmount    Total amount received
    /// @param systemAmount   Amount forwarded to FeeDistribution (2%)
    /// @param developerAmount Amount sent directly to developer (1%)
    event FeeRouted(
        bytes32 indexed moduleKey,
        address indexed payer,
        uint256 totalAmount,
        uint256 systemAmount,
        uint256 developerAmount
    );

    /// @notice Emitted when a developer reward is paid out
    /// @param moduleKey  keccak256 of the module identifier
    /// @param developer  Developer address that received the reward
    /// @param amount     Amount sent (wei)
    event DeveloperRewardPaid(
        bytes32 indexed moduleKey,
        address indexed developer,
        uint256 amount
    );

    // -------------------------------------------------------------------------
    // Errors
    // -------------------------------------------------------------------------

    error ZeroAddress();
    error ZeroAmount();
    error ModuleNotActive(bytes32 moduleKey);
    error InsufficientValue(uint256 required, uint256 sent);
    error TransferFailed(address recipient, uint256 amount);
    error SystemDepositFailed();

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    /**
     * @param _licenseRegistry  Address of the deployed LicenseRegistry.
     * @param _feeDistribution  Address of the deployed FeeDistribution.
     * @param _owner            Contract owner.
     */
    constructor(
        address _licenseRegistry,
        address _feeDistribution,
        address _owner
    ) {
        if (_licenseRegistry == address(0)) revert ZeroAddress();
        if (_feeDistribution == address(0)) revert ZeroAddress();
        if (_owner == address(0)) revert ZeroAddress();

        licenseRegistry = ILicenseRegistry(_licenseRegistry);
        feeDistribution = _feeDistribution;
        owner           = _owner;
    }

    // -------------------------------------------------------------------------
    // Fee routing
    // -------------------------------------------------------------------------

    /**
     * @notice Route a license fee for the given module.
     * @dev Splits msg.value:
     *        2% (SYSTEM_BPS)    -> forwarded to FeeDistribution contract
     *        1% (DEVELOPER_BPS) -> sent directly to module developer
     *        97% remainder      -> returned to caller
     *
     *      Non-custodial: no ETH is retained by this contract.
     *
     * @param moduleKey  keccak256 hash of the module identifier.
     * @param amount     Expected fee amount (must match msg.value).
     */
    function routeFee(bytes32 moduleKey, uint256 amount) external payable {
        if (amount == 0) revert ZeroAmount();
        if (msg.value < amount) revert InsufficientValue(amount, msg.value);

        // Lookup module license
        ILicenseRegistry.ModuleLicense memory lic = licenseRegistry.getLicense(moduleKey);
        if (!lic.active) revert ModuleNotActive(moduleKey);
        if (lic.developer == address(0)) revert ZeroAddress();

        // Calculate splits
        uint256 systemAmount    = (amount * SYSTEM_BPS)    / BASIS_POINTS;
        uint256 developerAmount = (amount * DEVELOPER_BPS) / BASIS_POINTS;

        // Forward system share to FeeDistribution (non-custodial pass-through)
        if (systemAmount > 0) {
            (bool sysOk, ) = feeDistribution.call{value: systemAmount}(
                abi.encodeWithSignature(
                    "distributeFee(bytes32,address,address)",
                    LICENSE_SERVICE_TYPE,
                    lic.developer,
                    owner       // validator slot receives system share
                )
            );
            if (!sysOk) revert SystemDepositFailed();
        }

        // Send developer reward directly — non-custodial, never held
        if (developerAmount > 0) {
            (bool devOk, ) = lic.developer.call{value: developerAmount}("");
            if (!devOk) revert TransferFailed(lic.developer, developerAmount);

            emit DeveloperRewardPaid(moduleKey, lic.developer, developerAmount);
        }

        // Return remainder to caller
        uint256 remainder = amount - systemAmount - developerAmount;
        if (remainder > 0) {
            (bool refundOk, ) = msg.sender.call{value: remainder}("");
            if (!refundOk) revert TransferFailed(msg.sender, remainder);
        }

        // Return any excess msg.value beyond amount
        uint256 excess = msg.value - amount;
        if (excess > 0) {
            (bool excessOk, ) = msg.sender.call{value: excess}("");
            if (!excessOk) revert TransferFailed(msg.sender, excess);
        }

        emit FeeRouted(moduleKey, msg.sender, amount, systemAmount, developerAmount);
    }

    // -------------------------------------------------------------------------
    // Fallback — reject accidental ETH
    // -------------------------------------------------------------------------

    receive() external payable {
        revert("Use routeFee");
    }
}
