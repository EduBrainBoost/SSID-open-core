// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title CodexRewardReporter
 * @notice On-chain reporting of Codex module reward distributions.
 * @dev Non-custodial: records only proof hashes of reward computations.
 *      No PII on-chain. No fund custody. Version: v4.1.0
 *
 * ROOT-24-LOCK | Module: 16_codex
 * Evidence strategy: hash_manifest_only
 *
 * Integrates with the off-chain reward_handler.py — the Python module
 * computes rewards, then submits a SHA3-256 proof here for immutability.
 */
contract CodexRewardReporter {
    // ---------------------------------------------------------------
    // Types
    // ---------------------------------------------------------------

    struct RewardReport {
        bytes32 batchHash;       // SHA3-256 of the full reward batch JSON
        bytes32 settlementHash;  // SHA3-256 of the settlement calculation
        uint256 totalParticipants;
        uint256 reportedAt;      // Block timestamp
        address reporter;        // Address that submitted the report
        string  periodLabel;     // e.g. "2026-Q1" or "2026-03"
    }

    // ---------------------------------------------------------------
    // State
    // ---------------------------------------------------------------

    /// @notice Report ID (sequential hash) => RewardReport
    mapping(bytes32 => RewardReport) private _reports;

    /// @notice Ordered list of all report IDs
    bytes32[] private _reportIds;

    /// @notice Authorized reporter address
    address public reporter;

    /// @notice Governance address
    address public governance;

    /// @notice Contract version
    string public constant VERSION = "4.1.0";

    // ---------------------------------------------------------------
    // Events
    // ---------------------------------------------------------------

    event RewardReported(
        bytes32 indexed reportId,
        bytes32 batchHash,
        bytes32 settlementHash,
        uint256 totalParticipants,
        string  periodLabel,
        address indexed reporter
    );

    event ReporterUpdated(address indexed previous, address indexed next);
    event GovernanceTransferred(address indexed previous, address indexed next);

    // ---------------------------------------------------------------
    // Errors
    // ---------------------------------------------------------------

    error NotAuthorized();
    error NotGovernance();
    error ReportAlreadyExists(bytes32 reportId);
    error ReportNotFound(bytes32 reportId);
    error InvalidHash();

    // ---------------------------------------------------------------
    // Modifiers
    // ---------------------------------------------------------------

    modifier onlyReporter() {
        if (msg.sender != reporter) revert NotAuthorized();
        _;
    }

    modifier onlyGovernance() {
        if (msg.sender != governance) revert NotGovernance();
        _;
    }

    // ---------------------------------------------------------------
    // Constructor
    // ---------------------------------------------------------------

    constructor(address _governance, address _reporter) {
        governance = _governance;
        reporter = _reporter;
    }

    // ---------------------------------------------------------------
    // Reporting
    // ---------------------------------------------------------------

    /**
     * @notice Submit a reward distribution report.
     * @param reportId          Unique report identifier.
     * @param batchHash         SHA3-256 hash of the reward batch result.
     * @param settlementHash    SHA3-256 hash of the settlement calculation.
     * @param totalParticipants Number of participants in the batch.
     * @param periodLabel       Settlement period label.
     */
    function submitReport(
        bytes32 reportId,
        bytes32 batchHash,
        bytes32 settlementHash,
        uint256 totalParticipants,
        string calldata periodLabel
    ) external onlyReporter {
        if (batchHash == bytes32(0)) revert InvalidHash();
        if (settlementHash == bytes32(0)) revert InvalidHash();
        if (_reports[reportId].reportedAt != 0) {
            revert ReportAlreadyExists(reportId);
        }

        _reports[reportId] = RewardReport({
            batchHash: batchHash,
            settlementHash: settlementHash,
            totalParticipants: totalParticipants,
            reportedAt: block.timestamp,
            reporter: msg.sender,
            periodLabel: periodLabel
        });

        _reportIds.push(reportId);

        emit RewardReported(
            reportId, batchHash, settlementHash,
            totalParticipants, periodLabel, msg.sender
        );
    }

    // ---------------------------------------------------------------
    // Queries (view)
    // ---------------------------------------------------------------

    /**
     * @notice Get a reward report by ID.
     */
    function getReport(bytes32 reportId) external view returns (RewardReport memory) {
        if (_reports[reportId].reportedAt == 0) revert ReportNotFound(reportId);
        return _reports[reportId];
    }

    /**
     * @notice Verify a batch hash matches the recorded report.
     */
    function verifyBatch(bytes32 reportId, bytes32 expectedBatchHash)
        external view returns (bool)
    {
        return _reports[reportId].batchHash == expectedBatchHash;
    }

    /**
     * @notice Total number of submitted reports.
     */
    function reportCount() external view returns (uint256) {
        return _reportIds.length;
    }

    // ---------------------------------------------------------------
    // Administration
    // ---------------------------------------------------------------

    /**
     * @notice Update the authorized reporter address.
     */
    function setReporter(address newReporter) external onlyGovernance {
        emit ReporterUpdated(reporter, newReporter);
        reporter = newReporter;
    }

    /**
     * @notice Transfer governance to a new address.
     */
    function transferGovernance(address newGovernance) external onlyGovernance {
        emit GovernanceTransferred(governance, newGovernance);
        governance = newGovernance;
    }
}
