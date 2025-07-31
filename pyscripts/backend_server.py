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
from io import BytesIO
import pyodbc
import sys
from pathlib import Path
import json
from ldap3 import Server, Connection, ALL, NTLM
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


############################################################################ Logs
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'backend_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


############################################################################ Debugs
@app.before_request
def log_request():
    logger.info(f"Request: {request.method} {request.path}")
@app.after_request

def log_response_info(response):
    logger.info(f"Response: {response.status}")
    return response


############################################################################ Set-ups
# Base upload folder
BASE_UPLOAD_FOLDER = r'/u01/Apps/EY_working/ECL_UI_v0.1/interim/'

# Base approved folder
BASE_APPROVED_FOLDER = r'/u01/Apps/EY_working/ECL_UI_v0.1/approved/'

# Base ECL Engine folder
BASE_ECL_ENGINE = r'/u01/Apps/EY_working/ECL_Engine_v0.2/'
CONFIG_FILE_PATH = os.path.join(BASE_ECL_ENGINE, 'run_config_file.json')

# Report file paths
REPORT_FILES = {
    'ecl_monthly': 'reporting_ecl_result_to_rmg.xlsx',
    'ecl_summary': 'reporting_ecl_result_summary.xlsx',
    'bu_excel': [
        'ecl_result_by_BU_PBG-BB.xlsx',
        'ecl_result_by_BU_PBG-NON-BB.xlsx',
        'ecl_result_by_BU_TMG.xlsx',
        'ecl_result_by_BU_WBG.xlsx'
    ]
}


############################################################################ Threading
task_queue = Queue()
task_status: Dict[str, dict] = {}
executor = ProcessPoolExecutor(max_workers=2)
future_to_task_id = {}  # Future: task_id
future_lock = threading.Lock()


############################################################################ Polling
def process_ecl_task(command: str, data: dict):
    import os
    logger.info(f"Running ECL task with params: {data}")
    logger.info(f"Command to execute: {command}")
    logger.info(f"Working directory: {BASE_ECL_ENGINE}")
    logger.info(f"Current working directory: {os.getcwd()}")
    # Check if main.py exists
    main_py_path = os.path.join(BASE_ECL_ENGINE, "main.py")
    if not os.path.exists(main_py_path):
        error_msg = f"main.py not found at {main_py_path}"
        logger.error(error_msg)
        return {'status': 'failed', 'error': error_msg}
    # Check if main.py is executable
    if not os.access(main_py_path, os.R_OK):
        error_msg = f"main.py is not readable at {main_py_path}"
        logger.error(error_msg)
        return {'status': 'failed', 'error': error_msg}
    logger.info(f"main.py exists and is readable at {main_py_path}")
    try:
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=BASE_ECL_ENGINE
        )
        logger.info(f"Process completed with return code: {process.returncode}")
        logger.info(f"STDOUT: {process.stdout}")
        logger.info(f"STDERR: {process.stderr}")
        if process.returncode != 0:
            error_message = process.stderr or "Unknown error occurred"
            logger.error(f"ECL Engine failed with return code {process.returncode}")
            logger.error(f"Error message: {error_message}")
            return {'status': 'failed', 'error': error_message, 'stdout': process.stdout, 'stderr': process.stderr, 'return_code': process.returncode}
        else:
            logger.info("ECL Engine completed successfully")
            return {'status': 'completed', 'output': process.stdout}
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Exception in process_ecl_task: {str(e)}")
        logger.error(f"Full traceback: {error_details}")
        return {'status': 'failed', 'error': str(e), 'traceback': error_details}

def monitor_futures():
    while True:
        try:
            with future_lock:
                # Process completed tasks
                for future, task_id in list(future_to_task_id.items()):
                    if future.done() and task_status[task_id]['status'] == 'running':
                        try:
                            result = future.result()
                            task_status[task_id].update(result)
                            # Keep the task status in memory even after completion
                            # Don't remove from future_to_task_id to prevent 404 errors
                            logger.info(f"Task {task_id} completed with status: {result.get('status', 'unknown')}")
                            update_eclengine_status_in_db(task_id, result.get('status', 'unknown'))
                        except Exception as e:
                            logger.error(f"Error processing completed task {task_id}: {str(e)}")
                            task_status[task_id].update({'status': 'failed', 'error': str(e)})
                            update_eclengine_status_in_db(task_id, 'failed')
                    elif task_status[task_id]['status'] == 'running':
                        task_status[task_id]['status'] = 'running'
                        update_eclengine_status_in_db(task_id, 'running')
        except Exception as e:
            logger.error(f"Error in monitor_futures: {str(e)}")
        time.sleep(1)

