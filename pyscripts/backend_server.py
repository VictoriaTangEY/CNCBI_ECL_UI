import os
import shutil
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime
import subprocess
import logging
import threading
from queue import Queue
import uuid
from typing import Dict
from concurrent.futures import ProcessPoolExecutor, Future
import time
import zipfile
from io import BytesIO, StringIO
import pyodbc
import sys
from pathlib import Path
import json
import signal
import csv
from ldap3 import Server, Connection, ALL, NTLM
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


################################################################################################################################################################
#                           CONFIGURATIONS
################################################################################################################################################################
"""
This section contains all configurable parameters for the ECL UI system. Modify these values according to deployment environment.

Configuration Categories:
1. Directory Paths           - File system paths for uploads, outputs, etc.
2. ECL Engine Settings       - ECL calculation engine configuration
3. Database Configuration    - SQL Server connection settings
4. LDAP/AD Configuration     - Active Directory authentication settings
5. Report Files              - Output report file names
6. Audit Logs                - Audit trail log file paths
7. Threading Settings        - Concurrent execution settings
8. Logging Settings          - Application logging configuration
"""
# ==============================================================================
# 1. DIRECTORY PATHS
BASE_ROOT = r'/u01/Apps/EY_working'
BASE_UI_ROOT = os.path.join(BASE_ROOT, 'ECL_UI_v0.1')
BASE_DATA_ROOT = os.path.join(BASE_ROOT, '99_data')
BASE_ECL_ENGINE = os.path.join(BASE_ROOT, 'ECL_Engine_v0.4')
BASE_UPLOAD_FOLDER = os.path.join(BASE_UI_ROOT, 'interim')      
BASE_APPROVED_FOLDER = os.path.join(BASE_UI_ROOT, 'approved')    
BASE_OUTPUT_FOLDER = os.path.join(BASE_DATA_ROOT, '03_output_folder')      
BASE_PARAM_FOLDER = os.path.join(BASE_DATA_ROOT, '02_param_upload_folder') 
AUDIT_FOLDER = os.path.join(BASE_UI_ROOT, 'AuditTrial')  
TEMP_LOG_FOLDER = '/tmp'                                  

# ==============================================================================
# 2. ECL ENGINE SETTINGS
ECL_ENGINE_CONFIG = {
    'python_executable': 'python3',           
    'main_script': 'main_ui.py',              
    'config_template': 'run_config_file.json', 
    'process_timeout': 21600,                 
}

CONFIG_FILE_PATH = os.path.join(BASE_ECL_ENGINE, ECL_ENGINE_CONFIG['config_template'])

# ==============================================================================
# 3. REPORTING
REPORT_FILES = {
    'ecl_monthly': 'reporting_ecl_result_to_rmg.xlsx',     
    'ecl_summary': 'reporting_ecl_result_summary.xlsx',    
    'bu_excel': [                                           
        'ecl_result_by_BU_PBG-BB.xlsx',
        'ecl_result_by_BU_PBG-NON-BB.xlsx',
        'ecl_result_by_BU_TMG.xlsx',
        'ecl_result_by_BU_WBG.xlsx'
    ],
    'hkma': 'reporting_ecl_hkma.xlsx',
    'audit_trial': 'reporting_ecl_audit_trial.xlsx',
    'gl_posting': [
        'reporting_ecl_gl_posting.xlsx',
        'Template_GL Posting_Manual Adj.xlsx'
    ]
}

# ==============================================================================
# 4. AUDIT TRIAL
AUDIT_LOGS = {
    'user_role_updates': os.path.join(AUDIT_FOLDER, 'user_role_updates_log.txt'),  
    'user_access': os.path.join(AUDIT_FOLDER, 'user_access_log.txt'),              
    'download': os.path.join(AUDIT_FOLDER, 'download_log.txt'),                    
    'ecl_confirmation': os.path.join(AUDIT_FOLDER, 'ecl_result_confirmation_log.txt'),  
    'parameter_update': os.path.join(AUDIT_FOLDER, 'parameter_update_log.txt'),
    'ecl_job_execution': os.path.join(AUDIT_FOLDER, 'ecl_job_execution_log.txt'),
}

# ==============================================================================
# 5. THREADING SETTINGS
THREADING_CONFIG = {
    'max_workers': 4,         
    'monitor_interval': 1,    
}

# ==============================================================================
# 6. DB CONNECTION
DB_CONFIG = {
    'dsn': 'ECLUATFSDB',
    'username': 'eclappusr',
    'password': os.getenv('DB_PASSWORD', ''),
    'database': 'ey_ecl',
}

DB_DSN = DB_CONFIG['dsn']
DB_USERNAME = DB_CONFIG['username']
DB_PASSWORD = DB_CONFIG['password']
DB_NAME = DB_CONFIG['database']

# ==============================================================================
# 7. LDAP CONNECTION
LDAP_CONFIG = {
    'server': 'ldap://10.30.244.12:389',
    'bind_dn': 'CN=svreclappusr, OU=Service Accounts,OU=Tier1,OU=Admin,OU=HKG,DC=hkg,DC=ho,DC=cncb2',
    'bind_password': os.getenv('LDAP_BIND_PASSWORD', ''),
    'search_base': 'OU=User Accounts,OU=HKG,DC=hkg,DC=ho,DC=cncb2',
    'connection_timeout': 10,
}

LDAP_SERVER = LDAP_CONFIG['server']
LDAP_BIND_DN = LDAP_CONFIG['bind_dn']
LDAP_BIND_PASSWORD = LDAP_CONFIG['bind_password']
LDAP_SEARCH_BASE = LDAP_CONFIG['search_base']

# ==============================================================================
# 8. LOG SETTINGS
LOG_CONFIG = {
    'level': logging.INFO,
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'dir': Path(__file__).parent / 'logs',
    'file': 'backend_server.log'
}

################################################################################################################################################################
#                           BASIC SETTINGS
################################################################################################################################################################
"""
This section contains 

Configuration Categories:
1. Logging Settings          - Check the log via sudo journalctl -u flaskapp -n 100 --no-pager
2. Threading Settings        - 
3. Polling Settings          - 
"""
# ==============================================================================
# 1. LOGGING SETTINGS
log_dir = LOG_CONFIG['dir']
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=LOG_CONFIG['level'],
    format=LOG_CONFIG['format'],
    handlers=[
        logging.FileHandler(log_dir / LOG_CONFIG['file']),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==============================================================================
# 2. THREADING SETTINGS
task_queue = Queue()
task_status: Dict[str, dict] = {}
executor = ProcessPoolExecutor(max_workers=THREADING_CONFIG['max_workers'])
future_to_task_id = {} 
future_lock = threading.Lock()

# ==============================================================================
# 3. POLLING SETTINGS
def format_timestamp_for_display(timestamp):
    """Format timestamp from Adhoc_Run_{DATA_YYMM}_{YYYYMMDDHHMMSS} or YYYYMMDDHHMMSS to YYYY-MM-DD HH:MM:SS"""
    if not timestamp:
        return timestamp

    try:
        # Extract time part from new format (last 14 characters after last underscore)
        if '_' in timestamp:
            parts = timestamp.split('_')
            if len(parts) >= 3:
                time_part = parts[-1]
            else:
                time_part = timestamp
        else:
            time_part = timestamp
        
        # Validate time part is 14 digits
        if len(time_part) != 14 or not time_part.isdigit():
            return timestamp
        
        year = time_part[:4]
        month = time_part[4:6]
        day = time_part[6:8]
        hour = time_part[8:10]
        minute = time_part[10:12]
        second = time_part[12:14]
        return f"{year}-{month}-{day} {hour}:{minute}:{second}"
    except:
        return timestamp

def process_ecl_task(command: str, data: dict):
    import os
    logger.info(f"Running ECL task with params: {data}")
    logger.info(f"Command to execute: {command}")
    logger.info(f"Working directory: {BASE_ECL_ENGINE}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Environment variables: {dict(os.environ)}")
    logger.info(f"Process ID: {os.getpid()}")
    
    # Check if ECL main script exists
    main_py_path = os.path.join(BASE_ECL_ENGINE, ECL_ENGINE_CONFIG['main_script'])
    if not os.path.exists(main_py_path):
        error_msg = f"ECL main script not found at {main_py_path}"
        logger.error(error_msg)
        return {'status': 'Failed', 'error': error_msg}
    
    # Check if main_ui.py is executable
    if not os.access(main_py_path, os.R_OK):
        error_msg = f"ECL main script is not readable at {main_py_path}"
        logger.error(error_msg)
        return {'status': 'Failed', 'error': error_msg}
    
    try:
        # Use subprocess.run with nohup to make ECL process independent of Gunicorn
        # This is the simplest solution to prevent termination by Gunicorn restart
        nohup_command = f"nohup {command} > /tmp/ecl_{os.getpid()}.log 2>&1"
        logger.info(f"Executing nohup command: {nohup_command}")
        
        process = subprocess.run(
            nohup_command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=BASE_ECL_ENGINE,
            env=os.environ.copy(),
            timeout=21600  # 6 hours timeout
        )
        
        logger.info(f"Process completed with return code: {process.returncode}")
        logger.info(f"STDOUT: {process.stdout}")
        logger.info(f"STDERR: {process.stderr}")
        
        if process.returncode != 0:
            error_message = process.stderr or "Unknown error occurred"
            logger.error(f"ECL Engine failed with return code {process.returncode}")
            logger.error(f"Error message: {error_message}")
            return {'status': 'Failed', 'error': error_message, 'stdout': process.stdout, 'stderr': process.stderr, 'return_code': process.returncode}
        else:
            logger.info("ECL Engine completed successfully")
            return {'status': 'Completed', 'output': process.stdout}
    
    except subprocess.TimeoutExpired:
        logger.error(f"ECL Engine process timed out after 6 hours")
        return {'status': 'Failed', 'error': 'Process timed out after 6 hours'}
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Exception in process_ecl_task: {str(e)}")
        logger.error(f"Full traceback: {error_details}")
        return {'status': 'Failed', 'error': str(e), 'traceback': error_details}

def monitor_futures():
    while True:
        try:
            with future_lock:
                # Process completed tasks
                for future, task_id in list(future_to_task_id.items()):
                    if future.done() and task_status[task_id]['status'] == 'Running':
                        try:
                            result = future.result()
                            task_status[task_id].update(result)
                            # Keep the task status in memory even after completion
                            # Don't remove from future_to_task_id to prevent 404 errors
                            logger.info(f"Task {task_id} completed with status: {result.get('status', 'unknown')}")
                            
                            # Check if this is a pre-run validation task
                            if task_status[task_id].get('is_prerun_validation'):
                                # Update pre-run validation status
                                update_prerun_validation_status(task_id, result.get('status', 'unknown'))
                                logger.info(f"Updated pre-run validation status for task {task_id} to {result.get('status', 'unknown')}")
                            elif task_status[task_id].get('is_generate_report'):
                                # Update reporting status
                                update_reporting_status_in_db(task_id, result.get('status', 'unknown'))
                                logger.info(f"Updated reporting status for task {task_id} to {result.get('status', 'unknown')}")
                            else:
                                # Update regular ECL engine status
                                update_eclengine_status_in_db(task_id, result.get('status', 'unknown'))
                        
                        except Exception as e:
                            logger.error(f"Error processing completed task {task_id}: {str(e)}")
                            task_status[task_id].update({'status': 'Failed', 'error': str(e)})
                            
                            # Check if this is a pre-run validation task
                            if task_status[task_id].get('is_prerun_validation'):
                                update_prerun_validation_status(task_id, 'Failed')
                                logger.info(f"Updated pre-run validation status for task {task_id} to failed")
                            elif task_status[task_id].get('is_generate_report'):
                                update_reporting_status_in_db(task_id, 'Failed')
                                logger.info(f"Updated reporting status for task {task_id} to failed")
                            else:
                                update_eclengine_status_in_db(task_id, 'Failed')
                    elif task_status[task_id]['status'] == 'Running':
                        task_status[task_id]['status'] = 'Running'
                        
                        # Check if this is a pre-run validation task
                        if task_status[task_id].get('is_prerun_validation'):
                            update_prerun_validation_status(task_id, 'Running')
                        elif task_status[task_id].get('is_generate_report'):
                            update_reporting_status_in_db(task_id, 'Running')
                        else:
                            update_eclengine_status_in_db(task_id, 'Running')
        except Exception as e:
            logger.error(f"Error in monitor_futures: {str(e)}")
        time.sleep(1)

monitor_thread = threading.Thread(target=monitor_futures, daemon=True)
monitor_thread.start()

################################################################################################################################################################
#                           DB FUNCTIONS
################################################################################################################################################################
"""
This section contains 

Configuration Categories:
1. Test                       - 
2. Parameter                  - 
3. Run Management             - 
4. Role Management            -  
5. Initialize DB Tables       -  
"""
# ==============================================================================
# 1. TEST
def test_db_connection():
    """Test database connection and log the result"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        # Test basic connection
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()
        # Check if target database exists
        cursor.execute(f"SELECT DB_ID('{DB_NAME}') as db_id")
        db_id = cursor.fetchone()[0]
        if not db_id:
            logger.error(f"Target database '{DB_NAME}' does not exist")
            return False
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database connection Failed: {str(e)}")
        return False

# ==============================================================================
# 2. PARAMETER
def create_ui_parameter_table():
    """Create the UI_Parameter_records table if it doesn't exist"""
    try:
        # First test connection
        if not test_db_connection():
            logger.error("Cannot create table - database connection Failed")
            return False
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        # Check if table exists first in the specific database
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'UI_Parameter_records'
        """)
        table_exists = cursor.fetchone()[0] > 0
        if table_exists:
            logger.info("UI_Parameter_records table already exists")
            return True
        # Create UI_Parameter_records table in the specific database
        logger.info("Creating UI_Parameter_records table...")
        cursor.execute(f"""
            CREATE TABLE [{DB_NAME}].[dbo].[UI_Parameter_records] (
                id INT IDENTITY(1,1) PRIMARY KEY,
                maker NVARCHAR(255) NOT NULL,
                time DATETIME NOT NULL,
                type NVARCHAR(50) NOT NULL,
                category NVARCHAR(255),
                action NVARCHAR(500) NOT NULL,
                status NVARCHAR(50) NOT NULL,
                checker NVARCHAR(255),
                timestamp NVARCHAR(50),
                suffix NVARCHAR(255),
                file_path NVARCHAR(500),
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        conn.close()
        logger.info("UI Parameter records table created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating UI Parameter table: {str(e)}")
        return False
 
def create_prerun_validation_table():
    """Create the UI_prerun_validation_records table if it doesn't exist"""
    try:
        # First test connection
        if not test_db_connection():
            logger.error("Cannot create table - database connection Failed")
            return False
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        # Check if table exists first in the specific database
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'UI_prerun_validation_records'
        """)
        table_exists = cursor.fetchone()[0] > 0
        if table_exists:
            # Check if new columns exist, if not add them
            try:
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM [{DB_NAME}].INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'UI_prerun_validation_records' AND COLUMN_NAME = 'upload_timestamp'
                """)
                upload_timestamp_exists = cursor.fetchone()[0] > 0
                
                if not upload_timestamp_exists:
                    logger.info("Adding upload_timestamp column to existing table")
                    cursor.execute(f"""
                        ALTER TABLE [{DB_NAME}].[dbo].[UI_prerun_validation_records]
                        ADD upload_timestamp NVARCHAR(20)
                    """)
                
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM [{DB_NAME}].INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'UI_prerun_validation_records' AND COLUMN_NAME = 'upload_type'
                """)
                upload_type_exists = cursor.fetchone()[0] > 0
                
                if not upload_type_exists:
                    logger.info("Adding upload_type column to existing table")
                    cursor.execute(f"""
                        ALTER TABLE [{DB_NAME}].[dbo].[UI_prerun_validation_records]
                        ADD upload_type NVARCHAR(50)
                    """)
                
                cursor.execute(f"""
                    SELECT CHARACTER_MAXIMUM_LENGTH
                    FROM [{DB_NAME}].INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'UI_prerun_validation_records' AND COLUMN_NAME = 'timestamp'
                """)
                timestamp_length = cursor.fetchone()
                if timestamp_length and timestamp_length[0] and timestamp_length[0] < 50:
                    logger.info("Altering timestamp column length to 50 for new format support")
                    cursor.execute(f"""
                        ALTER TABLE [{DB_NAME}].[dbo].[UI_prerun_validation_records]
                        ALTER COLUMN timestamp NVARCHAR(50) NOT NULL
                    """)
            
            except Exception as e:
                logger.warning(f"Could not add new columns to existing table: {str(e)}")
            
            return True
            
        # Create UI_prerun_validation_records table in the specific database
        logger.info("Creating UI_prerun_validation_records table...")
        cursor.execute(f"""
            CREATE TABLE [{DB_NAME}].[dbo].[UI_prerun_validation_records] (
                id INT IDENTITY(1,1) PRIMARY KEY,
                maker NVARCHAR(255) NOT NULL,
                time DATETIME NOT NULL,
                type NVARCHAR(50) NOT NULL,
                category NVARCHAR(255),
                action NVARCHAR(500) DEFAULT 'Pre-run Validation',
                status NVARCHAR(20) DEFAULT 'Running',
                task_id NVARCHAR(255) NOT NULL,
                timestamp NVARCHAR(50) NOT NULL,
                created_at DATETIME DEFAULT GETDATE(),
                completed_at DATETIME NULL
            )
        """)
        conn.close()
        logger.info("UI_prerun_validation_records table created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating UI_prerun_validation_records table: {str(e)}")
        return False
 
def save_parameter_record(maker, time, type_, category, action, status, checker, timestamp=None, suffix=None, file_path=None):
    """Save parameter/adjustment record to database"""
    try:
        # Ensure table exists
        create_ui_parameter_table() # Changed from create_review_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO [{DB_NAME}].[dbo].[UI_Parameter_records] (maker, time, type, category, action, status, checker, timestamp, suffix, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (maker, time, type_, category, action, status, checker, timestamp, suffix, file_path))
        conn.close()
        logger.info(f"Successfully saved record: {type_} - {action}")
        return True
    except Exception as e:
        logger.error(f"Error saving parameter record: {str(e)}")
        return False

def get_review_records():
    """Get all review records from database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, maker, time, type, category, action, status, checker, timestamp, suffix, file_path
            FROM [{DB_NAME}].[dbo].[UI_Parameter_records]
            ORDER BY time DESC
        """)
        records = []
        for row in cursor.fetchall():
            records.append({
                'id': row[0],
                'maker': row[1],
                'time': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else '',
                'type': row[3],
                'category': row[4] or '',
                'action': row[5],
                'status': row[6],
                'checker': row[7] or 'Waiting',
                'timestamp': row[8] or '',
                'suffix': row[9] or '',
                'file_path': row[10] or ''
            })
        conn.close()
        return records
    except Exception as e:
        logger.error(f"Error getting review records: {str(e)}")
        return []

# ==============================================================================
# 3. RUN MANAGEMENT
def create_ui_eclengine_table():
    """Create the UI_eclengine_records table if it doesn't exist"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            IF NOT EXISTS (
                SELECT * FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'UI_eclengine_records'
            )
            BEGIN
                CREATE TABLE [{DB_NAME}].[dbo].[UI_eclengine_records] (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    maker NVARCHAR(255) NOT NULL,
                    time DATETIME NOT NULL,
                    settings NVARCHAR(MAX),
                    action NVARCHAR(500) NOT NULL,
                    status NVARCHAR(50) NOT NULL,
                    checker NVARCHAR(255),
                    created_at DATETIME DEFAULT GETDATE()
                )
            END
        """)
        conn.close()
        logger.info("UI_eclengine_records table checked/created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating UI_eclengine_records table: {str(e)}")
        return False
 
def create_reporting_records_table():
    """Create the UI_reporting_records table if it doesn't exist"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            IF NOT EXISTS (
                SELECT * FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'UI_reporting_records'
            )
            BEGIN
                CREATE TABLE [{DB_NAME}].[dbo].[UI_reporting_records] (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    task_id NVARCHAR(255) NOT NULL,
                    maker NVARCHAR(255) NOT NULL,
                    time DATETIME NOT NULL,
                    settings NVARCHAR(MAX) NOT NULL,
                    action NVARCHAR(500) NOT NULL,
                    status NVARCHAR(50) NOT NULL,
                    checker NVARCHAR(255) DEFAULT 'Waiting',
                    original_timestamp NVARCHAR(50) NOT NULL,
                    created_at DATETIME DEFAULT GETDATE(),
                    completed_at DATETIME NULL
                )
            END
        """)
        conn.close()
        logger.info("UI_reporting_records table checked/created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating UI_reporting_records table: {str(e)}")
        return False

def save_reporting_record(task_id, maker, time, settings, action, status, checker, original_timestamp):
    """Save reporting record to database"""
    try:
        create_reporting_records_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO [{DB_NAME}].[dbo].[UI_reporting_records]
            (task_id, maker, time, settings, action, status, checker, original_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (task_id, maker, time, settings, action, status, checker, original_timestamp))
        conn.close()
        logger.info(f"Successfully saved reporting record: {task_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving reporting record: {str(e)}")
        return False

def get_reporting_records():
    """Get all reporting records from database"""
    try:
        create_reporting_records_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, task_id, maker, time, settings, action, status, checker, original_timestamp, created_at, completed_at
            FROM [{DB_NAME}].[dbo].[UI_reporting_records]
            ORDER BY created_at DESC
        """)
        records = []
        for row in cursor.fetchall():
            settings_dict = {}
            try:
                settings_dict = json.loads(row[4]) if row[4] else {}
            except:
                pass
            records.append({
                'id': row[0],
                'task_id': row[1],
                'maker': row[2],
                'time': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else '',
                'settings': settings_dict,
                'action': row[5],
                'status': row[6],
                'checker': row[7],
                'original_timestamp': row[8],
                'created_at': row[9].strftime('%Y-%m-%d %H:%M:%S') if row[9] else '',
                'completed_at': row[10].strftime('%Y-%m-%d %H:%M:%S') if row[10] else ''
            })
        conn.close()
        return records
    except Exception as e:
        logger.error(f"Error getting reporting records: {str(e)}")
        return []

