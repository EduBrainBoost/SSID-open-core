// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title LicenseRegistry
 * @author SSID Protocol
 * @notice On-chain registry for module licenses. Tracks which modules are
 *         registered, their developer addresses, and fee basis points.
 * @dev Non-custodial: this contract never holds or routes fees. Fee routing
 *      is handled by LicenseFeeRouter which reads from this registry.
 *      Fees ultimately flow through the existing FeeDistribution.sol contract.
 *
 *      Module IDs are stored as bytes32 (keccak256 of the human-readable moduleId
 *      string) to enable O(1) lookup while preserving the original string in the
 *      struct for off-chain consumers.
 */
contract LicenseRegistry is AccessControl {
    // -------------------------------------------------------------------------
    // Roles
    // -------------------------------------------------------------------------

    /// @notice Role that can register and deactivate modules
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");

    // -------------------------------------------------------------------------
    // Types
    // -------------------------------------------------------------------------

    /**
     * @notice Represents a registered module license.
     * @param moduleId      Human-readable module identifier (e.g. "ssid.kyc.basic")
     * @param developer     Address of the module developer (receives reward share)
     * @param feeBps        Fee in basis points (max 10000 = 100%)
     * @param active        Whether the module is currently active
     * @param registeredAt  Block timestamp when the module was registered
     */
    struct ModuleLicense {
        string  moduleId;
        address developer;
        uint16  feeBps;
        bool    active;
        uint256 registeredAt;
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    /// @dev moduleKey (keccak256 of moduleId) => ModuleLicense
    mapping(bytes32 => ModuleLicense) public licenses;

    /// @dev Array of all registered module keys for enumeration
    bytes32[] private _moduleKeys;

    /// @dev Track whether a key has been registered (prevents duplicate push)
    mapping(bytes32 => bool) private _keyExists;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a new module is registered
    /// @param moduleKey   keccak256 hash of the moduleId string
    /// @param moduleId    Human-readable module identifier
    /// @param developer   Developer address
    /// @param feeBps      Fee in basis points
    event ModuleRegistered(
        bytes32 indexed moduleKey,
        string  moduleId,
        address indexed developer,
        uint16  feeBps
    );

    /// @notice Emitted when a module is deactivated
    /// @param moduleKey  keccak256 hash of the moduleId string
    /// @param moduleId   Human-readable module identifier
    event ModuleDeactivated(bytes32 indexed moduleKey, string moduleId);

    // -------------------------------------------------------------------------
    // Errors
    // -------------------------------------------------------------------------

    error ZeroAddress();
    error ModuleAlreadyRegistered(bytes32 moduleKey);
    error ModuleNotFound(bytes32 moduleKey);
    error ModuleAlreadyInactive(bytes32 moduleKey);
    error FeeBpsTooHigh(uint16 feeBps);

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    /**
     * @param admin Address that receives DEFAULT_ADMIN_ROLE and REGISTRAR_ROLE.
     */
    constructor(address admin) {
        if (admin == address(0)) revert ZeroAddress();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REGISTRAR_ROLE, admin);
    }

    // -------------------------------------------------------------------------
    // Registration
    // -------------------------------------------------------------------------

    /**
     * @notice Register a new module license.
     * @param moduleId   Human-readable module identifier (must be unique).
     * @param developer  Address of the module developer.
     * @param feeBps     Fee in basis points (0-10000).
     */
    function registerModule(
        string calldata moduleId,
        address developer,
        uint16  feeBps
    ) external onlyRole(REGISTRAR_ROLE) {
        if (developer == address(0)) revert ZeroAddress();
        if (feeBps > 10_000) revert FeeBpsTooHigh(feeBps);

        bytes32 moduleKey = keccak256(abi.encodePacked(moduleId));
        if (_keyExists[moduleKey]) revert ModuleAlreadyRegistered(moduleKey);

        licenses[moduleKey] = ModuleLicense({
            moduleId:     moduleId,
            developer:    developer,
            feeBps:       feeBps,
            active:       true,
            registeredAt: block.timestamp
        });

        _moduleKeys.push(moduleKey);
        _keyExists[moduleKey] = true;

        emit ModuleRegistered(moduleKey, moduleId, developer, feeBps);
    }

    // -------------------------------------------------------------------------
    // Deactivation
    // -------------------------------------------------------------------------

    /**
     * @notice Deactivate a module license. Does not delete data.
     * @param moduleKey  keccak256 hash of the moduleId string.
     */
    function deactivateModule(bytes32 moduleKey) external onlyRole(REGISTRAR_ROLE) {
        ModuleLicense storage lic = licenses[moduleKey];
        if (!_keyExists[moduleKey]) revert ModuleNotFound(moduleKey);
        if (!lic.active) revert ModuleAlreadyInactive(moduleKey);

        lic.active = false;

        emit ModuleDeactivated(moduleKey, lic.moduleId);
    }

    // -------------------------------------------------------------------------
    // Queries
    // -------------------------------------------------------------------------

    /**
     * @notice Get the full license struct for a module.
     * @param moduleKey  keccak256 hash of the moduleId string.
     * @return license   The ModuleLicense struct.
     */
    function getLicense(bytes32 moduleKey)
        external
        view
        returns (ModuleLicense memory license)
    {
        if (!_keyExists[moduleKey]) revert ModuleNotFound(moduleKey);
        return licenses[moduleKey];
    }

    /**
     * @notice List all active module keys.
     * @dev Returns a dynamically sized array. For large registries, prefer
     *      off-chain indexing via events.
     * @return activeKeys  Array of bytes32 module keys that are currently active.
     */
    function listActiveModules()
        external
        view
        returns (bytes32[] memory activeKeys)
    {
        uint256 total = _moduleKeys.length;

        // First pass: count active modules
        uint256 activeCount = 0;
        for (uint256 i = 0; i < total; i++) {
            if (licenses[_moduleKeys[i]].active) {
                activeCount++;
            }
        }

        // Second pass: populate result array
        activeKeys = new bytes32[](activeCount);
        uint256 idx = 0;
        for (uint256 i = 0; i < total; i++) {
            if (licenses[_moduleKeys[i]].active) {
                activeKeys[idx] = _moduleKeys[i];
                idx++;
            }
        }
    }

    /**
     * @notice Get the total number of registered modules (active + inactive).
     * @return count Total module count.
     */
    function totalModules() external view returns (uint256 count) {
        return _moduleKeys.length;
    }
}
