// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title CodexRegistry
 * @notice On-chain registry for SSID Codex modules (SoT artifacts).
 * @dev Non-custodial: stores only SHA3-256 hashes of module manifests.
 *      No PII on-chain. Version: v4.1.0
 *
 * ROOT-24-LOCK | Module: 16_codex
 * Evidence strategy: hash_manifest_only
 */
contract CodexRegistry {
    // ---------------------------------------------------------------
    // Types
    // ---------------------------------------------------------------

    struct ModuleEntry {
        bytes32 manifestHash;   // SHA3-256 of the module manifest JSON
        bytes32 contentHash;    // SHA3-256 of the module content bundle
        string  version;        // Semantic version string (e.g. "4.1.0")
        uint256 registeredAt;   // Block timestamp of registration
        address registrant;     // Address that registered the module
        bool    active;         // Whether the module is currently active
    }

    // ---------------------------------------------------------------
    // State
    // ---------------------------------------------------------------

    /// @notice Module ID (bytes32) => ModuleEntry
    mapping(bytes32 => ModuleEntry) private _modules;

    /// @notice Ordered list of all registered module IDs
    bytes32[] private _moduleIds;

    /// @notice Governance address — only this address can register/deactivate
    address public governance;

    /// @notice Contract version
    string public constant VERSION = "4.1.0";

    // ---------------------------------------------------------------
    // Events
    // ---------------------------------------------------------------

    event ModuleRegistered(
        bytes32 indexed moduleId,
        bytes32 manifestHash,
        bytes32 contentHash,
        string  version,
        address indexed registrant
    );

    event ModuleDeactivated(bytes32 indexed moduleId, address indexed actor);
    event ModuleReactivated(bytes32 indexed moduleId, address indexed actor);
    event GovernanceTransferred(address indexed previous, address indexed next);

    // ---------------------------------------------------------------
    // Errors
    // ---------------------------------------------------------------

    error NotGovernance();
    error ModuleAlreadyExists(bytes32 moduleId);
    error ModuleNotFound(bytes32 moduleId);
    error InvalidHash();

    // ---------------------------------------------------------------
    // Modifiers
    // ---------------------------------------------------------------

    modifier onlyGovernance() {
        if (msg.sender != governance) revert NotGovernance();
        _;
    }

    // ---------------------------------------------------------------
    // Constructor
    // ---------------------------------------------------------------

    constructor(address _governance) {
        governance = _governance;
    }

    // ---------------------------------------------------------------
    // Registration
    // ---------------------------------------------------------------

    /**
     * @notice Register a new Codex module.
     * @param moduleId     Unique module identifier (hash of module path).
     * @param manifestHash SHA3-256 hash of the module manifest.
     * @param contentHash  SHA3-256 hash of the module content bundle.
     * @param version      Semantic version string.
     */
    function registerModule(
        bytes32 moduleId,
        bytes32 manifestHash,
        bytes32 contentHash,
        string calldata version
    ) external onlyGovernance {
        if (manifestHash == bytes32(0)) revert InvalidHash();
        if (contentHash == bytes32(0)) revert InvalidHash();
        if (_modules[moduleId].registeredAt != 0) {
            revert ModuleAlreadyExists(moduleId);
        }

        _modules[moduleId] = ModuleEntry({
            manifestHash: manifestHash,
            contentHash: contentHash,
            version: version,
            registeredAt: block.timestamp,
            registrant: msg.sender,
            active: true
        });

        _moduleIds.push(moduleId);

        emit ModuleRegistered(moduleId, manifestHash, contentHash, version, msg.sender);
    }

    // ---------------------------------------------------------------
    // Lifecycle
    // ---------------------------------------------------------------

    /**
     * @notice Deactivate a module (soft-delete, preserves history).
     */
    function deactivateModule(bytes32 moduleId) external onlyGovernance {
        if (_modules[moduleId].registeredAt == 0) revert ModuleNotFound(moduleId);
        _modules[moduleId].active = false;
        emit ModuleDeactivated(moduleId, msg.sender);
    }

    /**
     * @notice Reactivate a previously deactivated module.
     */
    function reactivateModule(bytes32 moduleId) external onlyGovernance {
        if (_modules[moduleId].registeredAt == 0) revert ModuleNotFound(moduleId);
        _modules[moduleId].active = true;
        emit ModuleReactivated(moduleId, msg.sender);
    }

    // ---------------------------------------------------------------
    // Queries (view)
    // ---------------------------------------------------------------

    /**
     * @notice Get module entry by ID.
     */
    function getModule(bytes32 moduleId) external view returns (ModuleEntry memory) {
        if (_modules[moduleId].registeredAt == 0) revert ModuleNotFound(moduleId);
        return _modules[moduleId];
    }

    /**
     * @notice Check if a module exists and is active.
     */
    function isActive(bytes32 moduleId) external view returns (bool) {
        return _modules[moduleId].active && _modules[moduleId].registeredAt != 0;
    }

    /**
     * @notice Total number of registered modules.
     */
    function moduleCount() external view returns (uint256) {
        return _moduleIds.length;
    }

    /**
     * @notice Verify a manifest hash matches the registered entry.
     */
    function verifyManifest(bytes32 moduleId, bytes32 expectedHash)
        external view returns (bool)
    {
        return _modules[moduleId].manifestHash == expectedHash;
    }

    // ---------------------------------------------------------------
    // Governance
    // ---------------------------------------------------------------

    /**
     * @notice Transfer governance to a new address.
     */
    function transferGovernance(address newGovernance) external onlyGovernance {
        emit GovernanceTransferred(governance, newGovernance);
        governance = newGovernance;
    }
}