def update_reporting_status(task_id, status):
    """Update reporting record status in database"""
    try:
        create_reporting_records_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        if status == 'Completed':
            cursor.execute(f"""
                UPDATE [{DB_NAME}].[dbo].[UI_reporting_records]
                SET status = ?, completed_at = GETDATE()
                WHERE task_id = ?
            """, (status, task_id))
        else:
            cursor.execute(f"""
                UPDATE [{DB_NAME}].[dbo].[UI_reporting_records]
                SET status = ?
                WHERE task_id = ?
            """, (status, task_id))
        conn.close()
        logger.info(f"Updated reporting status for {task_id} to {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating reporting status: {str(e)}")
        return False

def get_reporting_record(task_id):
    """Get reporting record by task_id"""
    try:
        create_reporting_records_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, task_id, maker, time, settings, action, status, checker, original_timestamp, created_at, completed_at
            FROM [{DB_NAME}].[dbo].[UI_reporting_records]
            WHERE task_id = ?
        """, (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            settings_dict = {}
            try:
                settings_dict = json.loads(row[4]) if row[4] else {}
            except:
                pass
            return {
                'id': row[0],
                'task_id': row[1],
                'maker': row[2],
                'time': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else '',
                'settings': settings_dict,
                'action': row[5],
                'status': row[6],
                'checker': row[7],
                'original_timestamp': row[8],
                'created_at': row[9].strftime('%Y-%m-%d %H:%M:%S') if row[9] else '',
                'completed_at': row[10].strftime('%Y-%m-%d %H:%M:%S') if row[10] else ''
            }
        return None
    except Exception as e:
        logger.error(f"Error getting reporting record: {str(e)}")
        return None

def get_eclengine_record_by_id(record_id):
    """Get ECL engine record by ID"""
    try:
        create_ui_eclengine_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, maker, time, settings, action, status, checker, created_at
            FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            WHERE id = ?
        """, (record_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            settings_dict = {}
            try:
                settings_dict = json.loads(row[3]) if row[3] else {}
            except:
                pass
            return {
                'id': row[0],
                'maker': row[1],
                'time': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else '',
                'settings': settings_dict,
                'action': row[4],
                'status': row[5],
                'checker': row[6],
                'created_at': row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else ''
            }
        return None
    except Exception as e:
        logger.error(f"Error getting ECL engine record by ID: {str(e)}")
        return None

def save_eclengine_record(maker, time, settings, action, status, checker):
    """Save run management record to database"""
    try:
        create_ui_eclengine_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO [{DB_NAME}].[dbo].[UI_eclengine_records]
            (maker, time, settings, action, status, checker)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (maker, time, settings, action, status, checker))
        conn.close()
        logger.info(f"Successfully saved ECL engine record: {action}")
        return True
    except Exception as e:
        logger.error(f"Error saving ECL engine record: {str(e)}")
        return False

def get_eclengine_records():
    """Get all run management records from database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, maker, time, settings, action, status, checker, created_at
            FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            ORDER BY time DESC
        """)
        records = []
        for row in cursor.fetchall():
            records.append({
                'id': row[0],
                'maker': row[1],
                'time': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else '',
                'settings': row[3] or '',
                'action': row[4],
                'status': row[5],
                'checker': row[6] or 'Waiting',
                'created_at': row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else ''
            })
        conn.close()
        return records
    except Exception as e:
        logger.error(f"Error getting ECL engine records: {str(e)}")
        return []

def update_eclengine_status_in_db(task_id, status):
    """
    Update the status of a task in the UI_eclengine_records table by task_id (in settings JSON).
    """
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[UI_eclengine_records]
            SET status = ?
            WHERE settings IS NOT NULL
            AND ISJSON(settings) = 1
            AND JSON_VALUE(settings, '$.task_id') = ?
        """, (status, task_id))
        
        rows_affected = cursor.rowcount
        conn.close()
       
    except Exception as e:
        logger.error(f"Error updating ECL engine status in DB for {task_id}: {str(e)}")

def update_reporting_status_in_db(task_id, status):
    """
    Update the status of a task in the UI_reporting_records table by task_id.
    """
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        if status == 'Completed':
            cursor.execute(f"""
                UPDATE [{DB_NAME}].[dbo].[UI_reporting_records]
                SET status = ?, completed_at = GETDATE()
                WHERE task_id = ?
            """, (status, task_id))
        else:
            cursor.execute(f"""
                UPDATE [{DB_NAME}].[dbo].[UI_reporting_records]
                SET status = ?
                WHERE task_id = ?
            """, (status, task_id))
        
        # Check if any rows were affected
        rows_affected = cursor.rowcount
        conn.close()
        
        if rows_affected > 0:
            logger.info(f"Updated reporting status for task {task_id} to {status} ({rows_affected} row(s) affected)")
        else:
            logger.warning(f"No rows updated for reporting task {task_id}.")
    
    except Exception as e:
        logger.error(f"Error updating reporting status for task {task_id}: {str(e)}")
        # Log additional debugging information
        try:
            # Try to get the problematic record for debugging
            conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT id, settings, status
                FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
                WHERE settings IS NOT NULL
                AND (ISJSON(settings) = 0 OR JSON_VALUE(settings, '$.task_id') = ?)
            """, (task_id,))
            debug_rows = cursor.fetchall()
            conn.close()
            
            if debug_rows:
                logger.error(f"Debug info - Found {len(debug_rows)} potentially problematic records:")
                for row in debug_rows:
                    logger.error(f"  ID: {row[0]}, Status: {row[2]}, Settings: {row[1]}")
            else:
                logger.error(f"Debug info - No records found with task_id {task_id}")
        
        except Exception as debug_e:
            logger.error(f"Error during debug query: {str(debug_e)}")
 
