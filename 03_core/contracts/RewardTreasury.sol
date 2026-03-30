// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title RewardTreasury
 * @notice Canonical SSID Treasury contract for deposit, withdrawal, and burn operations.
 * @dev Non-custodial, governance-controlled. No external dependencies.
 *      Fee model reference: 16_codex/SSID_structure_level3_part1_MAX.md
 *      - 2% system treasury share from 3% total fee
 *      - 50% of treasury share burned (daily/monthly caps enforced)
 */

/// @dev Minimal ERC20 interface — no OpenZeppelin dependency.
interface IERC20Minimal {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

contract RewardTreasury {
    // --- State ---
    address public governanceAddress;
    IERC20Minimal public token;

    uint256 public dailyCap;
    uint256 public monthlyCap;
    uint256 public dailyBurned;
    uint256 public monthlyBurned;
    uint256 public lastDailyReset;
    uint256 public lastMonthlyReset;

    address public constant DEAD_ADDRESS = 0x000000000000000000000000000000000000dEaD;

    // --- Events ---
    event Deposited(address indexed from, uint256 amount);
    event Withdrawn(address indexed to, uint256 amount);
    event Burned(uint256 amount);
    event CapsUpdated(uint256 newDailyCap, uint256 newMonthlyCap);

    // --- Modifiers ---
    modifier onlyGovernance() {
        require(msg.sender == governanceAddress, "RewardTreasury: caller is not governance");
        _;
    }

    // --- Constructor ---
    constructor(
        address _governanceAddress,
        address _token,
        uint256 _dailyCap,
        uint256 _monthlyCap
    ) {
        require(_governanceAddress != address(0), "RewardTreasury: governance is zero address");
        require(_token != address(0), "RewardTreasury: token is zero address");

        governanceAddress = _governanceAddress;
        token = IERC20Minimal(_token);
        dailyCap = _dailyCap;
        monthlyCap = _monthlyCap;
        lastDailyReset = block.timestamp;
        lastMonthlyReset = block.timestamp;
    }

    // --- Receive ETH ---
    receive() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    // --- Deposit ERC20 tokens ---
    function deposit(uint256 amount) external {
        require(amount > 0, "RewardTreasury: amount is zero");
        bool success = token.transferFrom(msg.sender, address(this), amount);
        require(success, "RewardTreasury: transferFrom failed");
        emit Deposited(msg.sender, amount);
    }

    // --- Withdraw ERC20 tokens (governance only) ---
    function withdraw(address to, uint256 amount) external onlyGovernance {
        require(to != address(0), "RewardTreasury: recipient is zero address");
        require(amount > 0, "RewardTreasury: amount is zero");
        require(token.balanceOf(address(this)) >= amount, "RewardTreasury: insufficient balance");
        bool success = token.transfer(to, amount);
        require(success, "RewardTreasury: transfer failed");
        emit Withdrawn(to, amount);
    }

    // --- Burn tokens to dead address (governance only, cap-checked) ---
    function burn(uint256 amount) external onlyGovernance {
        require(amount > 0, "RewardTreasury: amount is zero");
        require(token.balanceOf(address(this)) >= amount, "RewardTreasury: insufficient balance");

        _resetCapsIfNeeded();

        require(dailyBurned + amount <= dailyCap, "RewardTreasury: daily burn cap exceeded");
        require(monthlyBurned + amount <= monthlyCap, "RewardTreasury: monthly burn cap exceeded");

        dailyBurned += amount;
        monthlyBurned += amount;

        bool success = token.transfer(DEAD_ADDRESS, amount);
        require(success, "RewardTreasury: burn transfer failed");
        emit Burned(amount);
    }

    // --- Update burn caps (governance only) ---
    function updateCaps(uint256 _dailyCap, uint256 _monthlyCap) external onlyGovernance {
        require(_dailyCap <= _monthlyCap, "RewardTreasury: daily cap exceeds monthly cap");
        dailyCap = _dailyCap;
        monthlyCap = _monthlyCap;
        emit CapsUpdated(_dailyCap, _monthlyCap);
    }

    // --- View: token balance held by treasury ---
    function getBalance() external view returns (uint256) {
        return token.balanceOf(address(this));
    }

    // --- Internal: reset daily/monthly counters ---
    function _resetCapsIfNeeded() internal {
        if (block.timestamp >= lastDailyReset + 1 days) {
            dailyBurned = 0;
            lastDailyReset = block.timestamp;
        }
        if (block.timestamp >= lastMonthlyReset + 30 days) {
            monthlyBurned = 0;
            lastMonthlyReset = block.timestamp;
        }
    }
}
