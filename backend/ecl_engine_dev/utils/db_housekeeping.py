import pyodbc
import subprocess
import json
from datetime import datetime, timedelta
from pathlib import Path
from utils.loggers import createLogHandler


class Housekeeping:
    def __init__(self, config):
        """
        Initialize housekeeping utility with configuration

        Args:
            config (dict): Configuration dictionary containing DB_SETTING and HOUSEKEEPING_SETTING
        """
        # Setup logging first
        self.logger = createLogHandler('Housekeeping', 'housekeeping.log')

        # Store database settings
        self.db_name = config.get('DB_SETTING', {}).get('DB_NAME')
        self.db_dsn = config.get('DB_SETTING', {}).get('DSN')
        self.db_username = config.get('DB_SETTING', {}).get('USERNAME')
        self.db_password = config.get('DB_SETTING', {}).get('PASSWORD')

        # Store housekeeping settings
        self.housekeeping_config = config.get('HOUSEKEEPING_SETTING', {})

        # Store reporting date from RUN_SETTING
        self.reporting_date = str(config.get(
            'RUN_SETTING', {}).get('DATA_YYMM', ''))

        # Load batch calendar
        self.batch_calendar = self.load_batch_calendar()

        # Hardcoded tables to clean
        self.tables_to_clean = [
            {
                'table_name': 'exposure_table',
                'timestamp_column': 'timestamp'
            },
            {
                'table_name': 'collateral_table',
                'timestamp_column': 'timestamp'
            },
            {
                'table_name': 'schedule_table',
                'timestamp_column': 'timestamp'
            },
            {
                'table_name': 'facility_table',
                'timestamp_column': 'timestamp'
            }
        ]

    def load_batch_calendar(self):
        """
        Load and parse batch calendar file

        Returns:
            dict: Dictionary with dates as keys and housekeeping level as values
        """
        calendar_file = Path('batch_calendar.txt')
        calendar_data = {}

        if not calendar_file.exists():
            self.logger.warning(
                "Batch calendar file not found, using default settings")
            return calendar_data

        self.logger.info(
            f"Loading batch calendar from: {calendar_file.absolute()}")

        try:
            with open(calendar_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    # Skip comments and empty lines
                    if line.startswith('#') or not line:
                        continue

                    # Parse date and optional housekeeping level
                    parts = line.split()
                    if len(parts) >= 1:
                        date_str = parts[0]

                        # Skip non-date entries like EVERY_FRIDAY, MONTH_END
                        if date_str in ['EVERY_FRIDAY', 'MONTH_END']:
                            self.logger.info(
                                f"Line {line_num}: Skipping non-date entry: {date_str}")
                            continue

                        housekeeping_level = parts[1] if len(
                            parts) > 1 else 'DEFAULT'  # Default to 36 months

                        # Convert date to YYYYMMDD format for comparison
                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            date_key = date_obj.strftime('%Y%m%d')
                            calendar_data[date_key] = housekeeping_level
                            self.logger.info(
                                f"Line {line_num}: Loaded batch date {date_key} with level {housekeeping_level}")
                        except ValueError as ve:
                            self.logger.warning(
                                f"Line {line_num}: Invalid date format '{date_str}' - {str(ve)}")
                            continue

        except Exception as e:
            self.logger.error(f"Failed to load batch calendar: {str(e)}")

        self.logger.info(
            f"Successfully loaded {len(calendar_data)} batch dates from calendar")
        return calendar_data

    def get_connection(self):
        """Create and return database connection"""
        try:
            conn = pyodbc.connect(
                f'DSN={self.db_dsn};UID={self.db_username};PWD={self.db_password}',
                autocommit=True
            )
            return conn
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {str(e)}")
            raise

    def delete_old_data_sql(self, table_name, timestamp_column, months_old):
        """
        Delete old data using SQL DELETE statement

        Args:
            table_name (str): Name of the table to clean
            timestamp_column (str): Name of the timestamp column
            months_old (int): Number of months to keep data after batch run date

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Calculate the cutoff date based on batch run date + retention period
            # If reporting_date is 20250125 and retention is 60 months,
            # cutoff = 20250125 + 60 months = 20300125
            if self.reporting_date:
                # Parse reporting date (format: YYYYMMDD)
                batch_date = datetime.strptime(self.reporting_date, '%Y%m%d')
                cutoff_date = batch_date + timedelta(days=months_old * 30.5)
            else:
                # Fallback to current date if no reporting date
                cutoff_date = datetime.now() + timedelta(days=months_old * 30.5)

            # Format the cutoff date as string in the same format as stored in DB (YYYYMMDD_HHMMSS)
            cutoff_date_str = cutoff_date.strftime('%Y%m%d_%H%M%S')

            # Build the DELETE SQL statement - delete data older than cutoff date
            delete_sql = f"""
            DELETE FROM [{self.db_name}].[dbo].[{table_name}]
            WHERE [{timestamp_column}] < ?
            """

            self.logger.info(f"Executing DELETE for table {table_name}")
            self.logger.info(f"Batch run date: {self.reporting_date}")
            self.logger.info(f"Retention period: {months_old} months")
            self.logger.info(f"Cutoff date: {cutoff_date_str}")

            # Execute the delete
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get count before deletion
            count_sql = f"""
            SELECT COUNT(*) FROM [{self.db_name}].[dbo].[{table_name}]
            WHERE [{timestamp_column}] < ?
            """
            cursor.execute(count_sql, cutoff_date_str)
            records_to_delete = cursor.fetchone()[0]

            if records_to_delete == 0:
                self.logger.info(f"No old records found in table {table_name}")
                return True

            # Execute the delete
            cursor.execute(delete_sql, cutoff_date_str)
            deleted_count = cursor.rowcount

            self.logger.info(
                f"Successfully deleted {deleted_count} records from {table_name}")
            conn.close()

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to delete old data from {table_name}: {str(e)}")
            return False

    def delete_old_data_bcp(self, table_name, timestamp_column, months_old):
        """
        Delete old data using BCP export and SQL DELETE

        Args:
            table_name (str): Name of the table to clean
            timestamp_column (str): Name of the timestamp column
            months_old (int): Number of months to keep data after batch run date

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Calculate the cutoff date based on batch run date + retention period
            if self.reporting_date:
                batch_date = datetime.strptime(self.reporting_date, '%Y%m%d')
                cutoff_date = batch_date + timedelta(days=months_old * 30.5)
            else:
                cutoff_date = datetime.now() + timedelta(days=months_old * 30.5)

            # Create temporary file for BCP export
            temp_file = f"temp_{table_name}_old_data.csv"

            # Build BCP export command to get old records
            bcp_export_cmd = [
                "/opt/mssql-tools18/bin/bcp",
                f"{self.db_name}.dbo.{table_name}",
                "out",
                temp_file,
                "-c",
                "-t", "\x1F",
                "-S", self.db_dsn,
                "-U", self.db_username,
                "-P", self.db_password,
                "-C", "65001",
                "-q",  # Use quoted identifiers
                "-r", "\n"  # Row terminator
            ]

            # Add WHERE clause for timestamp filtering
            where_clause = f"WHERE [{timestamp_column}] < '{cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            bcp_export_cmd.extend(
                ["-Q", f"SELECT * FROM [{self.db_name}].[dbo].[{table_name}] {where_clause}"])

            self.logger.info(f"Exporting old data from {table_name} using BCP")
            self.logger.info(f"Batch run date: {self.reporting_date}")
            self.logger.info(f"Retention period: {months_old} months")
            self.logger.info(f"Cutoff date: {cutoff_date}")

            # Execute BCP export
            result = subprocess.run(
                " ".join(bcp_export_cmd), shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                self.logger.error(f"BCP export failed: {result.stderr}")
                return False

            # Now delete the old records using SQL
            return self.delete_old_data_sql(table_name, timestamp_column, months_old)

        except Exception as e:
            self.logger.error(
                f"Failed to delete old data using BCP from {table_name}: {str(e)}")
            return False

    def get_retention_for_batch_date(self, batch_date_str):
        """
        Get the retention period for a specific batch date

        Args:
            batch_date_str (str): Batch date in YYYYMMDD format

        Returns:
            int: Number of months to keep data after this batch run date
        """
        # Check if this batch date is in batch calendar
        if batch_date_str in self.batch_calendar:
            housekeeping_level = self.batch_calendar[batch_date_str]

            if housekeeping_level == '60M':
                # Use extended month-level housekeeping (60 months)
                months_old = self.housekeeping_config.get(
                    'EXTENDED_MONTH_OLD', 60)
                self.logger.info(
                    f"Batch {batch_date_str}: Using extended month-level housekeeping: {months_old} months retention")
                return months_old
            else:
                # Use default month-level housekeeping (36 months)
                months_old = self.housekeeping_config.get(
                    'DEFAULT_MONTH_OLD', 36)
                self.logger.info(
                    f"Batch {batch_date_str}: Using default month-level housekeeping: {months_old} months retention")
                return months_old

        # Use default month-level housekeeping if not in batch calendar
        default_months_old = self.housekeeping_config.get(
            'DEFAULT_MONTH_OLD', 36)
        self.logger.info(
            f"Batch {batch_date_str}: Using default month-level housekeeping: {default_months_old} months retention")
        return default_months_old

    def get_months_old_for_reporting_date(self):
        """
        Get the retention period based on the current reporting date and batch calendar
        This method is kept for backward compatibility but the logic has changed

        Returns:
            int: Number of months to keep data after batch run date
        """
        # This method now just returns the retention for the current reporting date
        # The actual deletion logic is handled in clean_table method
        return self.get_retention_for_batch_date(self.reporting_date)

    def get_deleted_batches(self):
        """
        Get list of batch dates that have already been deleted

        Returns:
            set: Set of batch dates (YYYYMMDD format) that have been deleted
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if tracking table exists, if not create it
            create_table_sql = """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='housekeeping_tracker' AND xtype='U')
            CREATE TABLE housekeeping_tracker (
                batch_date VARCHAR(8) PRIMARY KEY,
                deleted_date DATETIME DEFAULT GETDATE(),
                retention_months INT,
                tables_processed VARCHAR(MAX)
            )
            """
            cursor.execute(create_table_sql)

            # Get all deleted batch dates
            select_sql = "SELECT batch_date FROM housekeeping_tracker"
            cursor.execute(select_sql)
            deleted_batches = {row[0] for row in cursor.fetchall()}

            conn.close()
            return deleted_batches

        except Exception as e:
            self.logger.error(f"Failed to get deleted batches: {str(e)}")
            return set()

    def mark_batch_as_deleted(self, batch_date_str, retention_months, tables_processed):
        """
        Mark a batch date as deleted in the tracking table

        Args:
            batch_date_str (str): Batch date in YYYYMMDD format
            retention_months (int): Retention period used
            tables_processed (str): Comma-separated list of tables processed
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            insert_sql = """
            INSERT INTO housekeeping_tracker (batch_date, retention_months, tables_processed)
            VALUES (?, ?, ?)
            """
            cursor.execute(insert_sql, (batch_date_str,
                           retention_months, tables_processed))

            conn.close()
            self.logger.info(
                f"Marked batch {batch_date_str} as deleted in tracking table")

        except Exception as e:
            self.logger.error(
                f"Failed to mark batch {batch_date_str} as deleted: {str(e)}")

    def get_batches_needing_processing(self):
        """
        Get batch dates that need processing (not yet expired or not yet deleted)
        This is an alternative to database tracking

        Returns:
            dict: Dictionary of batch dates and their housekeeping levels that need processing
        """
        today = datetime.now()
        batches_to_process = {}

        for batch_date_str, housekeeping_level in self.batch_calendar.items():
            # Get retention period for this batch date
            retention_months = self.get_retention_for_batch_date(
                batch_date_str)

            # Calculate cutoff date for this batch
            batch_date = datetime.strptime(batch_date_str, '%Y%m%d')
            cutoff_date = batch_date + timedelta(days=retention_months * 30.5)

            # Only include batches that have exceeded retention period
            if today >= cutoff_date:
                batches_to_process[batch_date_str] = housekeeping_level
                self.logger.info(
                    f"Batch {batch_date_str}: Will be processed (expired on {cutoff_date.strftime('%Y-%m-%d')})")
            else:
                days_remaining = (cutoff_date - today).days
                self.logger.info(
                    f"Batch {batch_date_str}: Skipping (expires in {days_remaining} days)")

        return batches_to_process

    def clean_table(self, table_config, months_old):
        """
        Clean a specific table based on configuration
        Now applies retention logic to each batch date in the calendar
        Optimized to skip already deleted batches

        Args:
            table_config (dict): Table configuration containing table_name and timestamp_column
            months_old (int): Not used anymore, kept for backward compatibility

        Returns:
            bool: True if successful, False otherwise
        """
        table_name = table_config.get('table_name')
        timestamp_column = table_config.get('timestamp_column')

        if not table_name or not timestamp_column:
            self.logger.error(f"Invalid table configuration: {table_config}")
            return False

        self.logger.info(f"Starting housekeeping for table: {table_name}")

        # Get already deleted batches to avoid re-processing
        deleted_batches = self.get_deleted_batches()
        self.logger.info(
            f"Found {len(deleted_batches)} already deleted batches: {sorted(deleted_batches)}")

        # Process each batch date in the calendar
        total_deleted = 0
        success = True
        processed_batches = []

        for batch_date_str, housekeeping_level in self.batch_calendar.items():
            # Skip if this batch has already been deleted
            if batch_date_str in deleted_batches:
                self.logger.info(
                    f"Batch {batch_date_str}: Already deleted, skipping")
                continue

            # Get retention period for this batch date
            retention_months = self.get_retention_for_batch_date(
                batch_date_str)

            # Calculate cutoff date for this batch
            batch_date = datetime.strptime(batch_date_str, '%Y%m%d')
            cutoff_date = batch_date + timedelta(days=retention_months * 30.5)

            # Check if today's date has exceeded the retention period
            today = datetime.now()
            if today >= cutoff_date:
                self.logger.info(
                    f"Batch {batch_date_str}: Retention period exceeded, deleting batch data")
                self.logger.info(f"  Batch date: {batch_date_str}")
                self.logger.info(f"  Retention: {retention_months} months")
                self.logger.info(
                    f"  Cutoff date: {cutoff_date.strftime('%Y%m%d')}")
                self.logger.info(
                    f"  Will delete data with timestamp starting with: {batch_date_str}")

                # Delete data for this specific batch
                batch_success = self.delete_batch_data(
                    table_name, timestamp_column, batch_date_str, cutoff_date)
                if batch_success:
                    total_deleted += 1
                    processed_batches.append(batch_date_str)
                else:
                    success = False
            else:
                days_remaining = (cutoff_date - today).days
                self.logger.info(
                    f"Batch {batch_date_str}: Data still within retention period ({days_remaining} days remaining)")
                self.logger.info(
                    f"  Will keep data with timestamp starting with: {batch_date_str}")

        # Mark successfully processed batches as deleted
        if processed_batches:
            tables_processed = ','.join([table_name] * len(processed_batches))
            for batch_date_str in processed_batches:
                retention_months = self.get_retention_for_batch_date(
                    batch_date_str)
                self.mark_batch_as_deleted(
                    batch_date_str, retention_months, table_name)

        if total_deleted > 0:
            self.logger.info(
                f"Successfully processed {total_deleted} batch dates for table {table_name}")
        else:
            self.logger.info(
                f"No data deleted for table {table_name} - all batches within retention period or already deleted")

        return success

    def clean_table_optimized(self, table_config, months_old):
        """
        Optimized version of clean_table that only processes batches that need deletion

        Args:
            table_config (dict): Table configuration containing table_name and timestamp_column
            months_old (int): Not used anymore, kept for backward compatibility

        Returns:
            bool: True if successful, False otherwise
        """
        table_name = table_config.get('table_name')
        timestamp_column = table_config.get('timestamp_column')

        if not table_name or not timestamp_column:
            self.logger.error(f"Invalid table configuration: {table_config}")
            return False

        self.logger.info(
            f"Starting optimized housekeeping for table: {table_name}")

        # Get only batches that need processing
        batches_to_process = self.get_batches_needing_processing()

        if not batches_to_process:
            self.logger.info(
                f"No batches need processing for table {table_name}")
            return True

        self.logger.info(
            f"Processing {len(batches_to_process)} batches that need deletion")

        # Process only the batches that need deletion
        total_deleted = 0
        success = True

        for batch_date_str, housekeeping_level in batches_to_process.items():
            # Get retention period for this batch date
            retention_months = self.get_retention_for_batch_date(
                batch_date_str)

            # Calculate cutoff date for this batch
            batch_date = datetime.strptime(batch_date_str, '%Y%m%d')
            cutoff_date = batch_date + timedelta(days=retention_months * 30.5)

            self.logger.info(
                f"Batch {batch_date_str}: Processing deletion")
            self.logger.info(f"  Batch date: {batch_date_str}")
            self.logger.info(f"  Retention: {retention_months} months")
            self.logger.info(
                f"  Cutoff date: {cutoff_date.strftime('%Y%m%d')}")
            self.logger.info(
                f"  Will delete data with timestamp starting with: {batch_date_str}")

            # Delete data for this specific batch
            batch_success = self.delete_batch_data(
                table_name, timestamp_column, batch_date_str, cutoff_date)
            if batch_success:
                total_deleted += 1
            else:
                success = False

        if total_deleted > 0:
            self.logger.info(
                f"Successfully processed {total_deleted} batch dates for table {table_name}")
        else:
            self.logger.info(
                f"No data deleted for table {table_name}")

        return success

    def delete_batch_data(self, table_name, timestamp_column, batch_date_str, cutoff_date):
        """
        Delete data for a specific batch date that has exceeded its retention period

        Args:
            table_name (str): Name of the table to clean
            timestamp_column (str): Name of the timestamp column
            batch_date_str (str): Batch date in YYYYMMDD format
            cutoff_date (datetime): Cutoff date for deletion (not used in this logic)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Delete only data from this specific batch date
            # The timestamp format is YYYYMMDD_HHMMSS, so we match the batch date prefix
            delete_sql = f"""
            DELETE FROM [{self.db_name}].[dbo].[{table_name}]
            WHERE [{timestamp_column}] LIKE '{batch_date_str}%'
            """

            self.logger.info(
                f"Executing DELETE for batch {batch_date_str} in table {table_name}")
            self.logger.info(
                f"Deleting data with timestamp starting with: {batch_date_str}")

            # Execute the delete
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get count before deletion
            count_sql = f"""
            SELECT COUNT(*) FROM [{self.db_name}].[dbo].[{table_name}]
            WHERE [{timestamp_column}] LIKE '{batch_date_str}%'
            """
            cursor.execute(count_sql)
            records_to_delete = cursor.fetchone()[0]

            if records_to_delete == 0:
                self.logger.info(
                    f"No records found for batch {batch_date_str} in table {table_name}")
                return True

            # Execute the delete
            cursor.execute(delete_sql)
            deleted_count = cursor.rowcount

            self.logger.info(
                f"Successfully deleted {deleted_count} records for batch {batch_date_str} from {table_name}")
            conn.close()

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to delete data for batch {batch_date_str} from {table_name}: {str(e)}")
            return False

    def run_housekeeping(self):
        """
        Run housekeeping for all configured tables

        Returns:
            dict: Results for each table
        """
        results = {}

        # Check if housekeeping is enabled
        if not self.housekeeping_config.get('ENABLED', False):
            self.logger.info("Housekeeping is disabled")
            return results

        # Get months_old based on reporting date and batch calendar
        months_old = self.get_months_old_for_reporting_date()

        self.logger.info(
            f"Starting housekeeping for {len(self.tables_to_clean)} tables")
        self.logger.info(f"Current reporting date: {self.reporting_date}")

        for table_config in self.tables_to_clean:
            table_name = table_config.get('table_name')
            if table_name:
                # Use optimized method that only processes batches needing deletion
                results[table_name] = self.clean_table_optimized(
                    table_config, months_old)

        self.logger.info("Housekeeping completed")
        return results


def load_config(config_path):
    """Load configuration from JSON file"""
    try:
        with open(Path(config_path), 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load configuration: {str(e)}")
        return {}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python housekeeping.py <config_file_path>")
        sys.exit(1)

    config_path = sys.argv[1]
    config = load_config(config_path)

    if not config:
        print("Failed to load configuration")
        sys.exit(1)

    housekeeping = Housekeeping(config)
    results = housekeeping.run_housekeeping()

    print("Housekeeping Results:")
    for table, success in results.items():
        status = "SUCCESS" if success else "FAILED"
        print(f"  {table}: {status}")
