import pandas as pd
import subprocess
import json
from pathlib import Path
import os
import pyodbc
from datetime import datetime
import tempfile


class RunStatusRecorder:
    def __init__(self, context):
        # Store database settings
        self.db_name = context.db_name
        self.db_dsn = context.db_dsn
        self.db_username = context.db_username
        self.db_password = context.db_password
        self.table_name = "UI_eclengine_records"

    def _create_status_record_csv(self, maker, time, settings, action, status, checker, created_at):
        """Create a CSV file with the status record data"""
        data = {
            'maker': [maker],
            'time': [time],
            'settings': [settings],
            'action': [action],
            'status': [status],
            'checker': [checker],
            'created_at': [created_at]
        }

        df = pd.DataFrame(data)

        # Create temporary CSV file with proper separator
        temp_csv = tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False)
        df.to_csv(temp_csv.name, index=False, sep='\x1F', encoding='utf-8-sig')
        temp_csv.close()

        return temp_csv.name

    def insert_status_record(self, maker, time, settings, action, status, checker, created_at):
        """Insert a new status record into the database"""
        print(f"Inserting status record: {action} - {status}")
        print(f"Time: {time}, Created_at: {created_at}")

        try:
            # Connect to database
            conn = pyodbc.connect(
                f'DSN={self.db_dsn};UID={self.db_username};PWD={self.db_password}',
                autocommit=True
            )
            cursor = conn.cursor()

            # Insert record using direct SQL
            insert_sql = f"""
                INSERT INTO [{self.db_name}].[dbo].[{self.table_name}] 
                (maker, time, settings, action, status, checker, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """

            print(f"Executing SQL: {insert_sql}")
            print(
                f"Parameters: maker={maker}, time={time}, action={action}, status={status}")

            cursor.execute(insert_sql, (
                maker, time, settings, action, status, checker, created_at
            ))

            print("Status record inserted successfully")
            conn.close()
            return True

        except Exception as e:
            print(f"Error inserting status record: {str(e)}")
            return False

    def update_status_record(self, time, new_status):
        """Update the status of an existing record based on time"""
        print(f"Updating status record to: {new_status}")
        print(f"Looking for record with time: {time}")

        try:
            # Connect to database
            conn = pyodbc.connect(
                f'DSN={self.db_dsn};UID={self.db_username};PWD={self.db_password}',
                autocommit=True
            )
            cursor = conn.cursor()

            # First, let's check if the record exists
            check_sql = f"""
                SELECT COUNT(*) FROM [{self.db_name}].[dbo].[{self.table_name}]
                WHERE maker = 'Batch Run' AND time = ?
            """
            cursor.execute(check_sql, (time,))
            count = cursor.fetchone()[0]
            print(f"Found {count} matching records")

            if count == 0:
                # Try to find any recent Batch Run records
                recent_sql = f"""
                    SELECT TOP 5 time, status FROM [{self.db_name}].[dbo].[{self.table_name}]
                    WHERE maker = 'Batch Run'
                    ORDER BY created_at DESC
                """
                cursor.execute(recent_sql)
                recent_records = cursor.fetchall()
                print("Recent Batch Run records:")
                for record in recent_records:
                    print(f"  Time: {record[0]}, Status: {record[1]}")
                conn.close()
                return False

            # Update the status where maker='Batch Run' and time matches
            update_sql = f"""
                UPDATE [{self.db_name}].[dbo].[{self.table_name}]
                SET status = ?
                WHERE maker = 'Batch Run' AND time = ?
            """

            print(f"Executing SQL: {update_sql}")
            print(f"Parameters: status={new_status}, time={time}")

            cursor.execute(update_sql, (new_status, time))

            if cursor.rowcount > 0:
                print(
                    f"Status record updated successfully: {cursor.rowcount} row(s) affected")
                conn.close()
                return True
            else:
                print("No matching record found to update")
                conn.close()
                return False

        except Exception as e:
            print(f"Error updating status record: {str(e)}")
            return False
