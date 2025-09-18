#!/usr/bin/env python3
"""
Review Status Gate for CI/CD Pipeline
Version: 1.0
Date: 2025-09-18
Purpose: Validates review status and blocks CI/CD if reviews are overdue
"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import yaml


class ReviewStatusGate:
    def __init__(self):
        self.repo_root = Path(__file__).parent.parent.parent.parent.parent
        self.review_log_path = self.repo_root / "23_compliance" / "reviews" / "review_log.json"
        self.overdue_warning_days = 30
        self.overdue_blocking_days = 60

    def load_review_log(self):
        """Load the review log JSON file"""
        try:
            if self.review_log_path.exists():
                with open(self.review_log_path, 'r') as f:
                    return json.load(f)
            else:
                print(f"WARNING: Review log not found at {self.review_log_path}")
                return self.create_default_review_log()
        except Exception as e:
            print(f"ERROR: Error loading review log: {e}")
            return None

    def create_default_review_log(self):
        """Create a default review log structure"""
        return {
            "review_system_version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "review_history": [],
            "review_schedule": {
                "next_internal": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                "next_external": (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d"),
                "overdue_reviews": [],
                "scheduled_reviews": []
            },
            "ci_integration": {
                "pr_checks_enabled": True,
                "review_status_check": "required",
                "overdue_review_blocking": True,
                "last_automated_check": datetime.now().isoformat()
            }
        }

    def check_review_status(self):
        """Check if reviews are current and not overdue"""
        review_log = self.load_review_log()
        if not review_log:
            print("ERROR: Could not load review log")
            return False

        current_date = datetime.now()
        issues = []

        # Check for overdue external reviews
        if "review_schedule" in review_log:
            schedule = review_log["review_schedule"]

            if "next_external" in schedule:
                try:
                    next_external = datetime.strptime(schedule["next_external"], "%Y-%m-%d")
                    days_until_review = (next_external - current_date).days

                    if days_until_review < -self.overdue_blocking_days:
                        issues.append(f"ERROR: External review overdue by {abs(days_until_review)} days (blocking threshold: {self.overdue_blocking_days} days)")
                        return False
                    elif days_until_review < -self.overdue_warning_days:
                        issues.append(f"WARNING: External review overdue by {abs(days_until_review)} days (warning)")
                    elif days_until_review < 0:
                        issues.append(f"WARNING: External review overdue by {abs(days_until_review)} days")

                except ValueError as e:
                    issues.append(f"ERROR: Invalid external review date format: {schedule['next_external']}")

            # Check for overdue internal reviews
            if "next_internal" in schedule:
                try:
                    next_internal = datetime.strptime(schedule["next_internal"], "%Y-%m-%d")
                    days_until_review = (next_internal - current_date).days

                    if days_until_review < -self.overdue_blocking_days:
                        issues.append(f"ERROR: Internal review overdue by {abs(days_until_review)} days (blocking threshold: {self.overdue_blocking_days} days)")
                        return False
                    elif days_until_review < 0:
                        issues.append(f"WARNING: Internal review overdue by {abs(days_until_review)} days")

                except ValueError as e:
                    issues.append(f"ERROR: Invalid internal review date format: {schedule['next_internal']}")

        # Check review history for recent reviews
        if "review_history" in review_log and review_log["review_history"]:
            last_review = review_log["review_history"][-1]
            if "date" in last_review:
                try:
                    last_review_date = datetime.strptime(last_review["date"], "%Y-%m-%d")
                    days_since_last = (current_date - last_review_date).days

                    if days_since_last > 365:  # More than a year since last review
                        issues.append(f"WARNING: Last review was {days_since_last} days ago (consider scheduling)")

                except ValueError as e:
                    issues.append(f"ERROR: Invalid last review date format: {last_review['date']}")
        else:
            issues.append("WARNING: No review history found")

        # Print issues
        if issues:
            print("CHECK: Review Status Issues:")
            for issue in issues:
                print(f"   {issue}")

            # Return False only for blocking issues (ERROR:)
            return not any(issue.startswith("ERROR:") for issue in issues)
        else:
            print("PASS: All reviews are current")
            return True

    def update_last_check(self):
        """Update the last automated check timestamp"""
        review_log = self.load_review_log()
        if review_log:
            review_log["ci_integration"]["last_automated_check"] = datetime.now().isoformat()

            try:
                with open(self.review_log_path, 'w') as f:
                    json.dump(review_log, f, indent=2)
            except Exception as e:
                print(f"WARNING: Could not update last check timestamp: {e}")

    def run_gate_check(self):
        """Run the complete review status gate check"""
        print("Running Review Status Gate Check...")
        print(f"Repository root: {self.repo_root}")
        print(f"Review log path: {self.review_log_path}")

        # Check if CI integration is enabled
        review_log = self.load_review_log()
        if review_log and review_log.get("ci_integration", {}).get("review_status_check") != "required":
            print("INFO: Review status check is not required - skipping")
            return True

        # Perform the review status check
        status = self.check_review_status()

        # Update last check timestamp
        self.update_last_check()

        if status:
            print("PASS: Review Status Gate: PASSED")
            return True
        else:
            print("FAIL: Review Status Gate: FAILED")
            print("   Please update review schedule or conduct overdue reviews")
            return False


def main():
    """Main entry point"""
    gate = ReviewStatusGate()

    # Check if we're in CI context
    is_ci = os.getenv('CI', '').lower() in ('true', '1')
    pr_context = os.getenv('GITHUB_EVENT_NAME') == 'pull_request'

    if is_ci:
        print(f"CONFIG: Running in CI context (PR: {pr_context})")

    success = gate.run_gate_check()

    if not success:
        print("\nTIP: To resolve review issues:")
        print("   1. Update review_log.json with current review schedules")
        print("   2. Conduct overdue reviews and document results")
        print("   3. Contact maintainers if review coordination is needed")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()