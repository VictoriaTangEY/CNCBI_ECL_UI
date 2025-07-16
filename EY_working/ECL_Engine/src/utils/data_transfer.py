import pandas as pd
import subprocess
import json
from pathlib import Path
import os
import pyodbc
from datetime import datetime
# cmd = """
# /opt/mssql-tools18/bin/bcp test in test.csv -c -t ',' \
# -S ECLSITFSDB -U eclappusr -P Abcdef123456
# """
# subprocess.run(cmd, shell=True, check=True)


class DataTransfer:
    def __init__(self, context):

        # Store timestamp
        self.timestamp = context.timestamp_datetime

        # Store database settings
        self.db_name = context.db_name
        self.db_dsn = context.db_dsn
        self.db_username = context.db_username
        self.db_password = context.db_password

        # Type mapping for SQL Server data types
        self.type_mapping = {
            'object': 'NVARCHAR(MAX)',
            'string': 'NVARCHAR(MAX)',
            'category': 'NVARCHAR(255)',
            'int64': 'BIGINT',
            'int32': 'INT',
            'float64': 'FLOAT',
            'float32': 'REAL',
            'datetime64[ns]': 'DATETIME2',
            'datetime64[us]': 'DATETIME2',
            'datetime64[ms]': 'DATETIME2',
            'datetime64[s]': 'DATETIME2',
            'date': 'DATE',
            'bool': 'BIT',
            'timedelta64[ns]': 'BIGINT',
            'timedelta64[us]': 'BIGINT',
            'timedelta64[ms]': 'BIGINT',
            'timedelta64[s]': 'BIGINT'
        }

    def add_timestamp(self, csv_path):
        """Add TIMESTAMP column to CSV file and return the path to the modified file"""
        print("Adding TIMESTAMP column to CSV...")

        # Read the CSV file
        df = pd.read_csv(csv_path, sep='\x1F', encoding='utf-8-sig')

        # Add TIMESTAMP column as the first column using timestamp from context
        df.insert(0, 'TIMESTAMP', self.timestamp)

        # Save the modified DataFrame to a new CSV
        modified_csv_path = csv_path.with_stem(
            f"{csv_path.stem}_with_timestamp")
        df.to_csv(modified_csv_path, index=False,
                  sep='\x1F', encoding='utf-8-sig')
        print(f"Created timestamped CSV at: {modified_csv_path}")

        return modified_csv_path

    def generate_create_table(self, csv_path, table_name):
        """Generate CREATE TABLE SQL statement based on CSV structure"""
        # Read CSV to infer column types
        df = pd.read_csv(csv_path, sep='\x1F', encoding='utf-8-sig')

        # Initialize columns list
        columns = []

        for col, dtype in df.dtypes.items():
            # Get the string representation of the dtype
            dtype_str = str(dtype)
            # Look up the SQL type in our mapping
            sql_type = self.type_mapping.get(dtype_str, 'VARCHAR(255)')
            print(f"Column: {col}, Type: {dtype_str}, SQL Type: {sql_type}")
            # Add square brackets around column names to handle special characters
            columns.append(f"[{col}] {sql_type}")

        # Format the SQL statement using instance variables
        create_sql = f"CREATE TABLE [{self.db_name}].[dbo].[{table_name}] (\n  " + \
            ",\n  ".join(columns) + "\n);"
        return create_sql

    def create_table(self, csv_path, table_name):
        """Create table in database based on CSV structure"""
        print("Creating table in DB...")

        # Add timestamp to CSV first
        modified_csv_path = self.add_timestamp(csv_path)

        try:
            # Generate the CREATE TABLE statement using the modified CSV
            create_sql = self.generate_create_table(
                modified_csv_path, table_name)

            # Create table using pyodbc
            conn = pyodbc.connect(
                f'DSN={self.db_dsn};UID={self.db_username};PWD={self.db_password}',
                autocommit=True
            )
            cursor = conn.cursor()
            cursor.execute(create_sql)
            conn.close()
            print('Create successfully')
            return True
        finally:
            # Clean up the modified CSV file
            if os.path.exists(modified_csv_path):
                os.remove(modified_csv_path)

    def import_data(self, csv_path, table_name):
        """Import data from CSV into existing table using BCP"""
        print("Importing data into DB...")
        csv_path_str = str(csv_path)
        print(f"Using file path: {csv_path_str}")

        # Add timestamp to CSV
        modified_csv_path = self.add_timestamp(csv_path)
        modified_csv_path_str = str(modified_csv_path)

        # Debug information
        print(f"Modified CSV path: {modified_csv_path_str}")
        print(f"File exists: {os.path.exists(modified_csv_path_str)}")
        print(
            f"File size: {os.path.getsize(modified_csv_path_str) if os.path.exists(modified_csv_path_str) else 'N/A'}")

        try:
            # Try using a simpler BCP command format
            bcp_cmd = [
                "/opt/mssql-tools18/bin/bcp",
                f"{self.db_name}.dbo.{table_name}",
                "in",
                modified_csv_path_str,
                "-c",
                "-t", "\x1F",  # Changed from $'\x1F' to \x1F
                "-D",
                "-S", self.db_dsn,
                "-U", self.db_username,
                "-P", self.db_password,
                "-C", "65001"
            ]

            print("Executing BCP command:", " ".join(bcp_cmd))

            # Run BCP with shell=True to handle the hex character properly
            subprocess.run(" ".join(bcp_cmd), shell=True, check=True)
            print("Import successfully")
        except subprocess.CalledProcessError as e:
            print(f"BCP command failed with error: {str(e)}")
            print(
                f"Command output: {e.output if hasattr(e, 'output') else 'No output'}")
            raise
        finally:
            # Clean up the modified CSV file
            if os.path.exists(modified_csv_path):
                os.remove(modified_csv_path)
        return True

    def _handle_csv_file(self, file_path, table_name):
        """Handle CSV file directly - use original data types"""
        print(f"Processing CSV file {file_path}...")
        self.import_data(file_path, table_name)
        return True

    def _handle_excel_file(self, file_path, table_name):
        """Handle Excel file - convert all columns to strings"""
        print(f"Processing Excel file {file_path}...")
        # Read all sheets from Excel
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names

        if len(sheet_names) == 1:
            # Single sheet - process as before
            df = pd.read_excel(file_path, dtype=str)
            csv_path = file_path.with_stem(
                f"{file_path.stem}_{sheet_names[0]}").with_suffix('.csv')
            # Ensure all columns are strings when saving to CSV
            for col in df.columns:
                df[col] = df[col].astype(str)
            # Save CSV with proper encoding and line endings
            df.to_csv(csv_path, index=False,
                      encoding='utf-8-sig', sep='\x1F', lineterminator='\n')
            print(f"Excel file converted to {csv_path}")
            self.import_data(csv_path, table_name)
        else:
            # Multiple sheets - process each sheet
            print(f"Found {len(sheet_names)} sheets in Excel file")
            for sheet_name in sheet_names:
                # Create table name for this sheet
                sheet_table_name = f"{table_name}_{sheet_name}"
                print(f"\nProcessing sheet: {sheet_name}")

                # Read and convert sheet to CSV
                df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str)
                csv_path = file_path.with_stem(
                    f"{file_path.stem}_{sheet_name}").with_suffix('.csv')
                # Ensure all columns are strings when saving to CSV
                for col in df.columns:
                    df[col] = df[col].astype(str)
                # Save CSV with proper encoding and line endings
                df.to_csv(csv_path, index=False,
                          encoding='utf-8-sig', sep='\x1F', lineterminator='\n')
                print(f"Sheet converted to {csv_path}")

                # Import to database
                self.import_data(csv_path, sheet_table_name)
                print(
                    f"Successfully imported sheet to table: {sheet_table_name}")

        print(f"Successfully completed data transfer for Excel file")
        return True

    def _handle_log_file(self, file_path, table_name):
        """Handle Log file - convert to structured CSV with string columns"""
        print(f"Converting Log file {file_path} to CSV format...")
        # Read log file and convert to DataFrame
        log_data = []
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                # Parse log line format: timestamp - name - level - message
                try:
                    parts = line.strip().split(' - ', 3)
                    if len(parts) == 4:
                        timestamp, name, level, message = parts
                        log_data.append({
                            'timestamp': timestamp,
                            'name': name,
                            'level': level,
                            'message': message
                        })
                except Exception as e:
                    print(f"Warning: Could not parse line: {line.strip()}")
                    continue

        df = pd.DataFrame(log_data)
        csv_path = file_path.with_stem(file_path.stem).with_suffix('.csv')
        df.to_csv(csv_path, index=False, sep='\x1F', encoding='utf-8-sig')
        print(f"Log file converted to {csv_path}")
        self.import_data(csv_path, table_name)
        return True

    def run(self, file_path, table_name):
        """Main execution function to control the flow"""
        try:
            print(f"Starting data transfer for table: {table_name}")

            # Handle different file formats
            if file_path.suffix == '.csv':
                return self._handle_csv_file(file_path, table_name)
            elif file_path.suffix == '.xlsx':
                return self._handle_excel_file(file_path, table_name)
            elif file_path.suffix == '.log':
                return self._handle_log_file(file_path, table_name)
            else:
                raise ValueError(
                    f"Unsupported file format: {file_path.suffix}")

        except Exception as e:
            print(f"Error during data transfer: {str(e)}")
            return False
