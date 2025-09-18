#!/usr/bin/env python3
"""
Review Status Checker
Version: 1.0
Date: 2025-09-18
Purpose: Check and validate review status for compliance framework
"""

import json
import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import yaml


class ReviewStatusChecker:
    def __init__(self):
        self.repo_root = Path(__file__).parent.parent.parent
        self.review_log_path = self.repo_root / "23_compliance" / "reviews" / "review_log.json"
        self.review_schedule_path = self.repo_root / "23_compliance" / "reviews" / "review_schedule.yaml"

    def load_review_log(self):
        """Load the review log JSON file"""
        try:
            if self.review_log_path.exists():
                with open(self.review_log_path, 'r') as f:
                    return json.load(f)
            else:
                print(f"FILE: Creating new review log at {self.review_log_path}")
                return self.create_initial_review_log()
        except Exception as e:
            print(f"ERROR: Error loading review log: {e}")
            return None

    def create_initial_review_log(self):
        """Create initial review log structure"""
        initial_log = {
            "review_system_version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "review_history": [
                {
                    "review_id": "2025-09-18-framework-setup",
                    "date": "2025-09-18",
                    "type": "internal",
                    "reviewer": {
                        "name": "Framework Setup",
                        "organization": "SSID Project",
                        "credentials": "Initial Setup",
                        "independence_verified": True
                    },
                    "status": "FRAMEWORK_READY",
                    "matrix_version": "1.0",
                    "badge_logic_version": "1.0",
                    "findings": {
                        "critical": 0,
                        "major": 0,
                        "minor": 0
                    },
                    "score": "Framework Ready",
                    "next_review": "2025-12-18",
                    "report_path": "23_compliance/reviews/framework_setup_2025-09-18.md",
                    "dependencies_validated": 0,
                    "circular_dependencies_found": 0,
                    "badge_integrity_validated": True,
                    "compliance_matrix_accuracy": "Framework Ready"
                }
            ],
            "review_schedule": {
                "next_internal": "2025-12-18",
                "next_external": "2026-03-18",
                "overdue_reviews": [],
                "scheduled_reviews": [
                    {
                        "type": "quarterly_internal",
                        "date": "2025-12-18",
                        "reviewer": "Community Lead",
                        "scope": ["badge_thresholds", "compliance_updates"]
                    },
                    {
                        "type": "external_validation",
                        "date": "2026-03-18",
                        "reviewer": "External Expert Pool",
                        "scope": ["badge_logic", "anti_gaming_controls", "compliance_matrix"]
                    }
                ]
            },
            "ci_integration": {
                "pr_checks_enabled": True,
                "review_status_check": "required",
                "overdue_review_blocking": True,
                "last_automated_check": datetime.now().isoformat()
            }
        }

        # Save initial log
        try:
            os.makedirs(self.review_log_path.parent, exist_ok=True)
            with open(self.review_log_path, 'w') as f:
                json.dump(initial_log, f, indent=2)
            print(f"PASS: Created initial review log at {self.review_log_path}")
        except Exception as e:
            print(f"ERROR: Error creating initial review log: {e}")

        return initial_log

    def check_review_currency(self):
        """Check if reviews are current"""
        review_log = self.load_review_log()
        if not review_log:
            return False

        current_date = datetime.now()
        status = {
            "current": True,
            "warnings": [],
            "errors": [],
            "next_actions": []
        }

        # Check review schedule
        if "review_schedule" in review_log:
            schedule = review_log["review_schedule"]

            # Check next internal review
            if "next_internal" in schedule:
                try:
                    next_internal = datetime.strptime(schedule["next_internal"], "%Y-%m-%d")
                    days_until = (next_internal - current_date).days

                    if days_until < -30:  # Overdue by more than 30 days
                        status["errors"].append(f"Internal review overdue by {abs(days_until)} days")
                        status["current"] = False
                    elif days_until < 0:
                        status["warnings"].append(f"Internal review overdue by {abs(days_until)} days")
                    elif days_until < 14:
                        status["next_actions"].append(f"Internal review due in {days_until} days")

                except ValueError:
                    status["errors"].append(f"Invalid internal review date: {schedule['next_internal']}")

            # Check next external review
            if "next_external" in schedule:
                try:
                    next_external = datetime.strptime(schedule["next_external"], "%Y-%m-%d")
                    days_until = (next_external - current_date).days

                    if days_until < -60:  # Overdue by more than 60 days
                        status["errors"].append(f"External review overdue by {abs(days_until)} days")
                        status["current"] = False
                    elif days_until < 0:
                        status["warnings"].append(f"External review overdue by {abs(days_until)} days")
                    elif days_until < 30:
                        status["next_actions"].append(f"External review due in {days_until} days")

                except ValueError:
                    status["errors"].append(f"Invalid external review date: {schedule['next_external']}")

        return status

    def generate_status_report(self, pr_context=False):
        """Generate a status report"""
        print("CHECK: Review Status Report")
        print("=" * 50)

        review_log = self.load_review_log()
        if not review_log:
            print("ERROR: Cannot generate report - review log unavailable")
            return False

        status = self.check_review_currency()

        # Print overall status
        if status["current"]:
            print("PASS: Overall Status: CURRENT")
        else:
            print("ERROR: Overall Status: NEEDS ATTENTION")

        # Print errors
        if status["errors"]:
            print("\nERROR: Critical Issues:")
            for error in status["errors"]:
                print(f"   - {error}")

        # Print warnings
        if status["warnings"]:
            print("\nWARNING: Warnings:")
            for warning in status["warnings"]:
                print(f"   - {warning}")

        # Print next actions
        if status["next_actions"]:
            print("\nSCHEDULE: Upcoming:")
            for action in status["next_actions"]:
                print(f"   - {action}")

        # Print review history summary
        if "review_history" in review_log and review_log["review_history"]:
            last_review = review_log["review_history"][-1]
            print(f"\nREPORT: Last Review:")
            print(f"   - Date: {last_review.get('date', 'Unknown')}")
            print(f"   - Type: {last_review.get('type', 'Unknown')}")
            print(f"   - Status: {last_review.get('status', 'Unknown')}")

        # Print schedule info
        if "review_schedule" in review_log:
            schedule = review_log["review_schedule"]
            print(f"\nSCHEDULE: Next Scheduled Reviews:")
            print(f"   - Internal: {schedule.get('next_internal', 'Not scheduled')}")
            print(f"   - External: {schedule.get('next_external', 'Not scheduled')}")

        if pr_context:
            print(f"\nCONFIG: PR Context: Review status checked for pull request")

        return status["current"]

    def update_review_log(self, review_data=None, automated=False, ci_context=False):
        """Update the review log with new information"""
        review_log = self.load_review_log()
        if not review_log:
            return False

        # Update last automated check
        if automated:
            review_log["ci_integration"]["last_automated_check"] = datetime.now().isoformat()

        # Add new review data if provided
        if review_data:
            review_log["review_history"].append(review_data)

        # Update last_updated timestamp
        review_log["last_updated"] = datetime.now().isoformat()

        try:
            with open(self.review_log_path, 'w') as f:
                json.dump(review_log, f, indent=2)
            if not automated:
                print(f"PASS: Updated review log at {self.review_log_path}")
            return True
        except Exception as e:
            print(f"ERROR: Error updating review log: {e}")
            return False

    def run_check(self, pr_context=False, block_if_overdue=False):
        """Run the complete review status check"""
        print("Running Review Status Check...")

        status_ok = self.generate_status_report(pr_context)

        # Update automated check timestamp
        self.update_review_log(automated=True, ci_context=pr_context)

        if not status_ok and block_if_overdue:
            print("\nERROR: Review status check failed - blocking due to overdue reviews")
            return False

        if status_ok:
            print("\nPASS: Review status check passed")
        else:
            print("\nWARNING: Review status has issues but not blocking")

        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Check review status for SSID compliance framework")
    parser.add_argument("--pr-context", action="store_true", help="Run in pull request context")
    parser.add_argument("--block-if-overdue", action="store_true", help="Block (exit 1) if reviews are overdue")
    parser.add_argument("--update-log", action="store_true", help="Update the review log timestamp")

    args = parser.parse_args()

    checker = ReviewStatusChecker()

    success = checker.run_check(
        pr_context=args.pr_context,
        block_if_overdue=args.block_if_overdue
    )

    if not success:
        print("\nTIP: To resolve review issues:")
        print("   1. Schedule and conduct overdue reviews")
        print("   2. Update review_log.json with current schedules")
        print("   3. Contact maintainers for review coordination")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()