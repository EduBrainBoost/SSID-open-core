// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title CodexRewardReporter
 * @author SSID Protocol
 * @notice Reports contributor activity on-chain and manages reward claiming.
 * @dev The contract maintains a ledger of reported contributions.  An
 *      authorized reporter (off-chain oracle / backend signer) calls
 *      `reportContribution` after validating work off-chain.  The contributor
 *      can then call `claimReward` to receive their accumulated reward balance.
 *
 *      Reward tokens are native ETH in this version.  A future upgrade can
 *      swap the settlement layer for an ERC-20 token by adjusting the
 *      `_settleReward` internal function.
 */
contract CodexRewardReporter {
    // -------------------------------------------------------------------------
    // Types
    // -------------------------------------------------------------------------

    /**
     * @notice A single recorded contribution.
     */
    struct Contribution {
        address contributor;   // Who made the contribution
        bytes32 shardId;       // Associated codex shard
        bytes32 contributionId;// Unique ID assigned off-chain
        uint256 rewardWei;     // Reward amount denominated in wei
        uint64  reportedAt;    // block.timestamp when reported
        bool    claimed;       // Whether the reward has been claimed
    }

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    /// @dev Contract owner
    address public owner;

    /// @dev Addresses authorized to report contributions (oracles / backends)
    mapping(address => bool) public isReporter;

    /// @dev contributionId → Contribution record
    mapping(bytes32 => Contribution) private _contributions;

    /// @dev Accumulated claimable balances per contributor
    mapping(address => uint256) public pendingRewards;

    /// @dev Track which contributionIds have been reported (prevent duplicates)
    mapping(bytes32 => bool) private _reported;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a contribution is reported on-chain
    /// @param contributionId  Unique off-chain contribution identifier
    /// @param contributor     Address of the contributor
    /// @param shardId         Shard the contribution is associated with
    /// @param rewardWei       Reward amount in wei
    event ContributionReported(
        bytes32 indexed contributionId,
        address indexed contributor,
        bytes32 indexed shardId,
        uint256 rewardWei
    );

    /// @notice Emitted when a contributor claims their reward
    /// @param contributor  Address that claimed the reward
    /// @param amount       Total amount claimed (wei)
    event RewardClaimed(address indexed contributor, uint256 amount);

    /// @notice Emitted when contract receives a funding deposit
    /// @param funder  Address that deposited funds
    /// @param amount  Amount deposited (wei)
    event FundsDeposited(address indexed funder, uint256 amount);

    /// @notice Emitted when a reporter is authorized
    event ReporterAdded(address indexed reporter);

    /// @notice Emitted when a reporter authorization is removed
    event ReporterRemoved(address indexed reporter);

    /// @notice Emitted on ownership transfer
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    // -------------------------------------------------------------------------
    // Errors
    // -------------------------------------------------------------------------

    error Unauthorized();
    error ZeroAddress();
    error ZeroReward();
    error DuplicateContribution(bytes32 contributionId);
    error ContributionNotFound(bytes32 contributionId);
    error AlreadyClaimed(bytes32 contributionId);
    error NothingToClaim();
    error InsufficientContractBalance(uint256 available, uint256 required);
    error TransferFailed();

    // -------------------------------------------------------------------------
    // Modifiers
    // -------------------------------------------------------------------------

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier onlyReporter() {
        if (msg.sender != owner && !isReporter[msg.sender]) revert Unauthorized();
        _;
    }

    // -------------------------------------------------------------------------
    // Constructor
    // -------------------------------------------------------------------------

    /**
     * @param initialOwner Address that will own this contract.
     *                     The owner also has reporter privileges.
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

    /**
     * @notice Authorize an address to report contributions.
     * @param reporter Address to authorize.
     */
    function addReporter(address reporter) external onlyOwner {
        if (reporter == address(0)) revert ZeroAddress();
        isReporter[reporter] = true;
        emit ReporterAdded(reporter);
    }

    /**
     * @notice Revoke reporting privileges from an address.
     * @param reporter Address to deauthorize.
     */
    function removeReporter(address reporter) external onlyOwner {
        isReporter[reporter] = false;
        emit ReporterRemoved(reporter);
    }

    // -------------------------------------------------------------------------
    // Funding
    // -------------------------------------------------------------------------

    /**
     * @notice Deposit ETH to fund future reward payouts.
     * @dev Anyone can fund the contract (e.g. a DAO treasury or fee contract).
     */
    function deposit() external payable {
        emit FundsDeposited(msg.sender, msg.value);
    }

    /**
     * @notice View the contract's current reward pool balance.
     */
    function rewardPoolBalance() external view returns (uint256) {
        return address(this).balance;
    }

    // -------------------------------------------------------------------------
    // Contribution reporting
    // -------------------------------------------------------------------------

    /**
     * @notice Record a contribution on-chain and credit the contributor's
     *         pending reward balance.
     * @dev    The contract must hold sufficient ETH to cover the reward at
     *         reporting time (checked here to fail fast).  If the contract
     *         runs out of funds, the operator must call `deposit()` first.
     * @param contributionId  Unique identifier assigned off-chain (must be unique).
     * @param contributor     Address of the contributor to reward.
     * @param shardId         Shard the contribution is linked to.
     * @param rewardWei       Reward amount in wei.
     */
    function reportContribution(
        bytes32 contributionId,
        address contributor,
        bytes32 shardId,
        uint256 rewardWei
    ) external onlyReporter {
        if (contributor == address(0)) revert ZeroAddress();
        if (rewardWei == 0)            revert ZeroReward();
        if (_reported[contributionId]) revert DuplicateContribution(contributionId);

        uint256 available = address(this).balance;
        // Check pool is solvent: available must cover *all* pending + new reward
        // We use a simple forward-check here. A more advanced approach would use
        // a separate "reserved" counter — acceptable trade-off at this stage.
        uint256 totalPending = _totalPendingRewards + rewardWei;
        if (available < totalPending) {
            revert InsufficientContractBalance(available, totalPending);
        }

        _reported[contributionId] = true;
        _contributions[contributionId] = Contribution({
            contributor:    contributor,
            shardId:        shardId,
            contributionId: contributionId,
            rewardWei:      rewardWei,
            reportedAt:     uint64(block.timestamp),
            claimed:        false
        });

        pendingRewards[contributor] += rewardWei;
        _totalPendingRewards        += rewardWei;

        emit ContributionReported(contributionId, contributor, shardId, rewardWei);
    }

    /// @dev Running total of all unclaimed pending rewards (used for solvency check)
    uint256 private _totalPendingRewards;

    // -------------------------------------------------------------------------
    // Reward claiming
    // -------------------------------------------------------------------------

    /**
     * @notice Claim all pending rewards for the caller.
     * @dev Uses checks-effects-interactions to prevent reentrancy.
     */
    function claimReward() external {
        uint256 amount = pendingRewards[msg.sender];
        if (amount == 0) revert NothingToClaim();

        // Effects
        pendingRewards[msg.sender] = 0;
        _totalPendingRewards       -= amount;

        // Interaction
        (bool success, ) = msg.sender.call{value: amount}("");
        if (!success) revert TransferFailed();

        emit RewardClaimed(msg.sender, amount);
    }

    // -------------------------------------------------------------------------
    // View helpers
    // -------------------------------------------------------------------------

    /**
     * @notice Retrieve a contribution record by its ID.
     * @param contributionId The contribution to look up.
     * @return contribution  The stored Contribution struct.
     */
    function getContribution(bytes32 contributionId)
        external
        view
        returns (Contribution memory contribution)
    {
        if (!_reported[contributionId]) revert ContributionNotFound(contributionId);
        return _contributions[contributionId];
    }

    /**
     * @notice Check whether a contribution ID has already been reported.
     * @param contributionId ID to check.
     * @return reported True if already on-chain.
     */
    function hasBeenReported(bytes32 contributionId) external view returns (bool reported) {
        return _reported[contributionId];
    }

    /**
     * @notice Return total unclaimed pending rewards across all contributors.
     */
    function totalPendingRewards() external view returns (uint256) {
        return _totalPendingRewards;
    }

    // -------------------------------------------------------------------------
    // Fallback — accept plain ETH for reward pool top-ups
    // -------------------------------------------------------------------------

    receive() external payable {
        emit FundsDeposited(msg.sender, msg.value);
    }
}