monitor_thread = threading.Thread(target=monitor_futures, daemon=True)
monitor_thread.start()


############################################################################ DB-Connection
DB_DSN = 'ECLSITFSDB'
DB_USERNAME = 'eclappusr'
DB_PASSWORD = 'Abcdef123456'
DB_NAME = 'ey_test'
#============================================= Test =============================================
def test_db_connection():
    """Test database connection and log the result"""
    try:
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        # Test basic connection
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()
        logger.info(f"Database connection successful. SQL Server version: {version[0] if version else 'Unknown'}")
        # Check if target database exists
        cursor.execute(f"SELECT DB_ID('{DB_NAME}') as db_id")
        db_id = cursor.fetchone()[0]
        if not db_id:
            logger.error(f"Target database '{DB_NAME}' does not exist!")
            return False
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False

#============================================= Parameter =============================================
def create_ui_parameter_table():
    """Create the UI_Parameter_records table if it doesn't exist"""
    try:
        # First test connection
        if not test_db_connection():
            logger.error("Cannot create table - database connection failed")
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

def copy_folder_to_approved(source_folder_path):
    """
    Copy a folder from interim to approved directory
    """
    try:
        if not os.path.exists(source_folder_path):
            logger.error(f"Source folder does not exist: {source_folder_path}")
            return {'status': 'failed', 'error': 'Source folder does not exist'}
        # Create approved folder if it doesn't exist
        os.makedirs(BASE_APPROVED_FOLDER, exist_ok=True)
        # Get the folder name from the source path
        folder_name = os.path.basename(source_folder_path)
        destination_path = os.path.join(BASE_APPROVED_FOLDER, folder_name)
        # Check if destination already exists
        if os.path.exists(destination_path):
            logger.warning(f"Destination folder already exists: {destination_path}")
            return {'status': 'failed', 'error': 'Destination folder already exists'}
        # Copy the entire folder
        shutil.copytree(source_folder_path, destination_path)
        logger.info(f"Successfully copied folder from {source_folder_path} to {destination_path}")
        return {'status': 'success', 'destination': destination_path}
    except Exception as e:
        logger.error(f"Error copying folder to approved: {str(e)}")
        return {'status': 'failed', 'error': str(e)}


