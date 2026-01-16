import os
import shutil
import json
from pathlib import Path
from datetime import datetime, timedelta
from utils.loggers import createLogHandler


class FolderHousekeeping:
    def __init__(self, config):
        """
        Initialize folder housekeeping utility with configuration

        Args:
            config (dict): Configuration dictionary containing path settings
        """
        # Setup logging first
        self.logger = createLogHandler(
            'FolderHousekeeping', 'housekeeping.log')

        # Store path settings from config
        self.data_path = config.get('RUN_SETTING', {}).get('DATA_PATH', '')
        self.param_path = config.get('RUN_SETTING', {}).get('PARAM_PATH', '')
        self.output_path = config.get(
            'RUN_SETTING', {}).get('OUTPUT_PATH', '')

        # Store housekeeping settings
        self.housekeeping_config = config.get('HOUSEKEEPING_SETTING', {})

        # Validate only output path exists (data and param paths are not cleaned)
        self._validate_output_path()

    def _validate_output_path(self):
        """Validate that the output path exists and is accessible"""
        if not self.output_path:
            self.logger.warning("OUTPUT_PATH is not configured")
            return

        path_obj = Path(self.output_path)
        if not path_obj.exists():
            self.logger.warning(
                f"OUTPUT_PATH does not exist: {self.output_path}")
        elif not path_obj.is_dir():
            self.logger.warning(
                f"OUTPUT_PATH is not a directory: {self.output_path}")
        else:
            self.logger.info(f"OUTPUT_PATH validated: {self.output_path}")

    def _parse_folder_date(self, folder_name):
        """
        Parse folder name in format yyyymmdd_yyyymmdd and extract batch/reporting date

        Args:
            folder_name (str): Folder name in format yyyymmdd_yyyymmdd

        Returns:
            datetime or None: Batch/reporting date if valid, None otherwise
        """
        try:
            # Split by underscore and take the first part (batch/reporting date)
            parts = folder_name.split('_')
            if len(parts) != 2:
                return None

            batch_date_str = parts[0]
            if len(batch_date_str) != 8:
                return None

            # Parse the date
            batch_date = datetime.strptime(batch_date_str, '%Y%m%d')
            return batch_date

        except (ValueError, IndexError):
            return None

    def _should_delete_folder(self, folder_name, cutoff_date):
        """
        Determine if a folder should be deleted based on 1-year retention policy

        Args:
            folder_name (str): Folder name in format yyyymmdd_yyyymmdd
            cutoff_date (datetime): Cutoff date (1 year ago)

        Returns:
            bool: True if folder should be deleted, False otherwise
        """
        batch_date = self._parse_folder_date(folder_name)
        if batch_date is None:
            # If we can't parse the date, don't delete (safety measure)
            self.logger.warning(
                f"Could not parse date from folder: {folder_name}")
            return False

        return batch_date < cutoff_date

    def clean_output_directory(self):
        """
        Clean output directory based on 1-year retention policy for batch/reporting dates

        Returns:
            dict: Results of the cleaning operation
        """
        if not self.output_path:
            self.logger.warning("OUTPUT_PATH is not configured, skipping")
            return {'success': True, 'deleted_folders': [], 'error': 'OUTPUT_PATH not configured'}

        path_obj = Path(self.output_path)

        if not path_obj.exists():
            self.logger.warning(
                f"OUTPUT_PATH does not exist: {self.output_path}")
            return {'success': True, 'deleted_folders': [], 'error': 'OUTPUT_PATH does not exist'}

        if not path_obj.is_dir():
            self.logger.error(
                f"OUTPUT_PATH is not a directory: {self.output_path}")
            return {'success': False, 'deleted_folders': [], 'error': 'OUTPUT_PATH is not a directory'}

        try:
            # Calculate cutoff date (1 year ago)
            cutoff_date = datetime.now() - timedelta(days=365)
            self.logger.info(
                f"Cleaning output folders older than: {cutoff_date.strftime('%Y-%m-%d')}")

            # Get all folders in the output directory
            folders = [item for item in path_obj.iterdir() if item.is_dir()]

            if not folders:
                self.logger.info(f"OUTPUT_PATH is empty: {self.output_path}")
                return {'success': True, 'deleted_folders': [], 'error': None}

            deleted_folders = []
            failed_deletions = []

            for folder in folders:
                folder_name = folder.name

                if self._should_delete_folder(folder_name, cutoff_date):
                    try:
                        batch_date = self._parse_folder_date(folder_name)
                        self.logger.info(
                            f"Deleting folder: {folder_name} (batch date: {batch_date.strftime('%Y-%m-%d')})")

                        shutil.rmtree(folder)
                        deleted_folders.append(folder_name)
                        self.logger.debug(
                            f"Successfully deleted folder: {folder}")

                    except Exception as e:
                        error_msg = f"Failed to delete folder {folder_name}: {str(e)}"
                        self.logger.error(error_msg)
                        failed_deletions.append(folder_name)
                else:
                    batch_date = self._parse_folder_date(folder_name)
                    if batch_date:
                        self.logger.debug(
                            f"Keeping folder: {folder_name} (batch date: {batch_date.strftime('%Y-%m-%d')})")
                    else:
                        self.logger.debug(
                            f"Keeping folder (unparseable date): {folder_name}")

            # Log summary
            total_folders = len(folders)
            kept_folders = total_folders - \
                len(deleted_folders) - len(failed_deletions)

            self.logger.info(f"Output directory cleanup completed:")
            self.logger.info(f"  Total folders: {total_folders}")
            self.logger.info(f"  Deleted: {len(deleted_folders)}")
            self.logger.info(f"  Kept: {kept_folders}")
            self.logger.info(f"  Failed: {len(failed_deletions)}")

            success = len(failed_deletions) == 0
            return {
                'success': success,
                'deleted_folders': deleted_folders,
                'failed_deletions': failed_deletions,
                'total_folders': total_folders,
                'kept_folders': kept_folders,
                'cutoff_date': cutoff_date.strftime('%Y-%m-%d'),
                'error': None if success else f"Failed to delete {len(failed_deletions)} folders"
            }

        except Exception as e:
            error_msg = f"Failed to clean OUTPUT_PATH ({self.output_path}): {str(e)}"
            self.logger.error(error_msg)
            return {'success': False, 'deleted_folders': [], 'error': error_msg}

    def run_folder_housekeeping(self):
        """
        Run folder housekeeping for output path only (with 1-year retention policy)

        Returns:
            dict: Results of the cleaning operation
        """
        # Check if folder housekeeping is enabled
        if not self.housekeeping_config.get('FOLDER_CLEANUP_ENABLED', False):
            self.logger.info("Folder housekeeping is disabled")
            return {'success': True, 'message': 'Folder housekeeping is disabled'}

        self.logger.info(
            "Starting output folder housekeeping (1-year retention policy)")

        # Only clean output path with retention policy
        results = self.clean_output_directory()

        if results['success']:
            self.logger.info(
                "Output folder housekeeping completed successfully")
        else:
            self.logger.error(
                f"Output folder housekeeping failed: {results.get('error', 'Unknown error')}")

        return results

    def dry_run_folder_housekeeping(self):
        """
        Perform a dry run to show what would be cleaned without actually deleting

        Returns:
            dict: Information about what would be cleaned
        """
        dry_run_info = {}

        # Check if folder housekeeping is enabled
        if not self.housekeeping_config.get('FOLDER_CLEANUP_ENABLED', False):
            print("Folder housekeeping is disabled")
            return dry_run_info

        print("=== OUTPUT FOLDER HOUSEKEEPING DRY RUN (1-YEAR RETENTION) ===")

        if not self.output_path:
            print("  OUTPUT_PATH: Not configured")
            dry_run_info['OUTPUT_PATH'] = "Not configured"
            print("=== END DRY RUN ===")
            return dry_run_info

        path_obj = Path(self.output_path)

        if not path_obj.exists():
            print(f"  OUTPUT_PATH: Does not exist ({self.output_path})")
            dry_run_info['OUTPUT_PATH'] = "Does not exist"
            print("=== END DRY RUN ===")
            return dry_run_info

        if not path_obj.is_dir():
            print(f"  OUTPUT_PATH: Not a directory ({self.output_path})")
            dry_run_info['OUTPUT_PATH'] = "Not a directory"
            print("=== END DRY RUN ===")
            return dry_run_info

        # Calculate cutoff date (1 year ago)
        cutoff_date = datetime.now() - timedelta(days=365)
        print(
            f"  Cutoff date (1 year ago): {cutoff_date.strftime('%Y-%m-%d')}")

        # Get all folders in the output directory
        folders = [item for item in path_obj.iterdir() if item.is_dir()]

        if not folders:
            print(f"  OUTPUT_PATH: Already empty ({self.output_path})")
            dry_run_info['OUTPUT_PATH'] = "Already empty"
            print("=== END DRY RUN ===")
            return dry_run_info

        folders_to_delete = []
        folders_to_keep = []
        unparseable_folders = []

        for folder in folders:
            folder_name = folder.name
            batch_date = self._parse_folder_date(folder_name)

            if batch_date is None:
                unparseable_folders.append(folder_name)
            elif batch_date < cutoff_date:
                folders_to_delete.append((folder_name, batch_date))
            else:
                folders_to_keep.append((folder_name, batch_date))

        # Display results
        print(f"  Total folders found: {len(folders)}")
        print(f"  Folders to DELETE: {len(folders_to_delete)}")
        print(f"  Folders to KEEP: {len(folders_to_keep)}")
        print(
            f"  Unparseable folders (will be kept): {len(unparseable_folders)}")

        if folders_to_delete:
            print("\n  Folders that would be DELETED:")
            for folder_name, batch_date in sorted(folders_to_delete, key=lambda x: x[1]):
                print(
                    f"    - {folder_name} (batch date: {batch_date.strftime('%Y-%m-%d')})")

        if folders_to_keep:
            print(f"\n  Folders that would be KEPT (showing first 10):")
            for folder_name, batch_date in sorted(folders_to_keep, key=lambda x: x[1])[:10]:
                print(
                    f"    - {folder_name} (batch date: {batch_date.strftime('%Y-%m-%d')})")
            if len(folders_to_keep) > 10:
                print(f"    ... and {len(folders_to_keep) - 10} more folders")

        if unparseable_folders:
            print(f"\n  Unparseable folders (will be kept for safety):")
            for folder_name in unparseable_folders[:5]:
                print(f"    - {folder_name}")
            if len(unparseable_folders) > 5:
                print(f"    ... and {len(unparseable_folders) - 5} more")

        dry_run_info['OUTPUT_PATH'] = {
            'total_folders': len(folders),
            'to_delete': len(folders_to_delete),
            'to_keep': len(folders_to_keep),
            'unparseable': len(unparseable_folders),
            'cutoff_date': cutoff_date.strftime('%Y-%m-%d'),
            'folders_to_delete': [name for name, _ in folders_to_delete],
            'folders_to_keep': [name for name, _ in folders_to_keep],
            'unparseable_folders': unparseable_folders
        }

        print("=== END DRY RUN ===")
        return dry_run_info


if __name__ == "__main__":
    import sys
    from utils.db_housekeeping import load_config

    if len(sys.argv) < 2:
        print(
            "Usage: python folder_housekeeping.py <config_file_path> [--dry-run]")
        sys.exit(1)

    config_path = sys.argv[1]
    dry_run = len(sys.argv) > 2 and sys.argv[2] == '--dry-run'

    config = load_config(config_path)

    if not config:
        print("Failed to load configuration")
        sys.exit(1)

    folder_housekeeping = FolderHousekeeping(config)

    if dry_run:
        results = folder_housekeeping.dry_run_folder_housekeeping()
    else:
        results = folder_housekeeping.run_folder_housekeeping()

    if not dry_run:
        print("Output Folder Housekeeping Results:")
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