# ==============================================================================
# 4. ROLE MANAGEMENT
def create_ui_user_maintenance_table():
    """Create the UI_user_maintenance table if it doesn't exist"""
    try:
        if not test_db_connection():
            logger.error("Cannot create table - database connection Failed")
            return False
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'UI_user_maintenance'
        """)
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            logger.info("Creating UI_user_maintenance table...")
            cursor.execute(f"""
                CREATE TABLE [{DB_NAME}].[dbo].[UI_user_maintenance] (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    user_name NVARCHAR(255) NOT NULL,
                    login_name NVARCHAR(255) NOT NULL,
                    default_role NVARCHAR(255) NOT NULL,
                    updated_by NVARCHAR(255) NOT NULL,
                    time DATETIME NOT NULL,
                    email NVARCHAR(255),
                    mobile_no NVARCHAR(50),
                    phone_no NVARCHAR(50),
                    remark NVARCHAR(MAX),
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            logger.info("UI_user_maintenance table created successfully")
        else:
            logger.info("UI_user_maintenance table already exists")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating UI_user_maintenance table: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def create_ui_role_maintenance_table():
    """Create the UI_role_maintenance table if it doesn't exist"""
    try:
        if not test_db_connection():
            logger.error("Cannot create table - database connection Failed")
            return False
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'UI_role_maintenance'
        """)
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            logger.info("Creating UI_role_maintenance table...")
            cursor.execute(f"""
                CREATE TABLE [{DB_NAME}].[dbo].[UI_role_maintenance] (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    role_name NVARCHAR(255) NOT NULL,
                    status NVARCHAR(50) NOT NULL,
                    updated_by NVARCHAR(255) NOT NULL,
                    time DATETIME NOT NULL,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            logger.info("UI_role_maintenance table created successfully")
        else:
            logger.info("UI_role_maintenance table already exists")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating UI_role_maintenance table: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def create_ui_function_maintenance_table():
    """Create the UI_function_maintenance table if it doesn't exist"""
    try:
        if not test_db_connection():
            logger.error("Cannot create table - database connection Failed")
            return False
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = 'UI_function_maintenance'
        """)
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            logger.info("Creating UI_function_maintenance table...")
            cursor.execute(f"""
                CREATE TABLE [{DB_NAME}].[dbo].[UI_function_maintenance] (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    function_name NVARCHAR(255) NOT NULL,
                    status NVARCHAR(50) NOT NULL,
                    updated_by NVARCHAR(255) NOT NULL,
                    time DATETIME NOT NULL,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            logger.info("UI_function_maintenance table created successfully")
        else:
            logger.info("UI_function_maintenance table already exists")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating UI_function_maintenance table: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def create_ui_role_function_table(role_name):
    """Create a UI_role_function_<rolename> table if it doesn't exist and populate with all functions"""
    try:
        if not test_db_connection():
            logger.error("Cannot create table - database connection Failed")
            return False
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        table_name = f"UI_role_function_{role_name.replace(' ', '_').replace('-', '_')}"
        
        # Check if table exists
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = '{table_name}'
        """)
        table_exists = cursor.fetchone()[0] > 0
        
        if not table_exists:
            logger.info(f"Creating {table_name} table...")
            cursor.execute(f"""
                CREATE TABLE [{DB_NAME}].[dbo].[{table_name}] (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    function_name NVARCHAR(255) NOT NULL,
                    status NVARCHAR(50) NOT NULL,
                    updated_by NVARCHAR(255) NOT NULL,
                    time DATETIME NOT NULL,
                    created_at DATETIME DEFAULT GETDATE()
                )
            """)
            logger.info(f"{table_name} table created successfully")
        
        # Always populate table with all existing functions (status='Inactive' by default)
        cursor.execute(f"""
            SELECT function_name FROM [{DB_NAME}].[dbo].[UI_function_maintenance]
            WHERE status = 'Active'
        """)
        all_functions = [row[0] for row in cursor.fetchall()]
        
        if all_functions:
            # Get existing function mappings for this role
            if table_exists:
                cursor.execute(f"""
                    SELECT function_name FROM [{DB_NAME}].[dbo].[{table_name}]
                """)
                existing_functions = [row[0] for row in cursor.fetchall()]
            else:
                existing_functions = []
            
            # Find functions that need to be added
            missing_functions = [func for func in all_functions if func not in existing_functions]
            
            if missing_functions:
                current_time = datetime.now()
                for function_name in missing_functions:
                    cursor.execute(f"""
                        INSERT INTO [{DB_NAME}].[dbo].[{table_name}]
                        (function_name, status, updated_by, time)
                        VALUES (?, ?, ?, ?)
                    """, (function_name, 'Inactive', 'System', current_time))
                
                logger.info(f"Added {len(missing_functions)} missing functions to {table_name}")
            else:
                logger.info(f"All functions already exist in {table_name}")
        else:
            logger.warning(f"No active functions found to populate {table_name} table")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating/populating {table_name} table: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def save_user_record(user_name, login_name, default_role, updated_by, time, email=None, mobile_no=None, phone_no=None, remark=None):
    """Save user record to database"""
    try:
        create_ui_user_maintenance_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO [{DB_NAME}].[dbo].[UI_user_maintenance]
            (user_name, login_name, default_role, updated_by, time, email, mobile_no, phone_no, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_name, login_name, default_role, updated_by, time, email, mobile_no, phone_no, remark))
        conn.close()
        logger.info(f"Successfully saved user record: {user_name}")
        
        # Log audit trail
        details = f"Added new user: {user_name} with role: {default_role}"
        log_user_role_update("Add New User", updated_by, "Role Management", details)
        
        return True
    except Exception as e:
        logger.error(f"Error saving user record: {str(e)}")
        return False

def get_user_records():
    """Get all user records from database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, user_name, login_name, default_role, updated_by, time, email, mobile_no, phone_no, remark
            FROM [{DB_NAME}].[dbo].[UI_user_maintenance]
            ORDER BY time DESC
        """)
        records = []
        for row in cursor.fetchall():
            records.append({
                'id': row[0],
                'userName': row[1],
                'loginName': row[2],
                'defaultRole': row[3],
                'updatedBy': row[4],
                'time': row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else '',
                'email': row[6] or '',
                'mobileNo': row[7] or '',
                'phoneNo': row[8] or '',
                'remark': row[9] or ''
            })
        conn.close()
        return records
    except Exception as e:
        logger.error(f"Error getting user records: {str(e)}")
        return []

def export_user_records_to_csv():
    """Export all user records from database to CSV format"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, user_name, login_name, default_role, updated_by, time, email, mobile_no, phone_no, remark
            FROM [{DB_NAME}].[dbo].[UI_user_maintenance]
            ORDER BY time DESC
        """)
        
        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['User Name', 'Login Name', 'Default Role', 'Updated By', 'Time', 'Email', 'Mobile No', 'Phone No', 'Remark'])
        
        # Write data rows
        for row in cursor.fetchall():
            writer.writerow([
                row[1] or '',  # user_name
                row[2] or '',  # login_name
                row[3] or '',  # default_role
                row[4] or '',  # updated_by
                row[5].strftime('%Y-%m-%d %H:%M:%S') if row[5] else '',  # time
                row[6] or '',  # email
                row[7] or '',  # mobile_no
                row[8] or '',  # phone_no
                row[9] or ''   # remark
            ])
        
        conn.close()
        
        # Convert StringIO to BytesIO for download
        csv_data = output.getvalue()
        output.close()
        csv_bytes = BytesIO(csv_data.encode('utf-8-sig'))  # utf-8-sig for Excel compatibility
        
        return csv_bytes
    except Exception as e:
        logger.error(f"Error exporting user records to CSV: {str(e)}")
        return None

def update_user_record(user_id, user_name, default_role, email, mobile_no, phone_no, remark, updated_by):
    """Update user record in database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[UI_user_maintenance]
            SET user_name = ?, default_role = ?, email = ?, mobile_no = ?, phone_no = ?, remark = ?, updated_by = ?, time = GETDATE()
            WHERE id = ?
        """, (user_name, default_role, email, mobile_no, phone_no, remark, updated_by, user_id))
        conn.close()
        logger.info(f"Successfully updated user record: {user_name}")
        
        # Log audit trail
        details = f"Updated user: {user_name} with role: {default_role}"
        log_user_role_update("Edit User", updated_by, "Role Management", details)
        
        return True
    except Exception as e:
        logger.error(f"Error updating user record: {str(e)}")
        return False

def save_role_record(role_name, status, updated_by, time):
    """Save role record to database"""
    try:
        logger.info(f"Starting save_role_record with params: role_name={role_name}, status={status}, updated_by={updated_by}, time={time}")
        
        # Test database connection first
        if not test_db_connection():
            logger.error("Database connection Failed in save_role_record")
            return False
        
        # Create table if not exists
        table_created = create_ui_role_maintenance_table()
        if not table_created:
            logger.error("Failed to create UI_role_maintenance table")
            return False
        
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        logger.info(f"Executing INSERT statement for role: {role_name}")
        cursor.execute(f"""
            INSERT INTO [{DB_NAME}].[dbo].[UI_role_maintenance]
            (role_name, status, updated_by, time)
            VALUES (?, ?, ?, ?)
        """, (role_name, status, updated_by, time))
        
        conn.close()
        logger.info(f"Successfully saved role record: {role_name}")
        
        # Log audit trail
        details = f"Added new role: {role_name} with status: {status}"
        log_user_role_update("Add New Role", updated_by, "Role Management", details)
        
        return True
    except Exception as e:
        logger.error(f"Error saving role record: {str(e)}")
        logger.error(f"Full exception details: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def get_role_records():
    """Get all role records from database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, role_name, status, updated_by, time
            FROM [{DB_NAME}].[dbo].[UI_role_maintenance]
            ORDER BY time DESC
        """)
        records = []
        for row in cursor.fetchall():
            records.append({
                'id': row[0],
                'roleName': row[1],
                'status': row[2],
                'updatedBy': row[3],
                'time': row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else ''
            })
        conn.close()
        return records
    except Exception as e:
        logger.error(f"Error getting role records: {str(e)}")
        return []

def initialize_role_function_tables():
    """Create role function tables for all existing roles"""
    try:
        # Get all existing roles
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT role_name
            FROM [{DB_NAME}].[dbo].[UI_role_maintenance]
            WHERE status = 'Active'
        """)
        roles = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Create role function table for each role
        for role_name in roles:
            logger.info(f"Initializing role function table for role: {role_name}")
            create_ui_role_function_table(role_name)
            
        return True
    except Exception as e:
        logger.error(f"Error initializing role function tables: {str(e)}")
        return False

def update_role_record(role_id, role_name, status, updated_by):
    """Update role record in database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[UI_role_maintenance]
            SET role_name = ?, status = ?, updated_by = ?, time = GETDATE()
            WHERE id = ?
        """, (role_name, status, updated_by, role_id))
        conn.close()
        logger.info(f"Successfully updated role record: {role_name}")
        
        # Log audit trail
        details = f"Updated role: {role_name} with status: {status}"
        log_user_role_update("Edit Role", updated_by, "Role Management", details)
        
        return True
    except Exception as e:
        logger.error(f"Error updating role record: {str(e)}")
        return False

def save_function_record(function_name, status, updated_by, time):
    """Save function record to database"""
    try:
        create_ui_function_maintenance_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO [{DB_NAME}].[dbo].[UI_function_maintenance]
            (function_name, status, updated_by, time)
            VALUES (?, ?, ?, ?)
        """, (function_name, status, updated_by, time))
        conn.close()
        logger.info(f"Successfully saved function record: {function_name}")
        
        # Log audit trail
        details = f"Added new function: {function_name} with status: {status}"
        log_user_role_update("Add New Function", updated_by, "Role Management", details)
        
        return True
    except Exception as e:
        logger.error(f"Error saving function record: {str(e)}")
        return False

def get_function_records():
    """Get all function records from database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, function_name, status, updated_by, time
            FROM [{DB_NAME}].[dbo].[UI_function_maintenance]
            ORDER BY time DESC
        """)
        records = []
        for row in cursor.fetchall():
            records.append({
                'id': row[0],
                'name': row[1],
                'status': row[2],
                'updatedBy': row[3],
                'time': row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else ''
            })
        conn.close()
        return records
    except Exception as e:
        logger.error(f"Error getting function records: {str(e)}")
        return []

def update_function_record(function_id, function_name, status, updated_by):
    """Update function record in database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[UI_function_maintenance]
            SET function_name = ?, status = ?, updated_by = ?, time = GETDATE()
            WHERE id = ?
        """, (function_name, status, updated_by, function_id))
        conn.close()
        logger.info(f"Successfully updated function record: {function_name}")
        
        # Log audit trail
        details = f"Updated function: {function_name} with status: {status}"
        log_user_role_update("Edit Function", updated_by, "Role Management", details)
        
        return True
    except Exception as e:
        logger.error(f"Error updating function record: {str(e)}")
        return False

def save_role_function_record(role_name, function_name, status, updated_by, time):
    """Save role-function record to database"""
    try:
        create_ui_role_function_table(role_name)
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        table_name = f"UI_role_function_{role_name.replace(' ', '_').replace('-', '_')}"
        cursor.execute(f"""
            INSERT INTO [{DB_NAME}].[dbo].[{table_name}]
            (function_name, status, updated_by, time)
            VALUES (?, ?, ?, ?)
        """, (function_name, status, updated_by, time))
        conn.close()
        logger.info(f"Successfully saved role-function record: {role_name} - {function_name}")
        return True
    except Exception as e:
        logger.error(f"Error saving role-function record: {str(e)}")
        return False

def get_role_function_records(role_name):
    """Get all role-function records for a specific role from database"""
    try:
        # Ensure the table exists and is populated with all functions
        create_ui_role_function_table(role_name)
        
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        table_name = f"UI_role_function_{role_name.replace(' ', '_').replace('-', '_')}"
        cursor.execute(f"""
            SELECT id, function_name, status, updated_by, time
            FROM [{DB_NAME}].[dbo].[{table_name}]
            ORDER BY time DESC
        """)
        records = []
        for row in cursor.fetchall():
            records.append({
                'id': row[0],
                'functionName': row[1],
                'status': row[2],
                'updatedBy': row[3],
                'time': row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else ''
            })
        conn.close()
        return records
    except Exception as e:
        logger.error(f"Error getting role-function records: {str(e)}")
        return []

def update_role_function_record(role_name, function_name, status, updated_by):
    """Update role-function record in database"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        table_name = f"UI_role_function_{role_name.replace(' ', '_').replace('-', '_')}"
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[{table_name}]
            SET status = ?, updated_by = ?, time = GETDATE()
            WHERE function_name = ?
        """, (status, updated_by, function_name))
        conn.close()
        logger.info(f"Successfully updated role-function record: {role_name} - {function_name}")
        
        # Log audit trail
        details = f"Updated role-function mapping: {role_name} - {function_name} with status: {status}"
        log_user_role_update("Edit Role-Function", updated_by, "Role Management", details)
        
        return True
    except Exception as e:
        logger.error(f"Error updating role-function record: {str(e)}")
        return False

# ==============================================================================
# 5. INITIALIZE DB TABLES
logger.info("Initializing database tables...")
try:
    if test_db_connection():
        logger.info("Database connection successful, creating tables if needed...")
        create_ui_parameter_table()
        create_ui_user_maintenance_table()
        create_ui_role_maintenance_table()
        create_ui_function_maintenance_table()
        create_prerun_validation_table()
        create_ui_eclengine_table()
        create_reporting_records_table()
        initialize_role_function_tables()
        logger.info("Database table initialization completed successfully")
    else:
        logger.warning("Database connection failed during initialization")
except Exception as e:
    logger.error(f"Error during database initialization: {str(e)}")

################################################################################################################################################################
#                           MAIN FUNCTIONS
################################################################################################################################################################
"""
This section contains 

Configuration Categories:
1. Parameter                 - 
2. Pre-run Validation        - 
3. Run Management            -  
4. Reporting                 -  
5. Role Management           -  
6. Audit Trail               -  
"""
# ==============================================================================
# 1. PARAMETER
def copy_interim_to_approved(source_folder_path):
    """
    Copy a folder from interim to approved directory
    """
    try:
        if not os.path.exists(source_folder_path):
            logger.error(f"Source folder does not exist: {source_folder_path}")
            return {'status': 'Failed', 'error': 'Source folder does not exist'}
        
        # Create approved folder if it doesn't exist
        os.makedirs(BASE_APPROVED_FOLDER, exist_ok=True)
        
        # Get the folder name from the source path
        folder_name = os.path.basename(source_folder_path)
        destination_path = os.path.join(BASE_APPROVED_FOLDER, folder_name)
        
        # Check if destination already exists
        if os.path.exists(destination_path):
            logger.warning(f"Destination folder already exists: {destination_path}")
            return {'status': 'Failed', 'error': 'Destination folder already exists'}
        
        # Copy the entire folder
        shutil.copytree(source_folder_path, destination_path)
        logger.info(f"Successfully copied folder from {source_folder_path} to {destination_path}")
        return {'status': 'success', 'destination': destination_path}
    
    except Exception as e:
        logger.error(f"Error copying folder to approved: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}
 
def copy_approved_to_param_path(source_folder_path):
    """
    Copy files from approved folder to PARAM_PATH
    """
    try:
        if not os.path.exists(source_folder_path):
            logger.error(f"Source folder does not exist: {source_folder_path}")
            return {'status': 'Failed', 'error': 'Source folder does not exist'}

        # Read the config file to get PARAM_PATH
        import json
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
        param_path = config['RUN_SETTING']['PARAM_PATH']

        # Create PARAM_PATH if it doesn't exist
        os.makedirs(param_path, exist_ok=True)

        copied_files = []
        # Copy all files from the source folder to PARAM_PATH
        for file_name in os.listdir(source_folder_path):
            file_path = os.path.join(source_folder_path, file_name)
            if os.path.isfile(file_path):
                dest_path = os.path.join(param_path, file_name)
                shutil.copy2(file_path, dest_path)
                copied_files.append(file_name)
                logger.info(f"Copied {file_name} to PARAM_PATH")

        logger.info(f"Successfully copied {len(copied_files)} files from {source_folder_path} to {param_path}")
        return {'status': 'success', 'copied_files': copied_files, 'param_path': param_path}

    except Exception as e:
        logger.error(f"Error copying folder to PARAM_PATH: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}

def copy_interim_to_param_path(selected_parameters: str, selected_corrections: str):
    """
    Copy all files from selected parameter and adjustment folders to PARAM_PATH
    """
    try:
        # Read the config file to get PARAM_PATH
        import json
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
        param_path = config['RUN_SETTING']['PARAM_PATH']
        copied_files = []
        # Copy files from selected parameters folder
        if selected_parameters:
            param_folder = os.path.join(BASE_UPLOAD_FOLDER, selected_parameters)
            if os.path.exists(param_folder):
                for file_name in os.listdir(param_folder):
                    file_path = os.path.join(param_folder, file_name)
                    if os.path.isfile(file_path):
                        dest_path = os.path.join(param_path, file_name)
                        shutil.copy2(file_path, dest_path)
                        copied_files.append(f"Parameter: {file_name}")
        # Copy files from selected corrections folder
        if selected_corrections:
            adj_folder = os.path.join(BASE_UPLOAD_FOLDER, selected_corrections)
            if os.path.exists(adj_folder):
                for file_name in os.listdir(adj_folder):
                    file_path = os.path.join(adj_folder, file_name)
                    if os.path.isfile(file_path):
                        dest_path = os.path.join(param_path, file_name)
                        shutil.copy2(file_path, dest_path)
                        copied_files.append(f"Adjustment: {file_name}")
        logger.info(f"Copied files to PARAM_PATH: {copied_files}")
        return {'status': 'success', 'copied_files': copied_files}
    except Exception as e:
        logger.error(f"Error copying files to PARAM_PATH: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}

# Parameter: Upload File
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    file = request.files['file']
    file_type = request.form.get('fileType', 'unknown')  # Get file type from form data
    user_suffix = request.form.get('suffix', '')  # Get user input suffix
    maker = request.form.get('maker', '')
    category = request.form.get('category', '')
    checker = request.form.get('checker', '')
    auto_filename = request.form.get('auto_filename', '')  # Get auto-generated filename
 
    logger.info(f"Upload request - file_type: '{file_type}', user_suffix: '{user_suffix}', maker: '{maker}', category: '{category}', auto_filename: '{auto_filename}'")
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if file:
        try:
            # Get current timestamp in format yyyymmddHHMMSS
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            now_dt = datetime.now()
            # Get original file extension
            original_filename = file.filename
            file_extension = os.path.splitext(original_filename)[1] if '.' in original_filename else ''
            # Generate folder name based on file type and suffix
            if file_type == 'parameter':
                folder_name = f"par_{timestamp}_{user_suffix}" if user_suffix else f"par_{timestamp}"
                # Use auto-generated filename if provided and not a zip file
                if auto_filename and file_extension.lower() != '.zip':
                    new_filename = auto_filename
                else:
                    new_filename = original_filename
            elif file_type == 'adjustment':
                folder_name = f"adj_{timestamp}_{user_suffix}" if user_suffix else f"adj_{timestamp}"
                # Use auto-generated filename if provided and not a zip file
                if auto_filename and file_extension.lower() != '.zip':
                    new_filename = auto_filename
                else:
                    new_filename = original_filename
            else:
                # Fallback to original filename if file type is unknown
                folder_name = timestamp
                new_filename = original_filename
            
            logger.info(f"Generated folder_name: '{folder_name}' for file_type: '{file_type}'")
            # Create new folder path using the generated folder name
            new_upload_folder = os.path.join(BASE_UPLOAD_FOLDER, folder_name)
            # Create folder if it doesn't exist
            os.makedirs(new_upload_folder, exist_ok=True)
            # If the uploaded file is a zip, extract .xlsx/.csv files
            if file_extension.lower() == '.zip':
                file_bytes = BytesIO(file.read())
                with zipfile.ZipFile(file_bytes) as zf:
                    extracted_files = []
                    for member in zf.namelist():
                        if member.endswith('.xlsx') or member.endswith('.csv'):
                            # Flatten: ignore subfolders
                            base_name = os.path.basename(member)
                            if not base_name:
                                continue
                            out_path = os.path.join(new_upload_folder, base_name)
                            with zf.open(member) as source, open(out_path, 'wb') as target:
                                target.write(source.read())
                            extracted_files.append(base_name)
                # Write into DB
                save_parameter_record(
                    maker=maker,
                    time=now_dt,
                    type_=file_type,
                    category=category,
                    action=f'upload: {folder_name}',
                    status='Pending',
                    checker=checker or 'Waiting',
                    timestamp=timestamp,
                    suffix=user_suffix,
                    file_path=new_upload_folder
                )
                
                # Log parameter update
                log_parameter_update(maker, "Upload", file_type, new_upload_folder)
                
                return jsonify({
                    'message': f'Zip file extracted. Files: {extracted_files}',
                    'path': new_upload_folder,
                    'original_name': original_filename,
                    'extracted_files': extracted_files
                }), 200
            else:
                # Create full file path with new filename
                file_path = os.path.join(new_upload_folder, new_filename)
                # Save the file
                file.save(file_path)
                # Write into DB
                save_parameter_record(
                    maker=maker,
                    time=now_dt,
                    type_=file_type,
                    category=category,
                    action=f'upload: {folder_name}',
                    status='Pending',
                    checker=checker or 'Waiting',
                    timestamp=timestamp,
                    suffix=user_suffix,
                    file_path=new_upload_folder
                )
                
                # Log parameter update
                log_parameter_update(maker, "Upload", file_type, new_upload_folder)
                
                return jsonify({
                    'message': f'File "{original_filename}" uploaded successfully as "{new_filename}" to folder "{folder_name}"',
                    'path': file_path,
                    'original_name': original_filename,
                    'new_name': new_filename,
                    'folder_name': folder_name
                }), 200
        except Exception as e:
            return jsonify({'error': f'Error saving file: {str(e)}'}), 500

# Parameter: Get review records from DB
@app.route('/get_review_records', methods=['GET'])
def api_get_review_records():
    try:
        records = get_review_records()
        return jsonify({
            'records': records,
            'count': len(records)
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error getting review records: {str(e)}'}), 500

# Parameter: Update approval status when click "Approve" button
@app.route('/update_approval_status', methods=['POST'])
def update_approval_status():
    try:
        data = request.get_json()
        record_id = data.get('id')
        new_status = data.get('status', 'Approved')
        checker = data.get('checker', '')
        
        # Get the file_path from the database before updating
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        # First, get the file_path and type for this record
        cursor.execute(f"""
            SELECT file_path, type FROM [{DB_NAME}].[dbo].[UI_Parameter_records] WHERE id = ?
        """, (record_id,))
        result = cursor.fetchone()
        
        if not result or not result[0]:
            conn.close()
            return jsonify({'error': 'File path not found for this record'}), 404
        
        file_path = result[0]
        file_type = result[1] if result[1] else 'unknown'
        
        # Update the status in database
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[UI_Parameter_records]
            SET status = ?, checker = ?
            WHERE id = ?
        """, (new_status, checker, record_id))
        conn.close()
       
        # If the status is being changed to 'Approved', copy the folder to approved directory and then to PARAM_PATH
        if new_status == 'Approved':
            # Log parameter approval
            log_parameter_update(checker, "Approve", file_type, file_path)
        
            # Step 1: Copy to approved directory
            copy_result = copy_interim_to_approved(file_path)
            if copy_result['status'] != 'success':
                logger.error(f"Failed to copy folder to approved directory for record {record_id}: {copy_result['error']}")
                return jsonify({
                    'message': 'Status updated successfully but Failed to copy folder to approved directory',
                    'copy_error': copy_result['error']
                }), 500
        
            # Step 2: Copy from approved directory to PARAM_PATH
            approved_folder_path = copy_result['destination']
            copy_to_param_result = copy_approved_to_param_path(approved_folder_path)
            if copy_to_param_result['status'] == 'success':
                logger.info(f"Record {record_id} approved, folder copied to approved directory and files copied to PARAM_PATH")
                return jsonify({
                    'message': 'Status updated successfully, folder copied to approved directory and files copied to PARAM_PATH',
                    'copy_result': copy_result,
                    'param_copy_result': copy_to_param_result
                }), 200
            else:
                logger.error(f"Failed to copy files to PARAM_PATH for approved record {record_id}: {copy_to_param_result['error']}")
                return jsonify({
                    'message': 'Status updated successfully, folder copied to approved directory but Failed to copy files to PARAM_PATH',
                    'copy_result': copy_result,
                    'param_copy_error': copy_to_param_result['error']
                }), 500
        else:
            return jsonify({'message': 'Status updated successfully'}), 200
    
    except Exception as e:
        logger.error(f"Error updating approval status: {str(e)}")
        return jsonify({'error': f'Error updating approval status: {str(e)}'}), 500

