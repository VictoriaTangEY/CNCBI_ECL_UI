"""
Housekeeping Runner Script for ECL Engine
 
This script runs both database and folder housekeeping utilities.
Database housekeeping: Clean old data from database tables based on batch calendar retention periods.
Folder housekeeping: Clean OUTPUT_PATH directories with 1-year retention policy for batch/reporting dates.
It uses the configuration from run_config_file.json and batch_calendar.txt.
 
Usage:
    python run_housekeeping.py
    python run_housekeeping.py --config path/to/config.json
    python run_housekeeping.py --dry-run
    python run_housekeeping.py --db-only
    python run_housekeeping.py --folder-only
"""

from utils.db_housekeeping import Housekeeping, load_config
from utils.folder_housekeeping import FolderHousekeeping
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta


def run_database_housekeeping(config, dry_run=False):
    """
    Run database housekeeping (original functionality)
    """
    # Check if database housekeeping is enabled
    housekeeping_config = config.get('HOUSEKEEPING_SETTING', {})
    if not housekeeping_config.get('ENABLED', False):
        print("Database housekeeping is disabled in configuration")
        return

    # Create housekeeping instance
    housekeeping = Housekeeping(config)

    if dry_run:
        print("=== DATABASE HOUSEKEEPING DRY RUN ===")
        print("DRY RUN MODE - No data will be deleted")
        print("Tables configured for housekeeping:")

        # Get reporting date and determine housekeeping level
        reporting_date = str(config.get(
            'RUN_SETTING', {}).get('DATA_YYMM', ''))

        print(f"\nBatch calendar entries and retention analysis:")
        today = datetime.now()

        for date_key, level in housekeeping.batch_calendar.items():
            # Get retention period for this batch date
            if level == '60M':
                retention_months = housekeeping_config.get(
                    'EXTENDED_MONTH_OLD', 60)
                retention_type = "Extended"
            else:
                retention_months = housekeeping_config.get(
                    'DEFAULT_MONTH_OLD', 36)
                retention_type = "Default"

            # Calculate cutoff date for this batch
            batch_date = datetime.strptime(date_key, '%Y%m%d')
            cutoff_date = batch_date + timedelta(days=retention_months * 30.5)

            # Check if today's date has exceeded the retention period
            if today >= cutoff_date:
                status = "DELETE BATCH DATA"
            else:
                days_remaining = (cutoff_date - today).days
                status = f"KEEP BATCH DATA ({days_remaining} days remaining)"

            print(f"  {date_key}: {retention_type} ({retention_months} months)")
            print(f"    Batch date: {batch_date.strftime('%Y-%m-%d')}")
            print(f"    Keep until: {cutoff_date.strftime('%Y-%m-%d')}")
            print(f"    Status: {status}")
            print(f"    Data pattern: timestamp starting with '{date_key}'")
            print()

        for table_config in housekeeping.tables_to_clean:
            table_name = table_config.get('table_name')
            timestamp_column = table_config.get('timestamp_column')
            print(
                f"  - {table_name}: Will check retention for each batch date and delete specific batch data (column: {timestamp_column})")
    else:
        # Run housekeeping
        print("=== DATABASE HOUSEKEEPING ===")
        print("Starting database housekeeping process...")
        results = housekeeping.run_housekeeping()

        print("\nDatabase Housekeeping Results:")
        for table, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            print(f"  {table}: {status}")


def run_folder_housekeeping(config, dry_run=False):
    """
    Run folder housekeeping (output path only with 1-year retention policy)
    """
    # Check if folder housekeeping is enabled
    housekeeping_config = config.get('HOUSEKEEPING_SETTING', {})
    if not housekeeping_config.get('FOLDER_CLEANUP_ENABLED', False):
        print("Folder housekeeping is disabled in configuration")
        return

    # Create folder housekeeping instance
    folder_housekeeping = FolderHousekeeping(config)

    if dry_run:
        print("=== OUTPUT FOLDER HOUSEKEEPING DRY RUN ===")
        print("DRY RUN MODE - No files will be deleted")
        folder_housekeeping.dry_run_folder_housekeeping()
    else:
        # Run folder housekeeping
        print("=== OUTPUT FOLDER HOUSEKEEPING ===")
        print("Starting output folder housekeeping process (1-year retention policy)...")
        results = folder_housekeeping.run_folder_housekeeping()

        print("\nOutput Folder Housekeeping Results:")
        if results.get('success'):
            print(f"  Status: SUCCESS")
            print(f"  Cutoff Date: {results.get('cutoff_date', 'N/A')}")
            print(f"  Total Folders: {results.get('total_folders', 0)}")
            print(f"  Deleted: {len(results.get('deleted_folders', []))}")
            print(f"  Kept: {results.get('kept_folders', 0)}")
            if results.get('deleted_folders'):
                print("  Deleted Folders:")
                for folder in results['deleted_folders']:
                    print(f"    - {folder}")
        else:
            print(f"  Status: FAILED")
            print(f"  Error: {results.get('error', 'Unknown error')}")
            if results.get('failed_deletions'):
                print("  Failed Deletions:")
                for folder in results['failed_deletions']:
                    print(f"    - {folder}")


def main():
    parser = argparse.ArgumentParser(
        description='Run database and folder housekeeping')
    parser.add_argument('--config',
                        default='run_config_file.json',
                        help='Path to configuration file (default: run_config_file.json)')
    parser.add_argument('--dry-run',
                        action='store_true',
                        help='Show what would be deleted without actually deleting')
    parser.add_argument('--db-only',
                        action='store_true',
                        help='Run only database housekeeping')
    parser.add_argument('--folder-only',
                        action='store_true',
                        help='Run only folder housekeeping')

    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Configuration file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)
    if not config:
        print("Failed to load configuration")
        sys.exit(1)

    # Determine what to run
    run_db = not args.folder_only
    run_folder = not args.db_only

    # Run database housekeeping
    if run_db:
        run_database_housekeeping(config, args.dry_run)

    # Run folder housekeeping
    if run_folder:
        if run_db:  # Add separator if both are running
            print()
        run_folder_housekeeping(config, args.dry_run)


if __name__ == "__main__":
    main()
