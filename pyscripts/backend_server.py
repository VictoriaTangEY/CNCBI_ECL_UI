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
        file_type = request.args.get('type', 'all')  # 'parameter', 'adjustment', or 'all'
        # List all directories in the upload folder
        all_dirs = [d for d in os.listdir(BASE_UPLOAD_FOLDER)
                   if os.path.isdir(os.path.join(BASE_UPLOAD_FOLDER, d))]
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
def generate_new_config_file(reporting_date: str, run_mode: str, country: str):
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
        # Generate timestamp for new config file
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_config_filename = f'run_config_file_{timestamp}.json'
        new_config_path = os.path.join(BASE_ECL_ENGINE, new_config_filename)
        # Write the new config file
        with open(new_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Generated new config file: {new_config_path}")
        return {'status': 'success', 'config_path': new_config_path}
    except Exception as e:
        logger.error(f"Error generating new config file: {str(e)}")
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
        # Log the selections
        logger.info(f"Starting ECL engine with existing config file: {CONFIG_FILE_PATH}")
        logger.info(f"Selected parameters: {selected_parameters}")
        logger.info(f"Selected corrections: {selected_corrections}")
        logger.info(f"Reporting date: {reporting_date}")
        logger.info(f"Run mode: {run_mode}")
        logger.info(f"Country: {country}")
        # Copy selected files to PARAM_PATH
        copy_result = copy_files_to_param_path(selected_parameters, selected_corrections)
        if copy_result['status'] == 'failed':
            return jsonify({
                'error': f'Failed to copy files: {copy_result["error"]}'
            }), 500
        # Generate new config file with user selections
        config_result = generate_new_config_file(reporting_date, run_mode, country)
        if config_result['status'] == 'failed':
            return jsonify({
                'error': f'Failed to generate config file: {config_result["error"]}'
            }), 500
        # Use the new config file path
        new_config_path = config_result['config_path']
        # Generate task ID
        task_id = str(uuid.uuid4())
        # Assemble settings field, including task_id and all parameters
        settings = json.dumps({
            "task_id": task_id,
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
        # Initialize task status with creation timestamp
        task_status[task_id] = {
            'status': 'running',
            'data': data,
            'copied_files': copy_result.get('copied_files', []),
            'config_file': new_config_path,
            'created_at': datetime.now().isoformat(),
            'command': command
        }
        with future_lock:
            future = executor.submit(process_ecl_task, command, data)
            future_to_task_id[future] = task_id
        return jsonify({
            'task_id': task_id,
            'status': 'pending',
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


############################################################################ Run
if __name__ == '__main__':
    logger.info("Starting backend server...")
    if test_db_connection():
        create_ui_parameter_table()
    else:
        logger.error("Database connection failed")
    logger.info("Starting Flask server on port 5010...")
    app.run(debug=True, port=5010)