# Parameter: Download files when click "Download" button
@app.route('/download_files/<record_id>', methods=['GET'])
def download_files(record_id):
    try:
        # Get the file path from database
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT file_path, maker FROM [{DB_NAME}].[dbo].[UI_Parameter_records] WHERE id = ?
        """, (record_id,))
        result = cursor.fetchone()
        conn.close()
        if not result or not result[0]:
            return jsonify({'error': 'File path not found'}), 404
        file_path = result[0]
        maker = result[1] if result[1] else 'Unknown User'
        # Check if directory exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'File directory not found'}), 404
        
        # Log download activity
        folder_name = os.path.basename(file_path)
        log_download_activity(maker, "Parameter", f"Parameter files from {folder_name}")
        
        # Create zip file with all files in the directory
        import zipfile
        from io import BytesIO
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename in os.listdir(file_path):
                file_full_path = os.path.join(file_path, filename)
                if os.path.isfile(file_full_path):
                    zip_file.write(file_full_path, filename)
        zip_buffer.seek(0)
        # Get the folder name for the zip file name
        folder_name = os.path.basename(file_path)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{folder_name}.zip'
        )
    except Exception as e:
        return jsonify({'error': f'Error downloading files: {str(e)}'}), 500
 
# ==============================================================================
# 2. PRE-RUN VALIDATION
def save_prerun_validation_record(task_id: str, maker: str, time: datetime, type_: str, category: str, timestamp: str, upload_timestamp: str = '', upload_type: str = ''):
    """Save pre-run validation record to database"""
    try:
        create_prerun_validation_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO [{DB_NAME}].[dbo].[UI_prerun_validation_records]
            (task_id, maker, time, type, category, action, status, timestamp, upload_timestamp, upload_type)
            VALUES (?, ?, ?, ?, ?, 'Pre-run Validation', 'Running', ?, ?, ?)
        """, (task_id, maker, time, type_, category, timestamp, upload_timestamp, upload_type))
        conn.close()
        logger.info(f"Successfully saved pre-run validation record: {task_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving pre-run validation record: {str(e)}")
        return False

def update_prerun_validation_status(task_id: str, status: str):
    """Update pre-run validation status in database"""
    try:
        create_prerun_validation_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        if status == 'Completed':
            cursor.execute(f"""
                UPDATE [{DB_NAME}].[dbo].[UI_prerun_validation_records]
                SET status = ?, completed_at = GETDATE()
                WHERE task_id = ?
            """, (status, task_id))
        else:
            cursor.execute(f"""
                UPDATE [{DB_NAME}].[dbo].[UI_prerun_validation_records]
                SET status = ?
                WHERE task_id = ?
            """, (status, task_id))
        conn.close()
        logger.info(f"Updated pre-run validation status for {task_id} to {status}")
        return True
    except Exception as e:
        logger.error(f"Error updating pre-run validation status: {str(e)}")
        return False

