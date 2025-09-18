#!/usr/bin/env python3
"""
Update Review Log
Version: 1.0
Date: 2025-09-18
Purpose: Update and maintain the machine-readable review log
"""

import json
import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import yaml


class ReviewLogUpdater:
    def __init__(self):
        self.repo_root = Path(__file__).parent.parent.parent
        self.review_log_path = self.repo_root / "23_compliance" / "reviews" / "review_log.json"

    def load_review_log(self):
        """Load the review log JSON file"""
        try:
            if self.review_log_path.exists():
                with open(self.review_log_path, 'r') as f:
                    return json.load(f)
            else:
                return self.create_initial_log()
        except Exception as e:
            print(f"ERROR: Error loading review log: {e}")
            return None

    def create_initial_log(self):
        """Create initial review log if it doesn't exist"""
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

    def add_review_entry(self, review_data):
        """Add a new review entry to the log"""
        review_log = self.load_review_log()
        if not review_log:
            return False

        # Validate review data
        required_fields = ["review_id", "date", "type", "reviewer", "status"]
        for field in required_fields:
            if field not in review_data:
                print(f"ERROR: Missing required field: {field}")
                return False

        # Add review to history
        review_log["review_history"].append(review_data)
        review_log["last_updated"] = datetime.now().isoformat()

        return self.save_review_log(review_log)

    def update_schedule(self, internal_date=None, external_date=None):
        """Update the review schedule"""
        review_log = self.load_review_log()
        if not review_log:
            return False

        if internal_date:
            review_log["review_schedule"]["next_internal"] = internal_date

        if external_date:
            review_log["review_schedule"]["next_external"] = external_date

        review_log["last_updated"] = datetime.now().isoformat()

        return self.save_review_log(review_log)

    def update_automated_check(self, pr_context=False, ci_context=False):
        """Update the automated check timestamp"""
        review_log = self.load_review_log()
        if not review_log:
            return False

        review_log["ci_integration"]["last_automated_check"] = datetime.now().isoformat()

        if pr_context:
            review_log["ci_integration"]["last_pr_check"] = datetime.now().isoformat()

        if ci_context:
            review_log["ci_integration"]["last_ci_check"] = datetime.now().isoformat()

        review_log["last_updated"] = datetime.now().isoformat()

        return self.save_review_log(review_log)

    def mark_review_complete(self, review_id, status="COMPLETED", next_review_date=None):
        """Mark a review as complete and update schedule"""
        review_log = self.load_review_log()
        if not review_log:
            return False

        # Find and update the review
        for review in review_log["review_history"]:
            if review.get("review_id") == review_id:
                review["status"] = status
                review["completion_date"] = datetime.now().strftime("%Y-%m-%d")
                break

        # Update next review date if provided
        if next_review_date:
            # Determine if this was internal or external review
            review_type = None
            for review in review_log["review_history"]:
                if review.get("review_id") == review_id:
                    review_type = review.get("type")
                    break

            if review_type == "external":
                review_log["review_schedule"]["next_external"] = next_review_date
            else:
                review_log["review_schedule"]["next_internal"] = next_review_date

        review_log["last_updated"] = datetime.now().isoformat()

        return self.save_review_log(review_log)

    def save_review_log(self, review_log):
        """Save the review log to file"""
        try:
            # Ensure directory exists
            os.makedirs(self.review_log_path.parent, exist_ok=True)

            with open(self.review_log_path, 'w') as f:
                json.dump(review_log, f, indent=2)
            return True
        except Exception as e:
            print(f"ERROR: Error saving review log: {e}")
            return False

    def generate_summary(self):
        """Generate a summary of the current review status"""
        review_log = self.load_review_log()
        if not review_log:
            return

        print("REPORT: Review Log Summary")
        print("=" * 40)

        # Review history
        if "review_history" in review_log and review_log["review_history"]:
            print(f"STATS: Total Reviews: {len(review_log['review_history'])}")

            last_review = review_log["review_history"][-1]
            print(f"CHECK: Last Review:")
            print(f"   - ID: {last_review.get('review_id', 'Unknown')}")
            print(f"   - Date: {last_review.get('date', 'Unknown')}")
            print(f"   - Type: {last_review.get('type', 'Unknown')}")
            print(f"   - Status: {last_review.get('status', 'Unknown')}")

            # Count by type
            internal_count = sum(1 for r in review_log["review_history"] if r.get("type") == "internal")
            external_count = sum(1 for r in review_log["review_history"] if r.get("type") == "external")

            print(f"STATS: Review Breakdown:")
            print(f"   - Internal: {internal_count}")
            print(f"   - External: {external_count}")
        else:
            print("STATS: No reviews recorded yet")

        # Schedule
        if "review_schedule" in review_log:
            schedule = review_log["review_schedule"]
            print(f"SCHEDULE: Next Scheduled:")
            print(f"   - Internal: {schedule.get('next_internal', 'Not scheduled')}")
            print(f"   - External: {schedule.get('next_external', 'Not scheduled')}")

        # CI integration
        if "ci_integration" in review_log:
            ci = review_log["ci_integration"]
            print(f"CONFIG: CI Integration:")
            print(f"   - Checks Enabled: {ci.get('pr_checks_enabled', False)}")
            print(f"   - Last Check: {ci.get('last_automated_check', 'Never')}")

        print(f"TIME: Last Updated: {review_log.get('last_updated', 'Unknown')}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Update SSID compliance review log")

    # Actions
    parser.add_argument("--automated", action="store_true", help="Update automated check timestamp")
    parser.add_argument("--pr-context", action="store_true", help="Update in PR context")
    parser.add_argument("--ci-context", action="store_true", help="Update in CI context")
    parser.add_argument("--summary", action="store_true", help="Show review log summary")

    # Review management
    parser.add_argument("--add-review", help="Add new review entry (JSON file path)")
    parser.add_argument("--complete-review", help="Mark review as complete (review ID)")
    parser.add_argument("--next-internal", help="Set next internal review date (YYYY-MM-DD)")
    parser.add_argument("--next-external", help="Set next external review date (YYYY-MM-DD)")

    args = parser.parse_args()

    updater = ReviewLogUpdater()

    # Show summary if requested
    if args.summary:
        updater.generate_summary()
        return

    # Update automated check
    if args.automated or args.pr_context or args.ci_context:
        success = updater.update_automated_check(
            pr_context=args.pr_context,
            ci_context=args.ci_context
        )
        if success:
            if not args.automated:  # Don't spam for automated updates
                print("PASS: Updated automated check timestamp")
        else:
            print("ERROR: Failed to update automated check")
            sys.exit(1)

    # Add new review
    if args.add_review:
        try:
            with open(args.add_review, 'r') as f:
                review_data = json.load(f)

            if updater.add_review_entry(review_data):
                print(f"PASS: Added review entry from {args.add_review}")
            else:
                print(f"ERROR: Failed to add review entry")
                sys.exit(1)
        except Exception as e:
            print(f"ERROR: Error loading review data: {e}")
            sys.exit(1)

    # Complete review
    if args.complete_review:
        next_date = None
        if args.next_internal:
            next_date = args.next_internal
        elif args.next_external:
            next_date = args.next_external

        if updater.mark_review_complete(args.complete_review, next_review_date=next_date):
            print(f"PASS: Marked review {args.complete_review} as complete")
        else:
            print(f"ERROR: Failed to mark review as complete")
            sys.exit(1)

    # Update schedule
    if args.next_internal or args.next_external:
        if updater.update_schedule(args.next_internal, args.next_external):
            print("PASS: Updated review schedule")
        else:
            print("ERROR: Failed to update review schedule")
            sys.exit(1)

    # If no actions specified, show summary
    if not any([args.automated, args.pr_context, args.ci_context, args.add_review,
                args.complete_review, args.next_internal, args.next_external]):
        updater.generate_summary()


if __name__ == "__main__":
    main()