#============================================= Run Management =============================================
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
            WHERE JSON_VALUE(settings, '$.task_id') = ?
        """, (status, task_id))
        conn.close()
        logger.info(f"Updated DB status for task {task_id} to {status}")
    except Exception as e:
        logger.error(f"Error updating ECL engine status in DB for {task_id}: {str(e)}")

############################################################################ Main-Functions
#============================================= Parameter =============================================
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
            # Generate folder name and filename based on file type and suffix
            if file_type == 'parameter':
                folder_name = f"par_{timestamp}_{user_suffix}" if user_suffix else f"par_{timestamp}"
                new_filename = f"par_{timestamp}_{user_suffix}{file_extension}" if user_suffix else f"par_{timestamp}{file_extension}"
            elif file_type == 'adjustment':
                folder_name = f"adj_{timestamp}_{user_suffix}" if user_suffix else f"adj_{timestamp}"
                new_filename = f"adj_{timestamp}_{user_suffix}{file_extension}" if user_suffix else f"adj_{timestamp}{file_extension}"
            else:
                # Fallback to original filename if file type is unknown
                folder_name = timestamp
                new_filename = original_filename
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
                    maker=maker or 'RMGUser_1',
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
                    maker=maker or 'RMGUser_1',
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
                return jsonify({
                    'message': f'File "{new_filename}" uploaded successfully',
                    'path': file_path,
                    'original_name': original_filename,
                    'new_name': new_filename
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
        checker = data.get('checker', 'RMGUser_2')
        
        # Get the file_path from the database before updating
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        
        # First, get the file_path for this record
        cursor.execute(f"""
            SELECT file_path FROM [{DB_NAME}].[dbo].[UI_Parameter_records] WHERE id = ?
        """, (record_id,))
        result = cursor.fetchone()
        
        if not result or not result[0]:
            conn.close()
            return jsonify({'error': 'File path not found for this record'}), 404
        
        file_path = result[0]
        
        # Update the status in database
        cursor.execute(f"""
            UPDATE [{DB_NAME}].[dbo].[UI_Parameter_records]
            SET status = ?, checker = ?
            WHERE id = ?
        """, (new_status, checker, record_id))
        conn.close()
        
        # If the status is being changed to 'Approved', copy the folder to approved directory
        if new_status == 'Approved':
            copy_result = copy_folder_to_approved(file_path)
            if copy_result['status'] == 'success':
                logger.info(f"Record {record_id} approved and folder copied to approved directory")
                return jsonify({
                    'message': 'Status updated successfully and folder copied to approved directory',
                    'copy_result': copy_result
                }), 200
            else:
                logger.error(f"Failed to copy folder for approved record {record_id}: {copy_result['error']}")
                return jsonify({
                    'message': 'Status updated successfully but failed to copy folder to approved directory',
                    'copy_error': copy_result['error']
                }), 200
        else:
            return jsonify({'message': 'Status updated successfully'}), 200
            
    except Exception as e:
        logger.error(f"Error updating approval status: {str(e)}")
        return jsonify({'error': f'Error updating approval status: {str(e)}'}), 500

# Move approved files
@app.route('/get_approved_files', methods=['GET'])
def get_approved_files():
    try:
        file_type = request.args.get('type', 'all')  # 'parameter', 'adjustment', or 'all'
        # Check if approved folder exists
        if not os.path.exists(BASE_APPROVED_FOLDER):
            return jsonify({
                'files': [],
                'base_path': BASE_APPROVED_FOLDER,
                'message': 'Approved folder does not exist yet'
            }), 200
        
        # List all directories in the approved folder
        all_dirs = [d for d in os.listdir(BASE_APPROVED_FOLDER)
                   if os.path.isdir(os.path.join(BASE_APPROVED_FOLDER, d))]
        # Filter based on file type
        if file_type == 'parameter':
            files = [d for d in all_dirs if d.startswith('par_')]
        elif file_type == 'adjustment':
            files = [d for d in all_dirs if d.startswith('adj_')]
        else:
            files = all_dirs
        # Sort files by timestamp (newest first)
        files.sort(reverse=True)
        return jsonify({
            'files': files,
            'base_path': BASE_APPROVED_FOLDER
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error getting approved file list: {str(e)}'}), 500

# Parameter: Download files when click "Download" button
@app.route('/download_files/<record_id>', methods=['GET'])
def download_files(record_id):
    try:
        # Get the file path from database
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT file_path FROM [{DB_NAME}].[dbo].[UI_Parameter_records] WHERE id = ?
        """, (record_id,))
        result = cursor.fetchone()
        conn.close()
        if not result or not result[0]:
            return jsonify({'error': 'File path not found'}), 404
        file_path = result[0]
        # Check if directory exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'File directory not found'}), 404
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

#============================================= Run Management =============================================
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

# Run Management: Folder maintenance
def copy_files_to_param_path(selected_parameters: str, selected_corrections: str):
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
        return {'status': 'failed', 'error': str(e)}

