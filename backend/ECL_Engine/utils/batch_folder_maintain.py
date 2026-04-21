import json
import os
import sys
import uuid
import traceback
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Callable, Dict, Optional

import pyodbc

DEFAULT_BASE_ROOT = r'/u01/Apps/EY_working'
DEFAULT_ENGINE_DIR = 'ECL_Engine_v0.4'


class BatchFolderMaintain:
    """Batch run helper that manages config generation and DB tracking."""

    def __init__(
        self,
        base_root: str = DEFAULT_BASE_ROOT,
        engine_dir: str = DEFAULT_ENGINE_DIR,
        main_fn: Optional[Callable] = None,
    ):
        self.base_root = base_root
        self.base_ecl_engine = os.path.join(base_root, engine_dir)
        if not main_fn:
            raise ValueError("main_fn is required for BatchFolderMaintain")
        self.main_fn = main_fn

    def save_eclengine_record(self, maker, time, settings, action, status, checker, db_config) -> bool:
        """Persist a run management record."""
        try:
            dsn = db_config.get('DSN', '')
            username = db_config.get('USERNAME', '')
            password = db_config.get('PASSWORD', '')
            db_name = db_config.get('DB_NAME', '')

            conn = pyodbc.connect(f'DSN={dsn};UID={username};PWD={password}', autocommit=True)
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO [{db_name}].[dbo].[UI_eclengine_records]
                (maker, time, settings, action, status, checker)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (maker, time, settings, action, status, checker),
            )
            conn.close()
            print(f"Successfully saved ECL engine record: {action}")
            return True
        except Exception as exc:
            error_details = traceback.format_exc()
            print(f"Error saving ECL engine record: {exc}")
            print(f"Error details:\n{error_details}")
            print(f"Database connection info: DSN={dsn}, DB={db_name}, User={username}")
            return False

    def update_eclengine_status_in_db(self, task_id, status, db_config) -> None:
        """Update the status field for a given task_id."""
        try:
            dsn = db_config.get('DSN', '')
            username = db_config.get('USERNAME', '')
            password = db_config.get('PASSWORD', '')
            db_name = db_config.get('DB_NAME', '')

            conn = pyodbc.connect(f'DSN={dsn};UID={username};PWD={password}', autocommit=True)
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE [{db_name}].[dbo].[UI_eclengine_records]
                SET status = ?
                WHERE settings IS NOT NULL
                AND ISJSON(settings) = 1
                AND JSON_VALUE(settings, '$.task_id') = ?
            """,
                (status, task_id),
            )
            rows_affected = cursor.rowcount
            conn.close()
            if rows_affected > 0:
                print(f"Updated DB status for task {task_id} to {status}")
            else:
                print(f"Warning: No rows updated for task {task_id}")
        except Exception as exc:
            error_details = traceback.format_exc()
            print(f"Error updating ECL engine status in DB for {task_id}: {exc}")
            print(f"Error details:\n{error_details}")

    def generate_batch_config_file(self, run_config: dict, timestamp: str) -> Dict[str, str]:
        """Create a new config file for batch execution with a unique output path."""
        try:
            config = run_config.copy()
            base_output_path = config.get('RUN_SETTING', {}).get('OUTPUT_PATH', '')
            if not base_output_path:
                return {'status': 'Failed', 'error': 'OUTPUT_PATH not found in RUN_SETTING'}

            if '/03_output_folder' in base_output_path:
                base_path = base_output_path.split('/03_output_folder')[0]
                new_output_path = f"{base_path}/03_output_folder/{timestamp}"
            else:
                new_output_path = f"{base_output_path}/{timestamp}"

            config['RUN_SETTING']['OUTPUT_PATH'] = new_output_path
            print(f"Modified OUTPUT_PATH to: {new_output_path}")

            try:
                os.makedirs(new_output_path, exist_ok=True)
                print(f"Created/verified output folder: {new_output_path}")
            except Exception as exc:
                print(f"Failed to create output folder {new_output_path}: {exc}")
                return {'status': 'Failed', 'error': f'Failed to create output folder: {exc}'}

            new_config_filename = f'run_config_file_{timestamp}.json'
            new_config_path = os.path.join(self.base_ecl_engine, new_config_filename)

            with open(new_config_path, 'w') as file_pointer:
                json.dump(config, file_pointer, indent=2)
            print(f"Generated new config file: {new_config_path}")

            return {'status': 'success', 'config_path': new_config_path, 'timestamp': timestamp}
        except Exception as exc:
            print(f"Error generating batch config file: {exc}")
            traceback.print_exc()
            return {'status': 'Failed', 'error': str(exc)}

    def execute_batch_run(self, config_path: str, exit_on_completion: bool = True):
        """Execute a batch run end-to-end."""
        if not config_path:
            raise ValueError("config_path is required")

        try:
            with open(Path(config_path), 'r') as fp:
                run_config = json.load(fp)
        except Exception as exc:
            print(f"Error reading config file: {exc}")
            if exit_on_completion:
                sys.exit(1)
            raise

        task_id = str(uuid.uuid4())
        data_yymm = str(run_config.get('RUN_SETTING', {}).get('DATA_YYMM', ''))
        if not data_yymm:
            data_yymm = datetime.now().strftime('%Y%m%d')
        batch_timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        timestamp = f"Regular_Run_{data_yymm}_{batch_timestamp}"

        config_result = self.generate_batch_config_file(run_config, timestamp)
        if config_result.get('status') != 'success':
            print(f"Error generating batch config file: {config_result.get('error', 'Unknown error')}")
            if exit_on_completion:
                sys.exit(1)
            return {'status': 'Failed', 'error': config_result.get('error', 'Unknown error')}

        new_config_path = config_result['config_path']
        print(f"Using generated config file: {new_config_path}")

        db_config = run_config.get('DB_SETTING', {})
        if not db_config:
            print("Warning: DB_SETTING not found in config file, database operations may fail")

        reporting_date = ''
        if len(data_yymm) >= 8:
            date_str = data_yymm[:8]
            reporting_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        settings = json.dumps({
            "task_id": task_id,
            "timestamp": timestamp,
            "reportingDate": reporting_date,
            "runMode": str(run_config.get('RUN_SETTING', {}).get('RUN_MODE', '')),
            "isBatchRun": True
        })

        now_dt = datetime.now()
        try:
            save_result = self.save_eclengine_record(
                maker='Batch Run',
                time=now_dt,
                settings=settings,
                action='Batch Run',
                status='Running',
                checker='Waiting',
                db_config=db_config
            )
            if save_result:
                print(f"Batch run record saved to database - Task ID: {task_id}, Timestamp: {timestamp}")
            else:
                print("Warning: Failed to save record to database, but continuing execution...")
        except Exception as db_error:
            print(f"Warning: Database error when saving initial record: {db_error}, but continuing execution...")

        try:
            with open(Path(new_config_path), 'r') as fp:
                updated_run_config = json.load(fp)
            updated_run_config['config_path'] = new_config_path
            self.main_fn(run_config=updated_run_config)

            try:
                self.update_eclengine_status_in_db(task_id, 'Completed', db_config)
                print(f"Batch run completed successfully - Task ID: {task_id}")
            except Exception as db_error:
                print(f"Warning: Failed to update database status to Completed: {db_error}")

            if exit_on_completion:
                sys.exit(0)
            return {'status': 'success', 'task_id': task_id, 'timestamp': timestamp}

        except Exception as exc:
            try:
                self.update_eclengine_status_in_db(task_id, 'Failed', db_config)
                print(f"Batch run failed - Task ID: {task_id}")
            except Exception as db_error:
                print(f"Warning: Failed to update database status to Failed: {db_error}")

            print(f"Error in batch run: {exc}")
            traceback.print_exc()
            if exit_on_completion:
                sys.exit(1)
            raise