def get_prerun_validation_record(task_id: str):
    """Get pre-run validation record by task_id"""
    try:
        create_prerun_validation_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, task_id, maker, time, type, category, action, status, timestamp, upload_timestamp, upload_type, created_at, completed_at
            FROM [{DB_NAME}].[dbo].[UI_prerun_validation_records]
            WHERE task_id = ?
        """, (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'task_id': row[1],
                'maker': row[2],
                'time': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else '',
                'type': row[4],
                'category': row[5] or '',
                'action': row[6],
                'status': row[7],
                'timestamp': row[8],
                'upload_timestamp': row[9] or '',
                'upload_type': row[10] or '',
                'created_at': row[11].strftime('%Y-%m-%d %H:%M:%S') if row[11] else '',
                'completed_at': row[12].strftime('%Y-%m-%d %H:%M:%S') if row[12] else ''
            }
        return None
    except Exception as e:
        logger.error(f"Error getting pre-run validation record: {str(e)}")
        return None

@app.route('/start_prerun_validation', methods=['POST'])
def start_prerun_validation():
    """Start pre-run validation for a parameter or adjustment file"""
    try:
        data = request.get_json()
        parameter_folder = data.get('parameterFolder', '')
        adjustment_folder = data.get('adjustmentFolder', '')
        maker = data.get('maker', 'Unknown User')
        ui_timestamp = data.get('ui_timestamp', '')
        upload_timestamp = data.get('upload_timestamp', '')  # Original upload timestamp
        upload_type = data.get('upload_type', '')  # Original upload type
        
        # Validate input - must have either parameter or adjustment, not both
        if not parameter_folder and not adjustment_folder:
            return jsonify({'error': 'Must specify either parameter folder or adjustment folder'}), 400
        if parameter_folder and adjustment_folder:
            return jsonify({'error': 'Cannot specify both parameter and adjustment folders'}), 400
        
        # Log the validation request
        logger.info(f"Starting pre-run validation for parameter: {parameter_folder}, adjustment: {adjustment_folder}")
        logger.info(f"Maker: {maker}, UI timestamp: {ui_timestamp}")
        
        # Generate validation config file
        config_result = generate_prerun_validation_config_file(
            parameter_folder=parameter_folder,
            adjustment_folder=adjustment_folder,
            ui_timestamp=ui_timestamp
        )
        
        if config_result['status'] == 'Failed':
            return jsonify({'error': f'Failed to generate validation config: {config_result["error"]}'}), 500
        
        # Use the new config file path and timestamp
        new_config_path = config_result['config_path']
        timestamp = config_result.get('timestamp', '')
        
        # Copy selected files to PARAM_PATH for validation
        copy_result = copy_interim_to_param_path(parameter_folder, adjustment_folder)
        if copy_result['status'] == 'Failed':
            return jsonify({
                'error': f'Failed to copy files to PARAM_PATH: {copy_result["error"]}'
            }), 500
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Get current time for the record
        now_dt = datetime.now()
        
        # Get category from the upload record
        category = ''
        try:
            conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
            cursor = conn.cursor()
            # Find the upload record by folder name
            folder_name = parameter_folder if parameter_folder else adjustment_folder
            cursor.execute(f"""
                SELECT category FROM [{DB_NAME}].[dbo].[UI_Parameter_records]
                WHERE action LIKE ?
                ORDER BY time DESC
            """, (f'%{folder_name}%',))
            row = cursor.fetchone()
            if row:
                category = row[0] or ''
            conn.close()
        except Exception as e:
            logger.warning(f"Could not get category from upload record: {str(e)}")
            category = ''
        
        # Save validation record to database
        save_result = save_prerun_validation_record(
            task_id=task_id,
            maker=maker,  # Use current logged-in user as maker
            time=now_dt,
            type_=upload_type,  # Use original upload type
            category=category,  # Use category from upload record
            timestamp=timestamp,
            upload_timestamp=upload_timestamp,  # Store original upload timestamp
            upload_type=upload_type  # Store original upload type
        )
        
        if not save_result:
            return jsonify({'error': 'Failed to save validation record to database'}), 500
        
        # Prepare command with new validation config file
        command = f'{ECL_ENGINE_CONFIG["python_executable"]} {os.path.join(BASE_ECL_ENGINE, ECL_ENGINE_CONFIG["main_script"])} --configPath {new_config_path}'
        logger.info(f"Executing pre-run validation command: {command}")
        logger.info(f"Working directory: {BASE_ECL_ENGINE}")
        logger.info(f"Using new validation config file: {new_config_path}")
        logger.info(f"Output will be saved to new folder: {timestamp}")
        
        # Initialize task status
        task_status[task_id] = {
            'status': 'Running',
            'data': data,
            'copied_files': copy_result.get('copied_files', []),
            'config_file': new_config_path,
            'timestamp': timestamp,
            'created_at': datetime.now().isoformat(),
            'command': command,
            'is_prerun_validation': True
        }
        
        with future_lock:
            future = executor.submit(process_ecl_task, command, data)
            future_to_task_id[future] = task_id
        
        return jsonify({
            'task_id': task_id,
            'status': 'pending',
            'timestamp': timestamp,
            'config_file': new_config_path,
            'copied_files': copy_result.get('copied_files', [])
        }), 202
    
    except Exception as e:
        logger.error(f"Error starting pre-run validation: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Full error traceback: {error_details}")
        return jsonify({
            'error': str(e),
            'traceback': error_details
        }), 500

@app.route('/prerun_validation_status/<task_id>', methods=['GET'])
def get_prerun_validation_status(task_id):
    """Get pre-run validation status by task_id"""
    try:
        # First check task_status in memory
        if task_id in task_status:
            memory_status = task_status[task_id]
            return jsonify({
                'status': memory_status['status'],
                'timestamp': memory_status.get('timestamp', ''),
                'config_file': memory_status.get('config_file', '')
            })
        
        # If not in memory, check database
        record = get_prerun_validation_record(task_id)
        if record:
            return jsonify({
                'status': record['status'],
                'timestamp': record['timestamp'],
                'config_file': f"run_config_file_{record['timestamp']}.json"
            })
        
        return jsonify({'error': 'Task not found'}), 404
    
    except Exception as e:
        logger.error(f"Error getting pre-run validation status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_prerun_validation_records', methods=['GET'])
def get_prerun_validation_records():
    """Get all pre-run validation records"""
    try:
        create_prerun_validation_table()
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT id, task_id, maker, time, type, category, action, status, timestamp, upload_timestamp, upload_type, created_at, completed_at
            FROM [{DB_NAME}].[dbo].[UI_prerun_validation_records]
            ORDER BY created_at DESC
        """)
        
        records = []
        for row in cursor.fetchall():
            records.append({
                'id': row[0],
                'task_id': row[1],
                'maker': row[2],
                'time': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else '',
                'type': row[4],
                'category': row[5] or '',
                'action': row[6],
                'status': row[7],
                'timestamp': row[8],
                'upload_timestamp': row[9] or '',
                'upload_type': row[10] or '',
                'created_at': row[11].strftime('%Y-%m-%d %H:%M:%S') if row[11] else '',
                'completed_at': row[12].strftime('%Y-%m-%d %H:%M:%S') if row[12] else ''
            })
        
        conn.close()
        return jsonify({'records': records})
    
    except Exception as e:
        logger.error(f"Error getting pre-run validation records: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download_prerun_validation_logs/<task_id>', methods=['GET'])
def download_prerun_validation_logs(task_id):
    """Download pre-run validation logs (01_log folder)"""
    try:
        # Get validation record from database
        record = get_prerun_validation_record(task_id)
        if not record:
            return jsonify({'error': 'Validation record not found'}), 404
        
        # Construct path to 01_log folder
        timestamp = record['timestamp']
        timestamp_folder = os.path.join(BASE_OUTPUT_FOLDER, timestamp)
        
        # Look for the automatically created folder structure
        log_folder_path = None
        if os.path.exists(timestamp_folder):
            for item in os.listdir(timestamp_folder):
                item_path = os.path.join(timestamp_folder, item)
                if os.path.isdir(item_path) and '_' in item:
                    # Check if this directory contains 01_log
                    log_path = os.path.join(item_path, '01_log')
                    if os.path.exists(log_path):
                        log_folder_path = log_path
                        break
        
        if not log_folder_path:
            return jsonify({'error': f'Log folder not found for timestamp: {timestamp}'}), 404
        
        # Create zip file of logs
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(log_folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, log_folder_path)
                    zip_file.write(file_path, arc_name)
        
        zip_buffer.seek(0)
        
        # Log download activity
        log_download_activity(record['maker'], "Parameter", f"Pre-run validation logs for {timestamp}")
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'prerun_validation_logs_{timestamp}.zip'
        )
    
    except Exception as e:
        logger.error(f"Error downloading pre-run validation logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download_prerun_validation_report/<task_id>', methods=['GET'])
def download_prerun_validation_report(task_id):
    """Download pre-run validation report (04_report folder)"""
    try:
        # Get validation record from database
        record = get_prerun_validation_record(task_id)
        if not record:
            return jsonify({'error': 'Validation record not found'}), 404


        # Construct path to 04_report folder
        timestamp = record['timestamp']
        timestamp_folder = os.path.join(BASE_OUTPUT_FOLDER, timestamp)
        
        # Look for the automatically created folder structure
        report_folder_path = None
        if os.path.exists(timestamp_folder):
            for item in os.listdir(timestamp_folder):
                item_path = os.path.join(timestamp_folder, item)
                if os.path.isdir(item_path) and '_' in item:
                    # Check if this directory contains 04_report
                    report_path = os.path.join(item_path, '04_report')
                    if os.path.exists(report_path):
                        report_folder_path = report_path
                        break
        
        if not report_folder_path:
            return jsonify({'error': f'Report folder not found for timestamp: {timestamp}'}), 404
        
        # Create zip file of reports
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(report_folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, report_folder_path)
                    zip_file.write(file_path, arc_name)
        
        zip_buffer.seek(0)
        
        # Log download activity
        log_download_activity(record['maker'], "Parameter", f"Pre-run validation report for {timestamp}")
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'prerun_validation_report_{timestamp}.zip'
        )
    
    except Exception as e:
        logger.error(f"Error downloading pre-run validation report: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==============================================================================
# 3. RUN MANAGEMENT
def copy_original_data_only(original_timestamp: str, new_timestamp: str, base_output_path: str):
    """
    Copy only the original data (reportingdate_yymmdd folder) to new location
    This ensures data isolation by not copying any derived results (reports, resumes)
    """
    try:
        import shutil
        
        # Construct paths
        if '/03_output_folder' in base_output_path:
            base_path = base_output_path.split('/03_output_folder')[0]
            original_timestamp_path = f"{base_path}/03_output_folder/{original_timestamp}"
            new_timestamp_path = f"{base_path}/03_output_folder/{new_timestamp}"
        else:
            original_timestamp_path = f"{base_output_path}/{original_timestamp}"
            new_timestamp_path = f"{base_output_path}/{new_timestamp}"
        
        # Create new timestamp folder
        os.makedirs(new_timestamp_path, exist_ok=True)
        
        # Find the folder containing underscore (reportingdate_yymmdd format) in original timestamp folder
        if not os.path.exists(original_timestamp_path):
            return {'status': 'Failed', 'error': f'Original timestamp folder does not exist: {original_timestamp_path}'}
        
        # Look for folder containing underscore (reportingdate_yymmdd format)
        reporting_date_folder = None
        available_items = []
        for item in os.listdir(original_timestamp_path):
            item_path = os.path.join(original_timestamp_path, item)
            available_items.append(item)
            if os.path.isdir(item_path) and '_' in item:
                # This looks like a reportingdate_yymmdd folder (contains underscore)
                reporting_date_folder = item
                break
        
        if not reporting_date_folder:
            logger.error(f"No folder with underscore found in {original_timestamp_path}")
            logger.error(f"Available items in {original_timestamp_path}: {available_items}")
            return {'status': 'Failed', 'error': f'No folder with underscore found in {original_timestamp_path}. Available items: {available_items}'}
        
        # Copy only the folder containing underscore (reportingdate_yymmdd format)
        # Extract reporting_date part from original folder name (e.g., "20241231" from "20241231_20251016")
        reporting_date_part = reporting_date_folder.split('_')[0]
        
        # Extract date from new_timestamp (last 14 characters after last underscore, first 8 chars are date)
        if '_' in new_timestamp:
            parts = new_timestamp.split('_')
            if len(parts) >= 3:
                time_part = parts[-1]
                new_date = time_part[:8]
            else:
                new_date = new_timestamp[:8]
        else:
            new_date = new_timestamp[:8]
        
        # Build new folder name with current date (e.g., "20241231_20251017")
        new_folder_name = f"{reporting_date_part}_{new_date}"
        
        original_reporting_path = os.path.join(original_timestamp_path, reporting_date_folder)
        new_reporting_path = os.path.join(new_timestamp_path, new_folder_name)
        
        logger.info(f"Copying original data from {original_reporting_path} to {new_reporting_path}")
        logger.info(f"Renamed folder from {reporting_date_folder} to {new_folder_name}")
        shutil.copytree(original_reporting_path, new_reporting_path)
        
        logger.info(f"Successfully copied original data to: {new_reporting_path}")
        return {'status': 'success', 'copied_path': new_reporting_path}
    
    except Exception as e:
        logger.error(f"Failed to copy original data: {str(e)}")
        return {'status': 'Failed', 'error': f'Failed to copy original data: {str(e)}'}

def generate_new_config_file(reporting_date: str, run_mode: str, ui_timestamp: str = None):
    """
    Generate a new config file with user-selected parameters
    """
    try:
        # Read the original config file
        import json
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
        # Update the config with user selections
        # Convert reporting_date from YYYY-MM-DD to YYYYMMDD format
        if reporting_date:
            # Remove dashes and convert to YYYYMMDD format
            data_yymm = reporting_date.replace('-', '')
            config['RUN_SETTING']['DATA_YYMM'] = int(data_yymm)
        if run_mode:
            config['RUN_SETTING']['RUN_MODE'] = str(run_mode)
        
        # Use UI timestamp (must be provided for consistency)
        if not ui_timestamp:
            return {'status': 'Failed', 'error': 'UI timestamp is required for consistency'}
        
        # Get DATA_YYMM from config
        data_yymm_str = str(config['RUN_SETTING']['DATA_YYMM'])
        
        # Create new timestamp format: Adhoc_Run_{DATA_YYMM}_{ui_timestamp}
        timestamp = f"Adhoc_Run_{data_yymm_str}_{ui_timestamp}"
        
        # Modify OUTPUT_PATH to include timestamp subfolder
        base_output_path = config['RUN_SETTING']['OUTPUT_PATH']
        # Extract the base path without any existing timestamp folders
        if '/03_output_folder' in base_output_path:
            base_path = base_output_path.split('/03_output_folder')[0]
            new_output_path = f"{base_path}/03_output_folder/{timestamp}"
        else:
            # Fallback if path structure is different
            new_output_path = f"{base_output_path}/{timestamp}"
        
        config['RUN_SETTING']['OUTPUT_PATH'] = new_output_path
        logger.info(f"Modified OUTPUT_PATH to: {new_output_path}")
        
        # Create the timestamp folder if it doesn't exist
        try:
            os.makedirs(new_output_path, exist_ok=True)
            logger.info(f"Created/verified output folder: {new_output_path}")
        except Exception as e:
            logger.error(f"Failed to create output folder {new_output_path}: {str(e)}")
            return {'status': 'Failed', 'error': f'Failed to create output folder: {str(e)}'}
        
        new_config_filename = f'run_config_file_{timestamp}.json'
        new_config_path = os.path.join(BASE_ECL_ENGINE, new_config_filename)
        # Write the new config file
        with open(new_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Generated new config file: {new_config_path}")
        return {'status': 'success', 'config_path': new_config_path, 'timestamp': timestamp}
    except Exception as e:
        logger.error(f"Error generating new config file: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}

def generate_prerun_validation_config_file(parameter_folder: str = None, adjustment_folder: str = None, ui_timestamp: str = None):
    """
    Generate a new config file for pre-run validation with fixed settings
    """
    try:
        # Read the original config file
        import json
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
        
        # Fixed settings for pre-run validation
        config['RUN_SETTING']['RUN_MODE'] = '2'
        config['RUN_SETTING']['SANITY_CHECK_MODE'] = '2.1'
        
        # Generate new timestamp for validation run
        if ui_timestamp:
            ui_ts = ui_timestamp
        else:
            ui_ts = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Get DATA_YYMM from config
        data_yymm_str = str(config['RUN_SETTING']['DATA_YYMM'])
        
        # Create new timestamp format: Adhoc_Run_{DATA_YYMM}_{ui_timestamp}
        timestamp = f"Adhoc_Run_{data_yymm_str}_{ui_ts}"
        
        # Create new OUTPUT_PATH with validation timestamp
        base_output_path = config['RUN_SETTING']['OUTPUT_PATH']
        # Extract the base path without any existing timestamp folders
        if '/03_output_folder' in base_output_path:
            base_path = base_output_path.split('/03_output_folder')[0]
            new_output_path = f"{base_path}/03_output_folder/{timestamp}"
        else:
            # Fallback if path structure is different
            new_output_path = f"{base_path}/{timestamp}"
        
        config['RUN_SETTING']['OUTPUT_PATH'] = new_output_path
        logger.info(f"Modified OUTPUT_PATH for pre-run validation to: {new_output_path}")
        
        # Create the new timestamp folder for validation run
        try:
            os.makedirs(new_output_path, exist_ok=True)
            logger.info(f"Created/verified pre-run validation output folder: {new_output_path}")
        except Exception as e:
            logger.error(f"Failed to create pre-run validation output folder {new_output_path}: {str(e)}")
            return {'status': 'Failed', 'error': f'Failed to create pre-run validation output folder: {str(e)}'}
        
        # Create new config file with validation timestamp
        new_config_filename = f'run_config_file_{timestamp}.json'
        new_config_path = os.path.join(BASE_ECL_ENGINE, new_config_filename)
        
        # Write the new validation config file
        with open(new_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Generated new pre-run validation config file: {new_config_path}")
        return {'status': 'success', 'config_path': new_config_path, 'timestamp': timestamp}
    except Exception as e:
        logger.error(f"Error generating pre-run validation config file: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}

def generate_resume_config_file(config_filename: str, resume_run_mode: str, ui_timestamp: str = None):
    """
    Generate a new config file for resume run with independent output path
    """
    try:
        # Construct the full path to the existing config file
        existing_config_path = os.path.join(BASE_ECL_ENGINE, config_filename)
        
        # Check if the config file exists
        if not os.path.exists(existing_config_path):
            return {'status': 'Failed', 'error': f'Config file not found: {config_filename}'}
        
        # Read the existing config file
        import json
        with open(existing_config_path, 'r') as f:
            config = json.load(f)
        
        # Update RUN_MODE for resume run
        if resume_run_mode:
            config['RUN_SETTING']['RUN_MODE'] = str(resume_run_mode)
        
        # Use UI timestamp (must be provided for consistency)
        if not ui_timestamp:
            return {'status': 'Failed', 'error': 'UI timestamp is required for consistency'}
        
        # Get DATA_YYMM from config
        data_yymm_str = str(config['RUN_SETTING']['DATA_YYMM'])
        
        # Create new timestamp format: Adhoc_Run_{DATA_YYMM}_{ui_timestamp}
        timestamp = f"Adhoc_Run_{data_yymm_str}_{ui_timestamp}"
        
        # Extract the timestamp from the original config filename
        original_timestamp = config_filename.replace('run_config_file_', '').replace('.json', '')
        
        # Get the original output path
        original_output_path = config['RUN_SETTING']['OUTPUT_PATH']
        logger.info(f"Original output path for resume: {original_output_path}")
        
        # Verify the original output folder exists
        if not os.path.exists(original_output_path):
            return {'status': 'Failed', 'error': f'Original output folder does not exist: {original_output_path}'}
        
        # Create new OUTPUT_PATH with resume timestamp
        base_output_path = config['RUN_SETTING']['OUTPUT_PATH']
        # Extract the base path without any existing timestamp folders
        if '/03_output_folder' in base_output_path:
            base_path = base_output_path.split('/03_output_folder')[0]
            new_output_path = f"{base_path}/03_output_folder/{timestamp}"
        else:
            # Fallback if path structure is different
            new_output_path = f"{base_path}/{timestamp}"
        
        # Copy only the original data (reportingdate_yymmdd folder) to ensure data isolation
        copy_result = copy_original_data_only(original_timestamp, timestamp, base_output_path)
        if copy_result['status'] == 'Failed':
            return {'status': 'Failed', 'error': f'Failed to copy original data for resume: {copy_result["error"]}'}
        
        config['RUN_SETTING']['OUTPUT_PATH'] = new_output_path
        logger.info(f"Modified OUTPUT_PATH for resume run to: {new_output_path}")
        
        # Create new config file with resume timestamp
        new_config_filename = f'run_config_file_{timestamp}.json'
        new_config_path = os.path.join(BASE_ECL_ENGINE, new_config_filename)
        
        # Write the new resume config file
        with open(new_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Generated new resume config file: {new_config_path}")
        return {'status': 'success', 'config_path': new_config_path, 'timestamp': timestamp}
    except Exception as e:
        logger.error(f"Error generating resume config file: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}

def generate_report_config_file_from_record(record_id, ui_timestamp):
    """
    Automatically generate report config file from review record
    Inherits all previously modified functions: timestamp consistency and data isolation
    """
    try:
        # 1. Get original record information
        original_record = get_eclengine_record_by_id(record_id)
        if not original_record:
            return {'status': 'Failed', 'error': 'Original record not found'}
        
        # Ensure settings is a dict
        settings = original_record.get('settings', {}) or {}
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except Exception:
                logger.error(f"Failed to parse settings JSON for record {record_id}")
                settings = {}
        
        # 2. Get original timestamp from settings
        original_timestamp = settings.get('timestamp', '')
        if not original_timestamp:
            return {'status': 'Failed', 'error': 'Original timestamp not found in record settings'}
        
        original_config_filename = f"run_config_file_{original_timestamp}.json"
        
        # Get the base output path from config BEFORE generating new config
        base_output_path = None
        try:
            import json
            with open(CONFIG_FILE_PATH, 'r') as f:
                config = json.load(f)
            base_output_path = config['RUN_SETTING']['OUTPUT_PATH']
        except Exception as e:
            logger.error(f"Failed to read config file for base output path: {str(e)}")
            return {'status': 'Failed', 'error': f'Failed to read config file: {str(e)}'}
        
        # 3. Determine reporting date for this record
        # Always derive reporting date from the record itself, not from the template
        reporting_date = settings.get('reportingDate') or settings.get('reporting_date')
        
        # Fallback: try to derive reporting date from original_timestamp
        # original_timestamp format: Adhoc_Run_YYYYMMDD_YYYYMMDDHHMMSS
        if not reporting_date and original_timestamp:
            parts = original_timestamp.split('_')
            # Expect at least: ['Adhoc', 'Run', 'YYYYMMDD', 'YYYYMMDDHHMMSS']
            if len(parts) >= 3 and len(parts[2]) == 8 and parts[2].isdigit():
                date_str = parts[2]  # YYYYMMDD
                reporting_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        if not reporting_date:
            logger.error(f"Reporting date not found for record {record_id}. Settings: {settings}")
            return {'status': 'Failed', 'error': 'Reporting date not found in original record settings'}
        
        # 4. Use our modified function to ensure all functionality is preserved
        #    Here reporting_date is guaranteed to come from the record/its timestamp,
        #    so DATA_YYMM will not be affected by manual edits to the template config.
        config_result = generate_new_config_file(
            reporting_date=reporting_date,
            run_mode='6',  # Fixed to 6
            ui_timestamp=ui_timestamp  # Use UI timestamp to ensure consistency
        )
        
        if config_result['status'] == 'Failed':
            return config_result
        
        # 5. Copy original ECL run data to new report folder
        new_timestamp = config_result.get('timestamp', ui_timestamp)
        copy_result = copy_original_data_only(original_timestamp, new_timestamp, base_output_path)
        if copy_result['status'] == 'Failed':
            logger.error(f"Failed to copy original data for report generation: {copy_result['error']}")
            return {'status': 'Failed', 'error': f'Failed to copy original data: {copy_result["error"]}'}
        
        logger.info(f"Successfully copied original ECL run data to new report folder")
        return config_result
    
    except Exception as e:
        logger.error(f"Error generating report config from record: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}

# Run Management: Select Parameters and Data Correction
@app.route('/get_uploaded_files', methods=['GET'])
def get_uploaded_files():
    try:
        file_type = request.args.get('type', 'all')  # 'parameter', 'adjustment', 'resume_config', or 'all'
        # List all directories in the upload folder
        all_dirs = [d for d in os.listdir(BASE_UPLOAD_FOLDER)
                   if os.path.isdir(os.path.join(BASE_UPLOAD_FOLDER, d))]
        # Filter based on file type
        if file_type == 'parameter':
            files = [d for d in all_dirs if d.startswith('par_')]
        elif file_type == 'adjustment':
            files = [d for d in all_dirs if d.startswith('adj_')]
        elif file_type == 'resume_config':
            # Get all config files from ECL_Engine directory
            config_files = []
            if os.path.exists(BASE_ECL_ENGINE):
                for file_name in os.listdir(BASE_ECL_ENGINE):
                    if file_name.startswith('run_config_file_') and file_name.endswith('.json'):
                        config_files.append(file_name)
            # Sort files by timestamp (newest first)
            config_files.sort(reverse=True)
            return jsonify({
                'files': config_files,
                'base_path': BASE_ECL_ENGINE
            }), 200
        elif file_type == 'report_config':
            # Get all config files from ECL_Engine directory (same as resume_config)
            config_files = []
            if os.path.exists(BASE_ECL_ENGINE):
                for file_name in os.listdir(BASE_ECL_ENGINE):
                    if file_name.startswith('run_config_file_') and file_name.endswith('.json'):
                        config_files.append(file_name)
            # Sort files by timestamp (newest first)
            config_files.sort(reverse=True)
            return jsonify({
                'files': config_files,
                'base_path': BASE_ECL_ENGINE
            }), 200
        else:
            files = all_dirs
        # Sort files by timestamp (newest first)
        files.sort(reverse=True)
        return jsonify({
            'files': files,
            'base_path': BASE_UPLOAD_FOLDER
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error getting file list: {str(e)}'}), 500

# Run Management: Run ECL Engine
@app.route('/run_ecl_engine', methods=['POST'])
def run_ecl_engine():
    try:
        data = request.get_json()
        reporting_date = data.get('reportingDate', '')
        run_mode = data.get('runMode', '')
        ui_timestamp = data.get('ui_timestamp', '')  # Get UI timestamp from request
        
        # Log the selections
        logger.info(f"Starting ECL engine with existing config file: {CONFIG_FILE_PATH}")
        logger.info(f"Reporting date: {reporting_date}")
        logger.info(f"Run mode: {run_mode}")
        logger.info(f"UI timestamp: {ui_timestamp}")
        logger.info("Using files already in PARAM_PATH")
        
        # Generate new config file with user selections and UI timestamp
        config_result = generate_new_config_file(reporting_date, run_mode, ui_timestamp)
        if config_result['status'] == 'Failed':
            return jsonify({
                'error': f'Failed to generate config file: {config_result["error"]}'
            }), 500
        
        # Use the new config file path and timestamp
        new_config_path = config_result['config_path']
        timestamp = config_result.get('timestamp', '')
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Assemble settings field, including task_id, timestamp and all parameters
        settings = json.dumps({
            "task_id": task_id,
            "timestamp": timestamp,
            "reportingDate": reporting_date,
            "runMode": run_mode
        })
        
        now_dt = datetime.now()
        # Save to DB
        save_eclengine_record(
            maker=data.get('maker','Unknown User'),
            time=now_dt,
            settings=settings,
            action=data.get('action', ''),
            status='Running',
            checker='Waiting'
        )
        update_eclengine_status_in_db(task_id, 'Running')
        
        # Prepare command with new config file
        command = f'{ECL_ENGINE_CONFIG["python_executable"]} {os.path.join(BASE_ECL_ENGINE, ECL_ENGINE_CONFIG["main_script"])} --configPath {new_config_path}'
        logger.info(f"Executing command: {command}")
        logger.info(f"Working directory: {BASE_ECL_ENGINE}")
        logger.info(f"Using config file: {new_config_path}")
        logger.info(f"Output will be saved to timestamp folder: {timestamp}")
        
        # Initialize task status with creation timestamp
        task_status[task_id] = {
            'status': 'Running',
            'data': data,
            'copied_files': [],
            'config_file': new_config_path,
            'timestamp': timestamp,
            'created_at': datetime.now().isoformat(),
            'command': command
        }
        
        with future_lock:
            future = executor.submit(process_ecl_task, command, data)
            future_to_task_id[future] = task_id
        
        return jsonify({
            'task_id': task_id,
            'status': 'pending',
            'timestamp': timestamp,
            'copied_files': [],
            'config_file': new_config_path
        }), 202
    except Exception as e:
        logger.error(f"Error initiating ECL engine run: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Full error traceback: {error_details}")
        return jsonify({
            'error': str(e),
            'traceback': error_details
        }), 500
 
# Resume ECL Engine Run
@app.route('/resume_ecl_engine', methods=['POST'])
def resume_ecl_engine():
    try:
        data = request.get_json()
        selected_resume_config = data.get('selectedResumeConfig', '')
        selected_resume_run_mode = data.get('selectedResumeRunMode', '')
        resume_action_comment = data.get('resumeActionComment', '')
        ui_timestamp = data.get('ui_timestamp', '')
        
        # Log the resume selections
        logger.info(f"Resuming ECL engine with config file: {selected_resume_config}")
        logger.info(f"Resume run mode: {selected_resume_run_mode}")
        logger.info(f"Resume action comment: {resume_action_comment}")
        logger.info(f"UI timestamp: {ui_timestamp}")
        
        # Modify the existing config file with new run mode
        config_result = generate_resume_config_file(selected_resume_config, selected_resume_run_mode, ui_timestamp)
        if config_result['status'] == 'Failed':
            return jsonify({
                'error': f'Failed to generate resume config file: {config_result["error"]}'
            }), 500
        
        # Use the new resume config file path and timestamp
        new_config_path = config_result['config_path']
        timestamp = config_result.get('timestamp', '')
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Assemble settings field for resume run
        settings = json.dumps({
            "task_id": task_id,
            "timestamp": timestamp,
            "isResume": True,
            "resumedVersion": selected_resume_config,
            "runMode": selected_resume_run_mode,
            "selectedParameters": "",  # Resume run doesn't have parameters
            "selectedCorrections": "",  # Resume run doesn't have adjustments
            "reportingDate": "",  # Resume run doesn't have reporting date
            "country": ""  # Resume run doesn't have country
        })
        
        now_dt = datetime.now()
        # Save to DB
        save_eclengine_record(
            maker=data.get('maker', 'Unknown User'),
            time=now_dt,
            settings=settings,
            action=resume_action_comment,
            status='Running',
            checker='Waiting'
        )
        update_eclengine_status_in_db(task_id, 'Running')
        
        # Prepare command with new resume config file
        command = f'{ECL_ENGINE_CONFIG["python_executable"]} {os.path.join(BASE_ECL_ENGINE, ECL_ENGINE_CONFIG["main_script"])} --configPath {new_config_path}'
        logger.info(f"Executing resume command: {command}")
        logger.info(f"Working directory: {BASE_ECL_ENGINE}")
        logger.info(f"Using new resume config file: {new_config_path}")
        logger.info(f"Resume will use copied output folder: {timestamp}")
        
        # Initialize task status
        task_status[task_id] = {
            'status': 'Running',
            'data': data,
            'config_file': new_config_path,
            'timestamp': timestamp,
            'created_at': datetime.now().isoformat(),
            'command': command,
            'is_resume': True
        }
        
        with future_lock:
            future = executor.submit(process_ecl_task, command, data)
            future_to_task_id[future] = task_id
        
        return jsonify({
            'task_id': task_id,
            'status': 'pending',
            'timestamp': timestamp,
            'config_file': new_config_path
        }), 202
    except Exception as e:
        logger.error(f"Error initiating ECL engine resume: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Full error traceback: {error_details}")
        return jsonify({
            'error': str(e),
            'traceback': error_details
        }), 500

# Generate Report from Record
@app.route('/generate_report_from_record', methods=['POST'])
def generate_report_from_record():
    """New API to generate report from review record"""
    try:
        data = request.get_json()
        record_id = data.get('record_id')
        ui_timestamp = data.get('ui_timestamp', '')
        maker = data.get('maker', 'Unknown User')
        
        if not record_id:
            return jsonify({'error': 'Record ID is required'}), 400
        
        # Use frontend timestamp if provided, otherwise generate one (consistent with Parameter page)
        if ui_timestamp:
            timestamp = ui_timestamp
        else:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Get original record information
        original_record = get_eclengine_record_by_id(record_id)
        if not original_record:
            return jsonify({'error': 'Original record not found'}), 404
        
        if original_record['status'] != 'Completed':
            return jsonify({'error': 'Only completed records can generate reports'}), 400
        
        # Check if run mode ends with '5'
        run_mode = original_record['settings'].get('runMode', '')
        if not run_mode.endswith('5'):
            return jsonify({'error': 'Only records with run mode ending in 5 can generate reports'}), 400
        
        # Generate report config file
        # IMPORTANT:
        # - The report run's DATA_YYMM / run_yymm must be derived from the
        #   original record itself (DB settings / original timestamp),
        #   NOT from the mutable template run_config_file.json.
        # - This avoids issues where someone manually edits the template's
        #   RUN_YYMM and causes Generate Report to pick up the wrong date.
        config_result = generate_report_config_file_from_record(record_id, timestamp)
        if config_result['status'] == 'Failed':
            return jsonify({'error': f'Failed to generate report config: {config_result["error"]}'}), 500
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        new_timestamp = config_result.get('timestamp', '')
        new_config_path = config_result.get('config_path', '')
        
        # Build settings
        original_timestamp = original_record['settings'].get('timestamp', '')
        reporting_date = original_record['settings'].get('reportingDate', '')
        settings = json.dumps({
            "task_id": task_id,
            "timestamp": new_timestamp,
            "reportingDate": reporting_date,
            "runMode": "6",
            "original_timestamp": original_timestamp
        })
        
        # Build action with formatted timestamp
        formatted_timestamp = format_timestamp_for_display(original_timestamp)
        action = f"Generate report for ECL Run at {formatted_timestamp}"
        
        # Save to reporting records table
        now_dt = datetime.now()
        save_reporting_record(
            task_id=task_id,
            maker=maker,
            time=now_dt,
            settings=settings,
            action=action,
            status='Running',
            checker=maker,
            original_timestamp=original_timestamp
        )
        
        # Prepare command
        command = f'{ECL_ENGINE_CONFIG["python_executable"]} {os.path.join(BASE_ECL_ENGINE, ECL_ENGINE_CONFIG["main_script"])} --configPath {new_config_path}'
        logger.info(f"Executing report generation command: {command}")
        logger.info(f"Using config file: {new_config_path}")
        logger.info(f"Output will be saved to timestamp folder: {new_timestamp}")
        
        # Initialize task status
        task_status[task_id] = {
            'status': 'Running',
            'data': data,
            'copied_files': [],
            'config_file': new_config_path,
            'timestamp': new_timestamp,
            'created_at': datetime.now().isoformat(),
            'command': command,
            'is_generate_report': True
        }
        
        with future_lock:
            future = executor.submit(process_ecl_task, command, data)
            future_to_task_id[future] = task_id
        
        return jsonify({
            'task_id': task_id,
            'status': 'pending',
            'timestamp': timestamp,
            'config_file': new_config_path
        }), 202
    
    except Exception as e:
        logger.error(f"Error generating report from record: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Full error traceback: {error_details}")
        return jsonify({
            'error': str(e),
            'traceback': error_details
        }), 500

# Run Management: Get review records from DB
@app.route('/get_eclengine_records', methods=['GET'])
def api_get_eclengine_records():
    try:
        records = get_eclengine_records()
        return jsonify({'records': records, 'count': len(records)}), 200
    except Exception as e:
        return jsonify({'error': f'Error getting ECL engine records: {str(e)}'}), 500
 
# Get Reporting Records
@app.route('/get_reporting_records', methods=['GET'])
def api_get_reporting_records():
    """Get reporting records list"""
    try:
        records = get_reporting_records()
        return jsonify({'records': records}), 200
    except Exception as e:
        logger.error(f"Error getting reporting records: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Get Reporting Dates from batch_status.log
@app.route('/get_reporting_dates', methods=['GET'])
def api_get_reporting_dates():
    try:
        status_file = os.path.join(BASE_ECL_ENGINE, 'batch_status.log')
        if not os.path.exists(status_file):
            logger.warning(f"Status file not found: {status_file}")
            return jsonify({'dates': []}), 200

        today = datetime.now().date()
        dates_set = set()

        with open(status_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(':', 1)
                if not parts:
                    continue

                date_str = parts[0].strip()
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"Invalid date format in batch_status.log: {date_str}")
                    continue

                if date_obj <= today:
                    dates_set.add(date_str)

        dates = sorted(dates_set, reverse=True)
        return jsonify({'dates': dates}), 200
    except Exception as e:
        logger.error(f"Error getting reporting dates: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Reporting Status Check
@app.route('/reporting_status/<task_id>', methods=['GET'])
def get_reporting_status(task_id):
    """Get reporting task status"""
    try:
        # First check status in memory
        if task_id in task_status:
            memory_status = task_status[task_id]
            return jsonify({
                'status': memory_status['status'],
                'timestamp': memory_status.get('timestamp', ''),
                'config_file': memory_status.get('config_file', '')
            })
        
        # If not in memory, check database
        record = get_reporting_record(task_id)
        if record:
            return jsonify({
                'status': record['status'],
                'timestamp': record['timestamp'],
                'config_file': f"run_config_file_{record['timestamp']}.json"
            })
        
        return jsonify({'error': 'Task not found'}), 404
    
    except Exception as e:
        logger.error(f"Error getting reporting status: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Task Status Check
@app.route('/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    try:
        # Search id in DB
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT status, settings FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            WHERE settings IS NOT NULL
            AND ISJSON(settings) = 1
            AND JSON_VALUE(settings, '$.task_id') = ?
        """, (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            status, settings_json = row
            settings = json.loads(settings_json) if settings_json else {}
            return jsonify({
                'task_id': task_id,
                'status': status,
                **settings
            }), 200
        # If no id in DB, then search in task_status
        if task_id in task_status:
            return jsonify(task_status[task_id]), 200
        logger.warning(f"Task {task_id} not found in DB or task_status. Available tasks: {list(task_status.keys())}")
        return jsonify({'error': 'Task not found', 'available_tasks': list(task_status.keys())}), 404
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {str(e)}")
        return jsonify({'error': f'Error getting task status: {str(e)}'}), 500

# Run Management: Save records to DB
@app.route('/save_eclengine_record', methods=['POST'])
def api_save_eclengine_record():
    try:
        data = request.get_json()
        maker = data.get('maker', '')
        time = data.get('time', datetime.now())
        settings = data.get('settings', '')
        action = data.get('action', '')
        status = data.get('status', 'In review')
        checker = data.get('checker', 'Waiting')
        save_eclengine_record(maker, time, settings, action, status, checker)
        return jsonify({'message': 'ECL engine record saved successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Error saving ECL engine record: {str(e)}'}), 500

# Confirm Reporting Record
@app.route('/confirm_reporting_record', methods=['POST'])
def confirm_reporting_record():
    """Confirm a reporting record - update status to Confirmed and set checker"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        checker = data.get('checker')
        
        if not task_id or not checker:
            return jsonify({'error': 'Missing required fields: task_id and checker'}), 400
        
        # Update the reporting record status and checker
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[UI_reporting_records]
            SET status = 'Confirmed', checker = ?
            WHERE task_id = ?
        """, (checker, task_id))
        
        rows_affected = cursor.rowcount
        conn.close()
        
        if rows_affected > 0:
            logger.info(f"Confirmed reporting record {task_id} with checker {checker}")
            return jsonify({'message': 'Reporting record confirmed successfully'}), 200
        else:
            logger.warning(f"No reporting record found with task_id {task_id}")
            return jsonify({'error': 'Reporting record not found'}), 404
    
    except Exception as e:
        logger.error(f"Error confirming reporting record: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Unconfirm Reporting Record
@app.route('/unconfirm_reporting_record', methods=['POST'])
def unconfirm_reporting_record():
    """Unconfirm a reporting record - update status from Confirmed back to Completed"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        checker = data.get('checker')
        
        if not task_id or not checker:
            return jsonify({'error': 'Missing required fields: task_id and checker'}), 400
        
        # Update the reporting record status back to Completed
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[UI_reporting_records]
            SET status = 'Completed', checker = ?
            WHERE task_id = ? AND status = 'Confirmed'
        """, (checker, task_id))
        
        rows_affected = cursor.rowcount
        conn.close()
        
        if rows_affected > 0:
            logger.info(f"Unconfirmed reporting record {task_id} with checker {checker}")
            return jsonify({'message': 'Reporting record unconfirmed successfully'}), 200
        else:
            logger.warning(f"No confirmed reporting record found with task_id {task_id}")
            return jsonify({'error': 'Confirmed reporting record not found'}), 404
    
    except Exception as e:
        logger.error(f"Error unconfirming reporting record: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Run Management: Download log files for a specific record
@app.route('/download_log_files/<task_id>', methods=['GET'])
def download_log_files(task_id):
    """Download log files for a specific ECL engine run"""
    try:
        # Get the record from database to find timestamp
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT settings, maker FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            WHERE settings IS NOT NULL
            AND ISJSON(settings) = 1
            AND JSON_VALUE(settings, '$.task_id') = ?
        """, (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Record not found'}), 404
        
        settings = json.loads(row[0]) if row[0] else {}
        timestamp = settings.get('timestamp', '')
        maker = row[1] if row[1] else 'Unknown User'
        
        if not timestamp:
            return jsonify({'error': 'No timestamp found for this record'}), 404
        
        # Construct the log folder path
        timestamp_folder = os.path.join(BASE_OUTPUT_FOLDER, timestamp)
        
        # Look for the automatically created folder structure
        log_folder_path = None
        if os.path.exists(timestamp_folder):
            for item in os.listdir(timestamp_folder):
                item_path = os.path.join(timestamp_folder, item)
                if os.path.isdir(item_path) and '_' in item:
                    # Check if this directory contains 01_log
                    log_path = os.path.join(item_path, '01_log')
                    if os.path.exists(log_path):
                        log_folder_path = log_path
                        break
        
        if not log_folder_path:
            return jsonify({'error': f'Log folder not found for timestamp: {timestamp}'}), 404
        
        # Log download activity
        log_download_activity(maker, "Run Management", f"ECL log files for {timestamp}")
        
        # Create a zip file of the log folder
        from io import BytesIO
        import zipfile
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(log_folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate the relative path for the zip file
                    relative_path = os.path.relpath(file_path, log_folder_path)
                    zip_file.write(file_path, relative_path)
        
        zip_buffer.seek(0)
        
        # Generate filename with timestamp
        filename = f"ecl_log_files_{timestamp}.zip"
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logger.error(f"Error downloading log files for task {task_id}: {str(e)}")
        return jsonify({'error': f'Error downloading log files: {str(e)}'}), 500
 
# Run Management: Download ECL results for a specific record
@app.route('/download_ecl_results/<task_id>', methods=['GET'])
def download_ecl_results(task_id):
    """Download entire timestamp folder for a specific ECL engine run"""
    try:
        # Get the record from database to find timestamp
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT settings, maker FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            WHERE settings IS NOT NULL
            AND ISJSON(settings) = 1
            AND JSON_VALUE(settings, '$.task_id') = ?
        """, (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Record not found'}), 404
        
        settings = json.loads(row[0]) if row[0] else {}
        timestamp = settings.get('timestamp', '')
        maker = row[1] if row[1] else 'Unknown User'
        
        if not timestamp:
            return jsonify({'error': 'No timestamp found for this record'}), 404
        
        # Construct the timestamp folder path
        timestamp_folder = os.path.join(BASE_OUTPUT_FOLDER, timestamp)
        
        # Check if the timestamp folder exists
        if not os.path.exists(timestamp_folder):
            return jsonify({'error': f'Timestamp folder not found: {timestamp_folder}'}), 404
        
        # Log download activity
        log_download_activity(maker, "Run Management", f"ECL results for {timestamp}")
        
        # Create a zip file of the entire timestamp folder
        from io import BytesIO
        import zipfile
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(timestamp_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate the relative path for the zip file (relative to timestamp folder)
                    relative_path = os.path.relpath(file_path, timestamp_folder)
                    zip_file.write(file_path, relative_path)
        
        zip_buffer.seek(0)
        
        # Generate filename with timestamp
        filename = f"ecl_results_{timestamp}.zip"
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logger.error(f"Error downloading ECL results for task {task_id}: {str(e)}")
        return jsonify({'error': f'Error downloading ECL results: {str(e)}'}), 500

# Download Reporting Logs
@app.route('/download_reporting_logs/<task_id>', methods=['GET'])
def download_reporting_logs(task_id):
    """Download reporting logs"""
    try:
        # Get reporting record
        record = get_reporting_record(task_id)
        if not record:
            return jsonify({'error': 'Reporting record not found'}), 404
        
        # Get the new timestamp from settings (where generate report logs are stored)
        settings = record.get('settings', {})
        if isinstance(settings, str):
            import json
            try:
                settings = json.loads(settings)
            except:
                settings = {}
        
        # Use the generate report timestamp (new_timestamp) instead of original_timestamp
        timestamp = settings.get('timestamp', record.get('original_timestamp', ''))
        
        # Build path to 01_log folder
        base_output_path = BASE_OUTPUT_FOLDER
        timestamp_folder = f"{base_output_path}/{timestamp}"
        
        # Find automatically created folder structure
        log_folder_path = None
        if os.path.exists(timestamp_folder):
            for item in os.listdir(timestamp_folder):
                item_path = os.path.join(timestamp_folder, item)
                if os.path.isdir(item_path) and '_' in item:
                    # Check if this directory contains 01_log
                    log_path = os.path.join(item_path, '01_log')
                    if os.path.exists(log_path):
                        log_folder_path = log_path
                        break
        
        if not log_folder_path:
            return jsonify({'error': f'Log folder not found for timestamp: {timestamp}'}), 404
        
        # Create zip file of logs
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(log_folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, log_folder_path)
                    zip_file.write(file_path, arc_name)
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'reporting_logs_{timestamp}.zip'
        )
    
    except Exception as e:
        logger.error(f"Error downloading reporting logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Download Reporting Reports
@app.route('/download_reporting_reports/<task_id>', methods=['GET'])
def download_reporting_reports(task_id):
    """Download reporting reports and redirect to reporting page"""
    try:
        # Get reporting record
        record = get_reporting_record(task_id)
        if not record:
            return jsonify({'error': 'Reporting record not found'}), 404
        
        if record['status'] != 'Completed':
            return jsonify({'error': 'Report is not ready yet'}), 400
        
        # Return redirect information - use the generate report timestamp where reports are stored
        # For generate report records, use the new timestamp from settings, not original_timestamp
        settings = record.get('settings', {})
        if isinstance(settings, str):
            import json
            try:
                settings = json.loads(settings)
            except:
                settings = {}
        
        # Use the generate report timestamp (new_timestamp) instead of original_timestamp
        report_timestamp = settings.get('timestamp', record.get('original_timestamp', ''))
        
        return jsonify({
            'redirect': True,
            'url': f'/reporting?timestamp={report_timestamp}&report_task_id={task_id}'
        }), 200
    
    except Exception as e:
        logger.error(f"Error downloading reporting reports: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==============================================================================
# 4. REPORTING
def download_single_report(report_type, report_base_path=None):
    """Download a single report file"""
    try:
        if report_type not in REPORT_FILES:
            return {'status': 'Failed', 'error': f'Unknown report type: {report_type}'}
        
        filename = REPORT_FILES[report_type]
        
        if report_base_path:
            # Use dynamic report base path with timestamp
            # ECL Engine automatically creates {data_yymm}_{timestamp_date}/03_result structure
            base_path = report_base_path
            # Look for the automatically created folder structure
            
            possible_paths = []
            # Check if the base path exists
            if os.path.exists(base_path):
                # Look for subdirectories that match the pattern {data_yymm}_{timestamp_date}
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)
                    if os.path.isdir(item_path) and '_' in item:
                        # Check if this directory contains 03_result
                        result_path = os.path.join(item_path, '03_result')
                        if os.path.exists(result_path):
                            possible_paths.append(result_path)
            
            # Use the first found path, or construct a default one
            if possible_paths:
                file_path = os.path.join(possible_paths[0], filename)
                logger.info(f"Found ECL Engine result folder: {possible_paths[0]}")
            else:
                # Fallback: try to construct the path assuming ECL Engine created it
                file_path = os.path.join(base_path, '03_result', filename)
                logger.warning(f"No ECL Engine result folder found, trying fallback path: {file_path}")
        else:
            # No dynamic path provided, cannot download
            logger.error("No report base path provided and no default path available")
            return {'status': 'Failed', 'error': 'No report base path available'}
        
        logger.info(f"Attempting to download {report_type} from: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"Report file not found: {file_path}")
            return {'status': 'Failed', 'error': f'Report file not found: {file_path}'}
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(file_path, filename)
        
        zip_buffer.seek(0)
        
        # Generate ZIP filename based on report type
        zip_filename = filename.replace('.xlsx', '.zip')
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
    except Exception as e:
        logger.error(f"Error downloading {report_type} report: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}

def download_multiple_reports(report_type, report_base_path=None):
    """Download multiple report files as a zip file"""
    try:
        from io import BytesIO
        import zipfile
        
        if report_type not in REPORT_FILES:
            return {'status': 'Failed', 'error': f'Unknown report type: {report_type}'}
        
        filenames = REPORT_FILES[report_type]
        if not isinstance(filenames, list):
            return {'status': 'Failed', 'error': f'Report type {report_type} is not configured for multiple files'}
        
        if report_base_path:
            # Use dynamic report base path with timestamp
            # ECL Engine automatically creates {data_yymm}_{timestamp_date}/03_result structure
            base_path = report_base_path
            # Look for the automatically created folder structure
            possible_paths = []
            
            # Check if the base path exists
            if os.path.exists(base_path):
                # Look for subdirectories that match the pattern {data_yymm}_{timestamp_date}
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)
                    if os.path.isdir(item_path) and '_' in item:
                        # Check if this directory contains 03_result
                        result_path = os.path.join(item_path, '03_result')
                        if os.path.exists(result_path):
                            possible_paths.append(result_path)
            
            # Use the first found path, or construct a default one
            if possible_paths:
                result_folder = possible_paths[0]
                logger.info(f"Found ECL Engine result folder: {result_folder}")
            else:
                # Fallback: try to construct the path assuming ECL Engine created it
                result_folder = os.path.join(base_path, '03_result')
                logger.warning(f"No ECL Engine result folder found, trying fallback path: {result_folder}")
        else:
            # No dynamic path provided, cannot download
            logger.error("No report base path provided and no default path available")
            return {'status': 'Failed', 'error': 'No report base path available'}
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            files_added = 0
            for filename in filenames:
                file_path = os.path.join(result_folder, filename)
                if os.path.exists(file_path):
                    zip_file.write(file_path, filename)
                    files_added += 1
                else:
                    logger.warning(f"Report file not found (skipping): {file_path}")
            
            if files_added == 0:
                return {'status': 'Failed', 'error': f'No {report_type} report files found'}
        
        zip_buffer.seek(0)
        
        # Generate ZIP filename based on report type
        zip_filename_map = {
            'bu_excel': 'BU_Excel_Reports.zip',
            'gl_posting': 'GL_Posting_Reports.zip'
        }
        zip_filename = zip_filename_map.get(report_type, f'{report_type}_Reports.zip')
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
    except Exception as e:
        logger.error(f"Error downloading {report_type} reports: {str(e)}")
        return {'status': 'Failed', 'error': str(e)}

# Reporting: Download ECL Monthly Report
@app.route('/download_ecl_monthly_report', methods=['GET'])
def download_ecl_monthly_report():
    try:
        # Get report_base_path from request args
        report_base_path = request.args.get('report_base_path')
        maker = request.args.get('maker', 'Unknown User')
        
        # Log download activity
        file_path = f"ECL Monthly Report from {report_base_path}" if report_base_path else "ECL Monthly Report"
        log_download_activity(maker, "Reporting", file_path)
        
        return download_single_report('ecl_monthly', report_base_path)
    except Exception as e:
        logger.error(f"Error in download_ecl_monthly_report: {str(e)}")
        return jsonify({'error': f'Error downloading ECL Monthly Report: {str(e)}'}), 500

# Reporting: Download ECL Summary Report
@app.route('/download_ecl_summary_report', methods=['GET'])
def download_ecl_summary_report():
    try:
        # Get report_base_path from request args
        report_base_path = request.args.get('report_base_path')
        maker = request.args.get('maker', 'Unknown User')
        
        # Log download activity
        file_path = f"ECL Summary Report from {report_base_path}" if report_base_path else "ECL Summary Report"
        log_download_activity(maker, "Reporting", file_path)
        
        return download_single_report('ecl_summary', report_base_path)
    except Exception as e:
        logger.error(f"Error in download_ecl_summary_report: {str(e)}")
        return jsonify({'error': f'Error downloading ECL Summary Report: {str(e)}'}), 500

# Reporting: Download BU Excel Reports
@app.route('/download_bu_excel_reports', methods=['GET'])
def download_bu_excel_reports():
    try:
        # Get report_base_path from request args
        report_base_path = request.args.get('report_base_path')
        maker = request.args.get('maker', 'Unknown User')
        
        # Log download activity
        file_path = f"BU Excel Reports from {report_base_path}" if report_base_path else "BU Excel Reports"
        log_download_activity(maker, "Reporting", file_path)
        
        return download_multiple_reports('bu_excel', report_base_path)
    except Exception as e:
        logger.error(f"Error in download_bu_excel_reports: {str(e)}")
        return jsonify({'error': f'Error downloading BU Excel Reports: {str(e)}'}), 500

# Reporting: Download HKMA Report
@app.route('/download_hkma_report', methods=['GET'])
def download_hkma_report():
    try:
        report_base_path = request.args.get('report_base_path')
        maker = request.args.get('maker', 'Unknown User')
        
        file_path = f"HKMA Report from {report_base_path}" if report_base_path else "HKMA Report"
        log_download_activity(maker, "Reporting", file_path)
        
        return download_single_report('hkma', report_base_path)
    except Exception as e:
        logger.error(f"Error in download_hkma_report: {str(e)}")
        return jsonify({'error': f'Error downloading HKMA Report: {str(e)}'}), 500

# Reporting: Download Audit Trial Report
@app.route('/download_audit_trial_report', methods=['GET'])
def download_audit_trial_report():
    try:
        report_base_path = request.args.get('report_base_path')
        maker = request.args.get('maker', 'Unknown User')
        
        file_path = f"Audit Trial Report from {report_base_path}" if report_base_path else "Audit Trial Report"
        log_download_activity(maker, "Reporting", file_path)
        
        return download_single_report('audit_trial', report_base_path)
    except Exception as e:
        logger.error(f"Error in download_audit_trial_report: {str(e)}")
        return jsonify({'error': f'Error downloading Audit Trial Report: {str(e)}'}), 500

# Reporting: Download GL Posting Report
@app.route('/download_gl_posting_report', methods=['GET'])
def download_gl_posting_report():
    try:
        report_base_path = request.args.get('report_base_path')
        maker = request.args.get('maker', 'Unknown User')
        
        file_path = f"GL Posting Report from {report_base_path}" if report_base_path else "GL Posting Report"
        log_download_activity(maker, "Reporting", file_path)
        
        return download_multiple_reports('gl_posting', report_base_path)
    except Exception as e:
        logger.error(f"Error in download_gl_posting_report: {str(e)}")
        return jsonify({'error': f'Error downloading GL Posting Report: {str(e)}'}), 500

# Reporting: Check report availability
@app.route('/check_report_availability', methods=['GET'])
def check_report_availability():
    try:
        availability = {}
        for report_type, filename in REPORT_FILES.items():
            if report_type == 'bu_excel':
                # Check all BU Excel files
                available_files = []
                for bu_filename in filename:
                    file_path = os.path.join(REPORT_BASE_PATH, bu_filename)
                    if os.path.exists(file_path):
                        available_files.append(bu_filename)
                availability[report_type] = {
                    'available': len(available_files) > 0,
                    'total_files': len(filename),
                    'available_files': available_files
                }
            else:
                # Check single file
                file_path = os.path.join(REPORT_BASE_PATH, filename)
                availability[report_type] = {
                    'available': os.path.exists(file_path),
                    'filename': filename
                }
        
        return jsonify({
            'availability': availability,
            'base_path': REPORT_BASE_PATH
        }), 200
    except Exception as e:
        logger.error(f"Error checking report availability: {str(e)}")
        return jsonify({'error': f'Error checking report availability: {str(e)}'}), 500
 
# Reporting: Check report availability for specific timestamp
@app.route('/check_report_availability/<timestamp>', methods=['GET'])
def check_report_availability_for_timestamp(timestamp):
    try:
        # Construct the base path for this timestamp
        base_path = os.path.join(BASE_OUTPUT_FOLDER, timestamp)
        
        # Check if the base path exists
        if not os.path.exists(base_path):
            logger.warning(f"Base path does not exist: {base_path}")
            return jsonify({'has_reports': False, 'error': 'Output folder not found'}), 200
        
        # Look for the automatically created folder structure {data_yymm}_{timestamp_date}
        possible_paths = []
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path) and '_' in item:
                # Check if this directory contains 03_result
                result_path = os.path.join(item_path, '03_result')
                if os.path.exists(result_path):
                    possible_paths.append(result_path)
                    logger.info(f"Found result folder: {result_path}")
        
        if not possible_paths:
            logger.warning(f"No result folders found in: {base_path}")
            logger.warning(f"Available items in {base_path}: {os.listdir(base_path) if os.path.exists(base_path) else 'N/A'}")
            return jsonify({'has_reports': False, 'error': 'No result folders found'}), 200
        
        # Check if any reports exist in the result folders
        has_reports = False
        for result_path in possible_paths:
            for report_type, filename in REPORT_FILES.items():
                if report_type == 'bu_excel':
                    # Check if at least one BU Excel file exists
                    for bu_filename in filename:
                        file_path = os.path.join(result_path, bu_filename)
                        if os.path.exists(file_path):
                            has_reports = True
                            break
                    if has_reports:
                        break
                else:
                    # Check single file
                    file_path = os.path.join(result_path, filename)
                    if os.path.exists(file_path):
                        has_reports = True
                        break
            if has_reports:
                break
        
        logger.info(f"Report availability check for timestamp {timestamp}: {has_reports}")
        return jsonify({'has_reports': has_reports}), 200
    
    except Exception as e:
        logger.error(f"Error checking report availability for timestamp {timestamp}: {str(e)}")
        return jsonify({'error': f'Error checking report availability: {str(e)}'}), 500 

@app.route('/confirm_ecl_result', methods=['POST'])
def confirm_ecl_result():
    """Confirm ECL result and log the confirmation"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        timestamp = data.get('timestamp')
        
        if not task_id or not timestamp:
            return jsonify({'error': 'Missing task_id or timestamp'}), 400
        
        # Get the settings from database
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT settings, maker FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            WHERE settings IS NOT NULL
            AND ISJSON(settings) = 1
            AND JSON_VALUE(settings, '$.task_id') = ?
        """, (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Record not found'}), 404
        
        settings = row[0] if row[0] else '{}'
        maker = row[1] if row[1] else 'Unknown User'
        
        # Log ECL result confirmation
        log_ecl_result_confirmation(maker, timestamp, settings)
        
        return jsonify({
            'message': 'ECL result confirmed successfully',
            'task_id': task_id,
            'timestamp': timestamp
        }), 200
    
    except Exception as e:
        logger.error(f"Error confirming ECL result: {str(e)}")
        return jsonify({'error': f'Error confirming ECL result: {str(e)}'}), 500
 
# ==============================================================================
# 5. ROLE MANAGEMENT
@app.route('/get_user_records', methods=['GET'])
def api_get_user_records():
    """Get all user records from database"""
    try:
        records = get_user_records()
        return jsonify({'status': 'success', 'records': records})
    except Exception as e:
        logger.error(f"Error in api_get_user_records: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/export_user_records', methods=['GET'])
def api_export_user_records():
    """Export all user records to CSV file"""
    try:
        csv_bytes = export_user_records_to_csv()
        if csv_bytes is None:
            return jsonify({'status': 'error', 'message': 'Failed to export user records'}), 500
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f'user_list_{timestamp}.csv'
        
        csv_bytes.seek(0)
        return send_file(
            csv_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Error in api_export_user_records: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_user_record', methods=['POST'])
def api_save_user_record():
    """Save user record to database"""
    try:
        data = request.get_json()
        success = save_user_record(
            user_name=data['user_name'],
            login_name=data['login_name'],
            default_role=data['default_role'],
            updated_by=data['updated_by'],
            time=data['time'],
            email=data.get('email'),
            mobile_no=data.get('mobile_no'),
            phone_no=data.get('phone_no'),
            remark=data.get('remark')
        )
        if success:
            return jsonify({'status': 'success', 'message': 'User record saved successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save user record'}), 500
    except Exception as e:
        logger.error(f"Error in api_save_user_record: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/update_user_record', methods=['POST'])
def api_update_user_record():
    """Update user record in database"""
    try:
        data = request.get_json()
        success = update_user_record(
            user_id=data['user_id'],
            user_name=data['user_name'],
            default_role=data['default_role'],
            email=data.get('email'),
            mobile_no=data.get('mobile_no'),
            phone_no=data.get('phone_no'),
            remark=data.get('remark'),
            updated_by=data['updated_by']
        )
        if success:
            return jsonify({'status': 'success', 'message': 'User record updated successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to update user record'}), 500
    except Exception as e:
        logger.error(f"Error in api_update_user_record: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_role_records', methods=['GET'])
def api_get_role_records():
    """Get all role records from database"""
    try:
        records = get_role_records()
        return jsonify({'status': 'success', 'records': records})
    except Exception as e:
        logger.error(f"Error in api_get_role_records: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_role_record', methods=['POST'])
def api_save_role_record():
    """Save role record to database"""
    try:
        data = request.get_json()
        success = save_role_record(
            role_name=data['role_name'],
            status=data['status'],
            updated_by=data['updated_by'],
            time=data['time']
        )
        if success:
            return jsonify({'status': 'success', 'message': 'Role record saved successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save role record'}), 500
    except Exception as e:
        logger.error(f"Error in api_save_role_record: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/update_role_record', methods=['POST'])
def api_update_role_record():
    """Update role record in database"""
    try:
        data = request.get_json()
        success = update_role_record(
            role_id=data['role_id'],
            role_name=data['role_name'],
            status=data['status'],
            updated_by=data['updated_by']
        )
        if success:
            return jsonify({'status': 'success', 'message': 'Role record updated successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to update role record'}), 500
    except Exception as e:
        logger.error(f"Error in api_update_role_record: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_function_records', methods=['GET'])
def api_get_function_records():
    """Get all function records from database"""
    try:
        records = get_function_records()
        return jsonify({'status': 'success', 'records': records})
    except Exception as e:
        logger.error(f"Error in api_get_function_records: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_function_record', methods=['POST'])
def api_save_function_record():
    """Save function record to database"""
    try:
        data = request.get_json()
        success = save_function_record(
            function_name=data['function_name'],
            status=data['status'],
            updated_by=data['updated_by'],
            time=data['time']
        )
        if success:
            return jsonify({'status': 'success', 'message': 'Function record saved successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save function record'}), 500
    except Exception as e:
        logger.error(f"Error in api_save_function_record: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/update_function_record', methods=['POST'])
def api_update_function_record():
    """Update function record in database"""
    try:
        data = request.get_json()
        success = update_function_record(
            function_id=data['function_id'],
            function_name=data['function_name'],
            status=data['status'],
            updated_by=data['updated_by']
        )
        if success:
            return jsonify({'status': 'success', 'message': 'Function record updated successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to update function record'}), 500
    except Exception as e:
        logger.error(f"Error in api_update_function_record: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_role_function_records/<role_name>', methods=['GET'])
def api_get_role_function_records(role_name):
    """Get all role-function records for a specific role from database"""
    try:
        records = get_role_function_records(role_name)
        return jsonify({'status': 'success', 'records': records})
    except Exception as e:
        logger.error(f"Error in api_get_role_function_records: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_role_function_record', methods=['POST'])
def api_save_role_function_record():
    """Save role-function record to database"""
    try:
        data = request.get_json()
        success = save_role_function_record(
            role_name=data['role_name'],
            function_name=data['function_name'],
            status=data['status'],
            updated_by=data['updated_by'],
            time=data['time']
        )
        if success:
            return jsonify({'status': 'success', 'message': 'Role-function record saved successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save role-function record'}), 500
    except Exception as e:
        logger.error(f"Error in api_save_role_function_record: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/update_role_function_record', methods=['POST'])
def api_update_role_function_record():
    """Update role-function record in database"""
    try:
        data = request.get_json()
        success = update_role_function_record(
            role_name=data['role_name'],
            function_name=data['function_name'],
            status=data['status'],
            updated_by=data['updated_by']
        )
        if success:
            return jsonify({'status': 'success', 'message': 'Role-function record updated successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to update role-function record'}), 500
    except Exception as e:
        logger.error(f"Error in api_update_role_function_record: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==============================================================================
# 6. AUDIT TRAIL
def create_audit_trial_folder():
    """Create the AuditTrial folder if it doesn't exist"""
    try:
        audit_folder = AUDIT_FOLDER
        os.makedirs(audit_folder, exist_ok=True)
        logger.info(f"AuditTrial folder created/verified: {audit_folder}")
        return True
    except Exception as e:
        logger.error(f"Error creating AuditTrial folder: {str(e)}")
        return False

def log_user_role_update(operation, user_name, page="Role Management", details=""):
    """Log user and role updates to the audit trail"""
    try:
        create_audit_trial_folder()
        log_file = AUDIT_LOGS['user_role_updates']
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"[{current_time}] User: {user_name} | Page: {page} | Operation: {operation} | Details: {details}\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        logger.info(f"Audit log entry added: {operation} by {user_name}")
        return True
    except Exception as e:
        logger.error(f"Error logging user role update: {str(e)}")
        return False

def log_download_activity(user_name, page, file_path):
    """Log download activities to the audit trail"""
    try:
        create_audit_trial_folder()
        log_file = AUDIT_LOGS['download']
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"[{current_time}] User: {user_name} | Page: {page} | Download File: {file_path}\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        logger.info(f"Download activity logged: {page} by {user_name}")
        return True
    except Exception as e:
        logger.error(f"Error logging download activity: {str(e)}")
        return False
 
def log_user_access(username, action, status, details=None):
    """Log user access activities (login/logout) to the audit trail"""
    try:
        create_audit_trial_folder()
        log_file = AUDIT_LOGS['user_access']
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"[{current_time}] User: {username} | Action: {action} | Status: {status}"
        if details:
            log_entry += f" | Details: {details}"
        log_entry += "\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        logger.info(f"User access logged: {action} by {username} - {status}")
        return True
    except Exception as e:
        logger.error(f"Error logging user access: {str(e)}")
        return False

def create_all_admin_logs():
    """Create a combined log file containing all admin logs"""
    try:
        create_audit_trial_folder()
        
        # Define admin log files to combine
        admin_log_files = [
            ('User & Role Updates', AUDIT_LOGS['user_role_updates']),
            ('User Access', AUDIT_LOGS['user_access']),
            ('Download Activity', AUDIT_LOGS['download'])
        ]
        
        # Create combined content
        combined_content = f"All Admin Logs - Combined Report\n"
        combined_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        combined_content += "=" * 80 + "\n\n"
        
        for log_name, log_file_path in admin_log_files:
            combined_content += f"\n{'='*20} {log_name} {'='*20}\n"
            
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        combined_content += content + "\n"
                    else:
                        combined_content += f"No entries found for {log_name}\n"
            else:
                combined_content += f"Log file not found: {log_name}\n"
            
            combined_content += "\n"
        
        # Create temporary file for download
        temp_file = BytesIO()
        temp_file.write(combined_content.encode('utf-8'))
        temp_file.seek(0)
        
        return send_file(
            temp_file,
            mimetype='text/plain',
            as_attachment=True,
            download_name='all_admin_logs.txt'
        )
    
    except Exception as e:
        logger.error(f"Error creating all admin logs: {str(e)}")
        return jsonify({'error': f'Error creating combined log: {str(e)}'}), 500

def log_ecl_result_confirmation(user_name, timestamp, settings):
    """Log ECL result confirmation to the audit trail"""
    try:
        create_audit_trial_folder()
        log_file = AUDIT_LOGS['ecl_confirmation']
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"[{current_time}] User: {user_name} | Page: Run Management | Operation: Approve Record | Timestamp: {timestamp} | Settings: {settings}\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        logger.info(f"ECL result confirmation logged: {timestamp} by {user_name}")
        return True
    except Exception as e:
        logger.error(f"Error logging ECL result confirmation: {str(e)}")
        return False

def log_parameter_update(user_name, operation_type, file_type, file_path):
    """Log parameter updates to the audit trail"""
    try:
        create_audit_trial_folder()
        log_file = AUDIT_LOGS['parameter_update']
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = f"[{current_time}] User: {user_name} | Page: Parameter | Operation: {operation_type} | Type: {file_type} | File Path: {file_path}\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        logger.info(f"Parameter update logged: {operation_type} {file_type} by {user_name}")
        return True
    except Exception as e:
        logger.error(f"Error logging parameter update: {str(e)}")
        return False

def generate_ecl_job_execution_log():
    """Generate ECL job execution log from database records where maker = 'Batch Run'"""
    try:
        create_audit_trial_folder()
        
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT time, settings, action, status, checker
            FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            WHERE maker = 'Batch Run'
            ORDER BY time DESC
        """)
        
        records = cursor.fetchall()
        conn.close()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_content = f"ECL Job Execution Log\n"
        log_content += f"Generated: {current_time}\n"
        log_content += "=" * 80 + "\n\n"
        
        if not records:
            log_content += "No Batch Run records found.\n"
        else:
            for row in records:
                time = row[0]
                settings = row[1] or ''
                action = row[2] or ''
                status = row[3] or ''
                checker = row[4] or 'Waiting'
                
                time_str = time.strftime('%Y-%m-%d %H:%M:%S') if isinstance(time, datetime) else str(time)
                
                settings_dict = {}
                try:
                    if settings:
                        settings_dict = json.loads(settings) if isinstance(settings, str) else settings
                except:
                    pass
                
                reporting_date = settings_dict.get('reportingDate', 'N/A')
                run_mode = settings_dict.get('runMode', 'N/A')
                timestamp = settings_dict.get('timestamp', 'N/A')
                
                log_entry = f"[{time_str}] Reporting Date: {reporting_date} | Run Mode: {run_mode} | Action: {action} | Status: {status} | Checker: {checker} | Timestamp: {timestamp}\n"
                log_content += log_entry
        
        temp_file = BytesIO()
        temp_file.write(log_content.encode('utf-8'))
        temp_file.seek(0)
        
        return send_file(
            temp_file,
            mimetype='text/plain',
            as_attachment=True,
            download_name='ecl_job_execution_log.txt'
        )
        
    except Exception as e:
        logger.error(f"Error generating ECL job execution log: {str(e)}")
        return jsonify({'error': f'Error generating log: {str(e)}'}), 500

@app.route('/download_audit_log/<log_type>', methods=['GET'])
def download_audit_log(log_type):
    """Download audit log files"""
    try:
        create_audit_trial_folder()
        
        if log_type == 'user_role_updates':
            log_file = AUDIT_LOGS['user_role_updates']
            filename = 'user_role_updates_log.txt'
        elif log_type == 'download_activity':
            log_file = AUDIT_LOGS['download']
            filename = 'download_log.txt'
        elif log_type == 'ecl_result_confirmation':
            log_file = AUDIT_LOGS['ecl_confirmation']
            filename = 'ecl_result_confirmation_log.txt'
        elif log_type == 'parameter_updates':
            log_file = AUDIT_LOGS['parameter_update']
            filename = 'parameter_update_log.txt'
        elif log_type == 'user_access':
            log_file = AUDIT_LOGS['user_access']
            filename = 'user_access_log.txt'
        elif log_type == 'ecl_job_execution':
            return generate_ecl_job_execution_log()
        elif log_type == 'all_admin_logs':
            return create_all_admin_logs()
        else:
            return jsonify({'error': 'Invalid log type'}), 400
        
        if not os.path.exists(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"Audit Log - {log_type.replace('_', ' ').title()}\n")
                f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
        
        return send_file(log_file, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Error downloading audit log {log_type}: {str(e)}")
        return jsonify({'error': f'Error downloading log: {str(e)}'}), 500

################################################################################################################################################################
#                           LOGIN AUTHENTICATION
################################################################################################################################################################
"""
This section contains 

Configuration Categories:
1. AD Validation                - 
2. Login Authentication         - 
"""
# ==============================================================================
# 1. AD VALIDATION
def validate_ad_user_id(user_id):
    """Validate AD user ID against Active Directory"""
    logger.info(f"Validating user ID: {user_id}")
    
    try:
        # Create LDAP server connection
        server = Server(LDAP_SERVER, get_info=ALL, connect_timeout=10)
    
        # Connect using SIMPLE authentication
        conn = Connection(
            server,
            user=LDAP_BIND_DN,
            password=LDAP_BIND_PASSWORD,
            authentication="SIMPLE",
            auto_bind=True
        )
    
        # Search for user
        search_filter = f'(sAMAccountName={user_id})'
        logger.info(f"Searching for user with filter: {search_filter}")
      
        conn.search(
            search_base=LDAP_SEARCH_BASE,
            search_filter=search_filter,
            attributes=['sAMAccountName', 'displayName', 'mail', 'userPrincipalName'],
            search_scope='SUBTREE'
        )
       
        if conn.entries:
            # User found
            user_entry = conn.entries[0]
            logger.info(f"User {user_id} found in AD")
            
            # Safely extract attributes from LDAP entry
            display_name = ''
            email = ''
            upn = ''
            
            try:
                if hasattr(user_entry, 'displayName') and user_entry.displayName:
                    display_name = str(user_entry.displayName.value)
            except:
                pass
            
            try:
                if hasattr(user_entry, 'mail') and user_entry.mail:
                    email = str(user_entry.mail.value)
            except:
                pass
            
            try:
                if hasattr(user_entry, 'userPrincipalName') and user_entry.userPrincipalName:
                    upn = str(user_entry.userPrincipalName.value)
            except:
                pass
            
            return {
                "status": "success",
                "message": f"User ID {user_id} exists in Active Directory",
                "user_id": user_id,
                "display_name": display_name,
                "email": email,
                "upn": upn
            }
        else:
            logger.warning(f"User {user_id} not found in AD")
            return {
                "status": "error",
                "message": f"User ID {user_id} not found"
            }
    
    except Exception as e:
        error_msg = f"LDAP search error: {str(e)}"
        logger.error(f"{error_msg}")
        return {
            "status": "error",
            "message": error_msg
        }
    finally:
        if 'conn' in locals():
            conn.unbind()

@app.route('/validate-ad-user', methods=['POST'])
def validate_ad_user():
    """Validate user against Active Directory"""
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
    
    user_id = data['user_id']
    
    # Validate user ID against AD
    result = validate_ad_user_id(user_id)
    
    return jsonify(result), 200 if result['status'] == 'success' else 404
 
# ==============================================================================
# 2. LOGIN AUTHENTICATION
@app.route('/validate-ldap-user', methods=['POST'])
def validate_ldap_user():
    """Validate user credentials against Active Directory with detailed error messages"""
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({"status": "error", "message": "Missing username or password"}), 400
        
        username = data['username']
        password = data['password']
        
        logger.info(f"Validating LDAP credentials for user: {username}")
        
        # Standardize username format for AD search
        if '\\' in username:
            # Handle domain\username format (e.g., hkg\u_eya_carsonkwan -> u_eya_carsonkwan)
            standardized_username = username.split('\\')[-1]
            logger.info(f"Standardized username from '{username}' to '{standardized_username}'")
        else:
            standardized_username = username
        
        # Create LDAP server connection
        server = Server(LDAP_SERVER, get_info=ALL, connect_timeout=10)
        
        # Step 1: Check if username exists in AD using service account
        try:
            # Connect using service account to search for user
            search_conn = Connection(
                server,
                user=LDAP_BIND_DN,
                password=LDAP_BIND_PASSWORD,
                authentication="SIMPLE",
                auto_bind=True
            )
            
            # Search for user with standardized username
            search_filters = [
                f'(sAMAccountName={standardized_username})',
                f'(userPrincipalName={standardized_username})',
                f'(cn={standardized_username})'
            ]
            
            user_found = False
            user_dn = None
            
            for search_filter in search_filters:
                logger.info(f"Searching for user with filter: {search_filter}")
                
                search_conn.search(
                    search_base=LDAP_SEARCH_BASE,
                    search_filter=search_filter,
                    attributes=['sAMAccountName', 'userPrincipalName', 'distinguishedName'],
                    search_scope='SUBTREE'
                )
                
                if search_conn.entries:
                    user_found = True
                    user_entry = search_conn.entries[0]
                    user_dn = str(user_entry.distinguishedName.value)
                    logger.info(f"User {username} found in AD with DN: {user_dn}")
                    break
            
            search_conn.unbind()
            
            # Step 2: If user not found, return invalid username
            if not user_found:
                logger.warning(f"User {username} not found in AD")
                # Log failed login attempt
                log_user_access(username, "LOGIN_ATTEMPT", "FAILED", "User not found in AD")
                return jsonify({
                    "status": "error",
                    "message": "Invalid username",
                    "error_type": "invalid_username"
                }), 401
           
            # Step 3: If user found, try to authenticate with password using different formats
            auth_success = False
            auth_formats = [
                user_dn,  # Full DN
                f"{standardized_username}@hkg.ho.cncb2",  # UPN format
                f"hkg\\{standardized_username}",  # Domain\username format
                standardized_username  # Just username
            ]
            
            # Prepare standardized username for database lookup (convert to lowercase)
            db_username = standardized_username.lower()
            
            for auth_format in auth_formats:
                try:
                    logger.info(f"Trying authentication with format: {auth_format}")
                    auth_conn = Connection(
                        server,
                        user=auth_format,
                        password=password,
                        authentication="SIMPLE",
                        auto_bind=True
                    )
                    
                    # If bind successful, credentials are valid
                    logger.info(f"LDAP authentication successful for user: {username} using format: {auth_format}")
                    auth_conn.unbind()
                    auth_success = True
                    break
                
                except Exception as auth_error:
                    logger.debug(f"Authentication Failed with format {auth_format}: {str(auth_error)}")
                    continue
            
            if auth_success:
                # Log successful LDAP authentication
                log_user_access(username, "LDAP_AUTH", "SUCCESS", f"Standardized username: {db_username}")
                return jsonify({
                    "status": "success",
                    "message": "LDAP authentication successful",
                    "standardized_username": db_username
                })
            else:
                logger.warning(f"Password authentication failed for user {username} with all formats")
                # Log failed password authentication
                log_user_access(username, "LOGIN_ATTEMPT", "FAILED", "Invalid password")
                return jsonify({
                    "status": "error",
                    "message": "Invalid password",
                    "error_type": "invalid_password"
                }), 401
        
        except Exception as search_error:
            logger.error(f"Error searching for user {username}: {str(search_error)}")
            return jsonify({
                "status": "error",
                "message": "Invalid username",
                "error_type": "invalid_username"
            }), 401
    
    except Exception as e:
        logger.error(f"Error in LDAP validation: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Authentication service error"
        }), 500

@app.route('/validate-user', methods=['POST'])
def validate_user():
    """Validate user exists in database and get user information"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({"status": "error", "message": "Missing username"}), 400
        
        username = data['username']
        logger.info(f"Validating user in database: {username}")
        
        # Check if user exists in database
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT id, user_name, login_name, default_role, email, mobile_no, phone_no, remark
            FROM [{DB_NAME}].[dbo].[UI_user_maintenance]
            WHERE LOWER(login_name) = LOWER(?)
        """, (username,))
        
        user_record = cursor.fetchone()
        conn.close()
        
        if user_record:
            user_data = {
                'id': user_record[0],
                'userName': user_record[1],
                'loginName': user_record[2],
                'defaultRole': user_record[3],
                'email': user_record[4] or '',
                'mobileNo': user_record[5] or '',
                'phoneNo': user_record[6] or '',
                'remark': user_record[7] or ''
            }
            
            logger.info(f"User validation successful: {username}")
            # Log successful user validation (final login success)
            log_user_access(username, "LOGIN_SUCCESS", "SUCCESS", f"User: {user_data['userName']}")
            return jsonify({
                "status": "success",
                "message": "User found in system",
                "user": user_data
            })
        else:
            logger.warning(f"User not found in database: {username}")
            # Log failed user validation (user not in system)
            log_user_access(username, "LOGIN_ATTEMPT", "FAILED", "User not found in system")
            return jsonify({
                "status": "error",
                "message": "Access Denied - User not found in system"
            }), 403
    
    except Exception as e:
        logger.error(f"Error in user validation: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "User validation service error"
        }), 500

@app.route('/get-user-permissions/<username>', methods=['GET'])
def get_user_permissions(username):
    """Get user permissions based on their role"""
    try:
        logger.info(f"Getting permissions for user: {username}")
        
        # Get user's role
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT default_role
            FROM [{DB_NAME}].[dbo].[UI_user_maintenance]
            WHERE LOWER(login_name) = LOWER(?)
        """, (username,))
        
        role_record = cursor.fetchone()
        if not role_record:
            conn.close()
            return jsonify({
                "status": "error",
                "message": "User not found"
            }), 404
        
        user_role = role_record[0]
        conn.close()
        
        # Get permissions for the user's role
        permissions = get_role_permissions(user_role)
        
        return jsonify({
            "status": "success",
            "permissions": permissions
        })
    
    except Exception as e:
        logger.error(f"Error getting user permissions: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Error retrieving permissions"
        }), 500

def get_role_permissions(role_name):
    """Get all active permissions for a specific role"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        # Get role-function table name
        table_name = f"UI_role_function_{role_name.replace(' ', '_').replace('-', '_')}"
        
        # Check if table exists
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM [{DB_NAME}].INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
        """, (table_name,))
        
        if cursor.fetchone()[0] == 0:
            conn.close()
            return []
        
        # Get active permissions for this role
        cursor.execute(f"""
            SELECT function_name
            FROM [{DB_NAME}].[dbo].[{table_name}]
            WHERE status = 'Active'
        """)
        
        permissions = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return permissions
    
    except Exception as e:
        logger.error(f"Error getting role permissions: {str(e)}")
        return []

@app.route('/validate-session', methods=['POST'])
def validate_session():
    """Validate user session"""
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({"status": "error", "message": "Missing username"}), 400
        
        username = data['username']
        logger.info(f"Validating session for user: {username}")
        
        # Check if user still exists and is active
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM [{DB_NAME}].[dbo].[UI_user_maintenance]
            WHERE login_name = ?
        """, (username,))
        
        user_exists = cursor.fetchone()[0] > 0
        conn.close()
        
        if user_exists:
            # Log successful session validation
            log_user_access(username, "SESSION_VALIDATION", "SUCCESS", "Session is valid")
            return jsonify({
                "status": "success",
                "message": "Session valid"
            })
        else:
            # Log failed session validation
            log_user_access(username, "SESSION_VALIDATION", "FAILED", "User no longer exists")
            return jsonify({
                "status": "error",
                "message": "User no longer exists"
            }), 403
    
    except Exception as e:
        logger.error(f"Error in session validation: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Session validation error"
        }), 500

@app.route('/logout', methods=['POST'])
def logout():
    """Handle user logout"""
    try:
        data = request.get_json()
        username = data.get('username', 'Unknown') if data else 'Unknown'
        
        # Log user logout
        log_user_access(username, "LOGOUT", "SUCCESS", "User logged out")
        
        return jsonify({
            "status": "success",
            "message": "Logout successful"
        })
    except Exception as e:
        logger.error(f"Error in logout: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Logout error"
        }), 500

################################################################################################################################################################
#                               RUN
################################################################################################################################################################
if __name__ == '__main__':
    logger.info("Starting Flask server on port 5010...")
    app.run(debug=True, port=5010)