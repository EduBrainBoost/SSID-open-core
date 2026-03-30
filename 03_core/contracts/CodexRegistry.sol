// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CodexRegistry
 * @author SSID Protocol
 * @notice On-chain registry mapping SSID shard IDs to content hashes.
 *         Supports registration, update, and revocation of codex entries.
 * @dev Access control is handled via an owner + authorized registrars pattern.
 *      No external dependencies — implements access control inline to avoid
 *      import coupling in the early smart-contract layer.
 */
contract CodexRegistry {
    // -------------------------------------------------------------------------
    // Types
    // -------------------------------------------------------------------------

    /// @notice Status of a codex entry
    enum EntryStatus {
        Unregistered,
        Active,
        Revoked
    }

    /// @notice A single codex entry stored on-chain
    struct CodexEntry {
        bytes32 contentHash;   // keccak256 or IPFS CID encoded as bytes32
        address registrar;     // who registered / last updated this entry
        uint64  registeredAt;  // block.timestamp of initial registration
        uint64  updatedAt;     // block.timestamp of last update
        EntryStatus status;
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    /// @dev Contract owner — can grant/revoke registrar roles and change owner
    address public owner;

    /// @dev Authorized registrars (besides owner)
    mapping(address => bool) public isRegistrar;

    /// @dev shardId  →  codex entry
    mapping(bytes32 => CodexEntry) private _entries;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a new shard is registered
    /// @param shardId     Unique identifier of the shard
    /// @param contentHash Hash of the codex content
    /// @param registrar   Address that performed the registration
    event Registered(bytes32 indexed shardId, bytes32 indexed contentHash, address indexed registrar);

    /// @notice Emitted when an existing entry is updated
    /// @param shardId        Unique identifier of the shard
    /// @param oldContentHash Previous content hash
    /// @param newContentHash New content hash
    /// @param registrar      Address that performed the update
    event Updated(
        bytes32 indexed shardId,
        bytes32 oldContentHash,
        bytes32 indexed newContentHash,
        address indexed registrar
    );

    /// @notice Emitted when an entry is revoked
    /// @param shardId   Unique identifier of the shard
    /// @param registrar Address that performed the revocation
    event Revoked(bytes32 indexed shardId, address indexed registrar);

    /// @notice Emitted when a registrar is authorized
    event RegistrarAdded(address indexed registrar);

    /// @notice Emitted when a registrar authorization is removed
    event RegistrarRemoved(address indexed registrar);

    /// @notice Emitted on ownership transfer
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // -------------------------------------------------------------------------
    // Errors
    // -------------------------------------------------------------------------

    error Unauthorized();
    error AlreadyRegistered(bytes32 shardId);
    error NotRegistered(bytes32 shardId);
    error AlreadyRevoked(bytes32 shardId);
    error ZeroAddress();
    error EmptyContentHash();

    // -------------------------------------------------------------------------
    // Modifiers
    // -------------------------------------------------------------------------

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier onlyAuthorized() {
        if (msg.sender != owner && !isRegistrar[msg.sender]) revert Unauthorized();
        _;
    }

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    /**
     * @param initialOwner Address that will own this contract initially.
     *                     Must not be the zero address.
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
     * @notice Transfer contract ownership to a new address.
     * @param newOwner The address that will become the new owner.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        address previous = owner;
        owner = newOwner;
        emit OwnershipTransferred(previous, newOwner);
    }

    /**
     * @notice Grant registrar privileges to an address.
     * @param registrar Address to authorize.
     */
    function addRegistrar(address registrar) external onlyOwner {
        if (registrar == address(0)) revert ZeroAddress();
        isRegistrar[registrar] = true;
        emit RegistrarAdded(registrar);
    }

    /**
     * @notice Revoke registrar privileges from an address.
     * @param registrar Address to deauthorize.
     */
    function removeRegistrar(address registrar) external onlyOwner {
        isRegistrar[registrar] = false;
        emit RegistrarRemoved(registrar);
    }

    // -------------------------------------------------------------------------
    // Core registry operations
    // -------------------------------------------------------------------------

    /**
     * @notice Register a new codex entry for a shard ID.
     * @param shardId     Unique identifier for the shard.
     * @param contentHash keccak256 hash (or IPFS CID bytes32) of the codex content.
     */
    function register(bytes32 shardId, bytes32 contentHash) external onlyAuthorized {
        if (contentHash == bytes32(0)) revert EmptyContentHash();
        CodexEntry storage entry = _entries[shardId];
        if (entry.status == EntryStatus.Active) revert AlreadyRegistered(shardId);

        _entries[shardId] = CodexEntry({
            contentHash:   contentHash,
            registrar:     msg.sender,
            registeredAt:  uint64(block.timestamp),
            updatedAt:     uint64(block.timestamp),
            status:        EntryStatus.Active
        });

        emit Registered(shardId, contentHash, msg.sender);
    }

    /**
     * @notice Update the content hash of an existing active codex entry.
     * @param shardId        Shard ID whose entry should be updated.
     * @param newContentHash New content hash to store.
     */
    function update(bytes32 shardId, bytes32 newContentHash) external onlyAuthorized {
        if (newContentHash == bytes32(0)) revert EmptyContentHash();
        CodexEntry storage entry = _entries[shardId];
        if (entry.status != EntryStatus.Active) revert NotRegistered(shardId);

        bytes32 old = entry.contentHash;
        entry.contentHash = newContentHash;
        entry.registrar   = msg.sender;
        entry.updatedAt   = uint64(block.timestamp);

        emit Updated(shardId, old, newContentHash, msg.sender);
    }

    /**
     * @notice Revoke an existing active codex entry.
     * @param shardId Shard ID to revoke.
     */
    function revoke(bytes32 shardId) external onlyAuthorized {
        CodexEntry storage entry = _entries[shardId];
        if (entry.status == EntryStatus.Unregistered) revert NotRegistered(shardId);
        if (entry.status == EntryStatus.Revoked)      revert AlreadyRevoked(shardId);

        entry.status    = EntryStatus.Revoked;
        entry.updatedAt = uint64(block.timestamp);

        emit Revoked(shardId, msg.sender);
    }

    // -------------------------------------------------------------------------
    // View functions
    // -------------------------------------------------------------------------

    /**
     * @notice Retrieve the full codex entry for a shard ID.
     * @param shardId The shard to query.
     * @return entry The stored CodexEntry struct.
     */
    function getEntry(bytes32 shardId) external view returns (CodexEntry memory entry) {
        return _entries[shardId];
    }

    /**
     * @notice Check whether a shard ID is currently active.
     * @param shardId The shard to check.
     * @return active True if the entry exists and has not been revoked.
     */
    function isActive(bytes32 shardId) external view returns (bool active) {
        return _entries[shardId].status == EntryStatus.Active;
    }

    /**
     * @notice Retrieve only the content hash for a shard ID.
     * @param shardId The shard to query.
     * @return contentHash The stored content hash (bytes32(0) if not registered).
     */
    function getContentHash(bytes32 shardId) external view returns (bytes32 contentHash) {
        return _entries[shardId].contentHash;
    }
}