# Run Management: Generate new config file
def generate_new_config_file(reporting_date: str, run_mode: str, country: str, ui_timestamp: str = None):
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
        if country:
            config['RUN_SETTING']['COUNTRY'] = country
        
        # Use UI timestamp if provided, otherwise generate new one
        if ui_timestamp:
            timestamp = ui_timestamp
        else:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
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
            return {'status': 'failed', 'error': f'Failed to create output folder: {str(e)}'}
        
        new_config_filename = f'run_config_file_{timestamp}.json'
        new_config_path = os.path.join(BASE_ECL_ENGINE, new_config_filename)
        # Write the new config file
        with open(new_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Generated new config file: {new_config_path}")
        return {'status': 'success', 'config_path': new_config_path, 'timestamp': timestamp}
    except Exception as e:
        logger.error(f"Error generating new config file: {str(e)}")
        return {'status': 'failed', 'error': str(e)}

def modify_existing_config_file(config_filename: str, resume_run_mode: str):
    """
    Modify an existing config file for resume run by updating RUN_MODE
    """
    try:
        # Construct the full path to the existing config file
        existing_config_path = os.path.join(BASE_ECL_ENGINE, config_filename)
        
        # Check if the config file exists
        if not os.path.exists(existing_config_path):
            return {'status': 'failed', 'error': f'Config file not found: {config_filename}'}
        
        # Read the existing config file
        import json
        with open(existing_config_path, 'r') as f:
            config = json.load(f)
        
        # Update only the RUN_MODE, keep everything else the same
        if resume_run_mode:
            config['RUN_SETTING']['RUN_MODE'] = str(resume_run_mode)
        
        # Write the modified config back to the same file
        with open(existing_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Modified existing config file: {existing_config_path} with RUN_MODE: {resume_run_mode}")
        return {'status': 'success', 'config_path': existing_config_path}
    except Exception as e:
        logger.error(f"Error modifying existing config file: {str(e)}")
        return {'status': 'failed', 'error': str(e)}

# Run Management: Run ECL Engine
@app.route('/run_ecl_engine', methods=['POST'])
def run_ecl_engine():
    try:
        data = request.get_json()
        selected_parameters = data.get('selectedParameters', '')
        selected_corrections = data.get('selectedCorrections', '')
        reporting_date = data.get('reportingDate', '')
        run_mode = data.get('runMode', '')
        country = data.get('country', '')
        ui_timestamp = data.get('ui_timestamp', '')  # Get UI timestamp from request
        
        # Log the selections
        logger.info(f"Starting ECL engine with existing config file: {CONFIG_FILE_PATH}")
        logger.info(f"Selected parameters: {selected_parameters}")
        logger.info(f"Selected corrections: {selected_corrections}")
        logger.info(f"Reporting date: {reporting_date}")
        logger.info(f"Run mode: {run_mode}")
        logger.info(f"Country: {country}")
        logger.info(f"UI timestamp: {ui_timestamp}")
        
        # Copy selected files to PARAM_PATH
        copy_result = copy_files_to_param_path(selected_parameters, selected_corrections)
        if copy_result['status'] == 'failed':
            return jsonify({
                'error': f'Failed to copy files: {copy_result["error"]}'
            }), 500
        
        # Generate new config file with user selections and UI timestamp
        config_result = generate_new_config_file(reporting_date, run_mode, country, ui_timestamp)
        if config_result['status'] == 'failed':
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
            "selectedParameters": selected_parameters,
            "selectedCorrections": selected_corrections,
            "reportingDate": reporting_date,
            "runMode": run_mode,
            "country": country
        })
        
        now_dt = datetime.now()
        # Save to DB
        save_eclengine_record(
            maker='RMGUser_1',
            time=now_dt,
            settings=settings,
            action=data.get('action', ''),
            status='running',
            checker='Waiting'
        )
        update_eclengine_status_in_db(task_id, 'running')
        
        # Prepare command with new config file
        command = f'python3 {os.path.join(BASE_ECL_ENGINE, "main.py")} --configPath {new_config_path}'
        logger.info(f"Executing command: {command}")
        logger.info(f"Working directory: {BASE_ECL_ENGINE}")
        logger.info(f"Using config file: {new_config_path}")
        logger.info(f"Output will be saved to timestamp folder: {timestamp}")
        
        # Initialize task status with creation timestamp
        task_status[task_id] = {
            'status': 'running',
            'data': data,
            'copied_files': copy_result.get('copied_files', []),
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
            'copied_files': copy_result.get('copied_files', []),
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
        config_result = modify_existing_config_file(selected_resume_config, selected_resume_run_mode)
        if config_result['status'] == 'failed':
            return jsonify({
                'error': f'Failed to modify config file: {config_result["error"]}'
            }), 500
        
        # Use the modified config file path
        modified_config_path = config_result['config_path']
        
        # Extract timestamp from config filename for output path
        # Config filename format: run_config_file_YYYYMMDDHHMMSS.json
        config_filename_without_ext = selected_resume_config.replace('.json', '')
        timestamp = config_filename_without_ext.replace('run_config_file_', '')
        
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
            maker='RMGUser_1',
            time=now_dt,
            settings=settings,
            action=resume_action_comment,
            status='running',
            checker='Waiting'
        )
        update_eclengine_status_in_db(task_id, 'running')
        
        # Prepare command with modified config file
        command = f'python3 {os.path.join(BASE_ECL_ENGINE, "main.py")} --configPath {modified_config_path}'
        logger.info(f"Executing resume command: {command}")
        logger.info(f"Working directory: {BASE_ECL_ENGINE}")
        logger.info(f"Using modified config file: {modified_config_path}")
        logger.info(f"Output will continue in existing folder: {timestamp}")
        
        # Initialize task status
        task_status[task_id] = {
            'status': 'running',
            'data': data,
            'config_file': modified_config_path,
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
            'config_file': modified_config_path
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

# Generate Report
@app.route('/generate_report', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        selected_report_config = data.get('selectedReportConfig', '')
        selected_report_run_mode = data.get('selectedReportRunMode', '')
        report_action_comment = data.get('reportActionComment', '')
        ui_timestamp = data.get('ui_timestamp', '')
        
        # Log the report generation selections
        logger.info(f"Generating report with config file: {selected_report_config}")
        logger.info(f"Report run mode: {selected_report_run_mode}")
        logger.info(f"Report action comment: {report_action_comment}")
        logger.info(f"UI timestamp: {ui_timestamp}")
        
        # Modify the existing config file with run mode 6
        config_result = modify_existing_config_file(selected_report_config, selected_report_run_mode)
        if config_result['status'] == 'failed':
            return jsonify({
                'error': f'Failed to modify config file: {config_result["error"]}'
            }), 500
        
        # Use the modified config file path
        modified_config_path = config_result['config_path']
        
        # Extract timestamp from config filename for output path
        # Config filename format: run_config_file_YYYYMMDDHHMMSS.json
        config_filename_without_ext = selected_report_config.replace('.json', '')
        timestamp = config_filename_without_ext.replace('run_config_file_', '')
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Assemble settings field for report generation
        settings = json.dumps({
            "task_id": task_id,
            "timestamp": timestamp,
            "isResume": False,
            "isGenerateReport": True,
            "resumedVersion": selected_report_config,
            "runMode": selected_report_run_mode,
            "selectedParameters": "",  # Report generation doesn't have parameters
            "selectedCorrections": "",  # Report generation doesn't have adjustments
            "reportingDate": "",  # Report generation doesn't have reporting date
            "country": ""  # Report generation doesn't have country
        })
        
        now_dt = datetime.now()
        # Save to DB
        save_eclengine_record(
            maker='RMGUser_1',
            time=now_dt,
            settings=settings,
            action=report_action_comment,
            status='running',
            checker='Waiting'
        )
        update_eclengine_status_in_db(task_id, 'running')
        
        # Prepare command with modified config file
        command = f'python3 {os.path.join(BASE_ECL_ENGINE, "main.py")} --configPath {modified_config_path}'
        logger.info(f"Executing report generation command: {command}")
        logger.info(f"Working directory: {BASE_ECL_ENGINE}")
        logger.info(f"Using modified config file: {modified_config_path}")
        logger.info(f"Output will continue in existing folder: {timestamp}")
        
        # Initialize task status
        task_status[task_id] = {
            'status': 'running',
            'data': data,
            'config_file': modified_config_path,
            'timestamp': timestamp,
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
            'config_file': modified_config_path
        }), 202
    except Exception as e:
        logger.error(f"Error initiating report generation: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Full error traceback: {error_details}")
        return jsonify({
            'error': str(e),
            'traceback': error_details
        }), 500

# Task Status Check
@app.route('/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    try:
        # Search id in DB
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT status, settings FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            WHERE JSON_VALUE(settings, '$.task_id') = ?
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

# Run Management: Get review records from DB
@app.route('/get_eclengine_records', methods=['GET'])
def api_get_eclengine_records():
    try:
        records = get_eclengine_records()
        return jsonify({'records': records, 'count': len(records)}), 200
    except Exception as e:
        return jsonify({'error': f'Error getting ECL engine records: {str(e)}'}), 500

# Run Management: Download log files for a specific record
@app.route('/download_log_files/<task_id>', methods=['GET'])
def download_log_files(task_id):
    """Download log files for a specific ECL engine run"""
    try:
        # Get the record from database to find timestamp
        conn = pyodbc.connect(f'DSN={DB_DSN};UID={DB_USERNAME};PWD={DB_PASSWORD}', autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT settings FROM [{DB_NAME}].[dbo].[UI_eclengine_records]
            WHERE JSON_VALUE(settings, '$.task_id') = ?
        """, (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Record not found'}), 404
        
        settings = json.loads(row[0]) if row[0] else {}
        timestamp = settings.get('timestamp', '')
        
        if not timestamp:
            return jsonify({'error': 'No timestamp found for this record'}), 404
        
        # Construct the log folder path
        base_output_path = "/u01/Apps/EY_working/99_data/03_output_folder"
        timestamp_folder = f"{base_output_path}/{timestamp}"
        
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

#============================================= Reporting =============================================
def download_single_report(report_type, report_base_path=None):
    """Download a single report file"""
    try:
        if report_type not in REPORT_FILES:
            return {'status': 'failed', 'error': f'Unknown report type: {report_type}'}
        
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
            return {'status': 'failed', 'error': 'No report base path available'}
        
        logger.info(f"Attempting to download {report_type} from: {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"Report file not found: {file_path}")
            return {'status': 'failed', 'error': f'Report file not found: {file_path}'}
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error downloading {report_type} report: {str(e)}")
        return {'status': 'failed', 'error': str(e)}

def download_bu_reports(report_base_path=None):
    """Download all BU Excel reports as a zip file"""
    try:
        from io import BytesIO
        import zipfile
        
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
            return {'status': 'failed', 'error': 'No report base path available'}
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            files_added = 0
            for filename in REPORT_FILES['bu_excel']:
                file_path = os.path.join(result_folder, filename)
                if os.path.exists(file_path):
                    zip_file.write(file_path, filename)
                    files_added += 1
                else:
                    logger.warning(f"BU report file not found: {file_path}")
            
            if files_added == 0:
                return {'status': 'failed', 'error': 'No BU report files found'}
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='BU_Excel_Reports.zip'
        )
    except Exception as e:
        logger.error(f"Error downloading BU reports: {str(e)}")
        return {'status': 'failed', 'error': str(e)}

# Reporting: Download ECL Monthly Report
@app.route('/download_ecl_monthly_report', methods=['GET'])
def download_ecl_monthly_report():
    try:
        # Get report_base_path from request args
        report_base_path = request.args.get('report_base_path')
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
        return download_bu_reports(report_base_path)
    except Exception as e:
        logger.error(f"Error in download_bu_excel_reports: {str(e)}")
        return jsonify({'error': f'Error downloading BU Excel Reports: {str(e)}'}), 500

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
        base_path = f'/u01/Apps/EY_working/99_data/03_output_folder/{timestamp}'
        
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
        
        if not possible_paths:
            logger.warning(f"No result folders found in: {base_path}")
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


############################################################################ AD Validation
# LDAP Configuration (Update these with your AD details)
LDAP_SERVER = 'ldap://10.30.244.12:389'
LDAP_BIND_DN = 'CN=svreclappmgr, OU=Service Accounts,OU=Tier1,OU=Admin,OU=HKG,DC=hkg,DC=ho,DC=cncb2'
LDAP_BIND_PASSWORD = 'Cncbi@567890'
LDAP_SEARCH_BASE = 'OU=User Accounts,OU=HKG,DC=hkg,DC=ho,DC=cncb2'

def validate_ad_user_id(user_id):
    try:
        # Initialize LDAP server
        server = Server(LDAP_SERVER, get_info=ALL)
        
        # Connect to LDAP server using service account
        conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PASSWORD, authentication=NTLM)
        
        if not conn.bind():
            return {"status": "error", "message": "Failed to connect to LDAP server"}
        
        # Search for user by sAMAccountName
        search_filter = f'(sAMAccountName={user_id})'
        conn.search(
            search_base=LDAP_SEARCH_BASE,
            search_filter=search_filter,
            attributes=['sAMAccountName', 'displayName', 'mail']
        )
        
        if conn.entries:
            # User found, return user details
            user_entry = conn.entries[0]
            return {
                "status": "success", 
                "message": f"User ID {user_id} exists in Active Directory",
                "user_id": user_id,
                "display_name": str(user_entry.get('displayName', '')),
                "email": str(user_entry.get('mail', ''))
            }
        else:
            return {"status": "error", "message": f"User ID {user_id} not found"}
            
    except Exception as e:
        return {"status": "error", "message": f"LDAP error: {str(e)}"}
    finally:
        if 'conn' in locals():
            conn.unbind()

@app.route('/validate-ad-user', methods=['POST'])
def validate_user():
    # Expect JSON payload with user_id
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({"status": "error", "message": "Missing user_id"}), 400
    
    user_id = data['user_id']
    
    # Validate user ID against AD
    result = validate_ad_user_id(user_id)
    
    return jsonify(result), 200 if result['status'] == 'success' else 404

############################################################################ Run
if __name__ == '__main__':
    logger.info("Starting backend server...")
    if test_db_connection():
        create_ui_parameter_table()
    else:
        logger.error("Database connection failed")
    logger.info("Starting Flask server on port 5010...")
    app.run(debug=True, port=5010)