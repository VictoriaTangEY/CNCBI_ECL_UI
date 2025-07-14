import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from werkzeug.utils import secure_filename
import zipfile
import shutil
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Set-ups
# Base parameter upload folder
BASE_UPLOAD_FOLDER = r'C:/Users/UV665AR/OneDrive - EY/Documents/GitHub/CNCBI_ECL_UI/EY_working/99_data/04_UI_param_interim'
app.config['UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER

# Base ECL Engine folder
BASE_ECL_ENGINE = r'C:/Users/UV665AR/OneDrive - EY/Documents/GitHub/CNCBI_ECL_UI/EY_working/ECL_Engine'
CONFIG_FILE_PATH = os.path.join(BASE_ECL_ENGINE, 'src', 'run_config_file.json')


# Parameter: Upload File
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        file_type = request.form.get('fileType', '')  # parameter or dataCorrection
        suffix = request.form.get('suffix', '')  # user input suffix
        category = request.form.get('category', '')  # parameter category
        
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # Generate timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Create folder name with proper format: par/adj_timestamp_category_suffix
        folder_prefix = 'par_' if file_type == 'parameter' else 'adj_'
        folder_name = f"{folder_prefix}{timestamp}"
        
        # Add category
        if category:
            folder_name = f"{folder_name}_{category}"
        
        # Add suffix if provided
        if suffix:
            folder_name = f"{folder_name}_{suffix}"

        # Create folder path
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # Keep the original filename
        original_filename = secure_filename(file.filename)
        file_path = os.path.join(folder_path, original_filename)

        # Check if file is a zip file
        if original_filename.lower().endswith('.zip'):
            # Save zip file temporarily
            temp_zip_path = os.path.join(folder_path, 'temp.zip')
            file.save(temp_zip_path)
            
            # Extract zip file
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(folder_path)
            
            # Remove the temporary zip file
            os.remove(temp_zip_path)
            
            # If zip file contains a single folder, move its contents up
            contents = os.listdir(folder_path)
            if len(contents) == 1 and os.path.isdir(os.path.join(folder_path, contents[0])):
                inner_dir = os.path.join(folder_path, contents[0])
                # Move all files from inner directory to folder_path
                for item in os.listdir(inner_dir):
                    shutil.move(os.path.join(inner_dir, item), folder_path)
                # Remove the empty directory
                os.rmdir(inner_dir)
        else:
            # For non-zip files, save directly
            file.save(file_path)
        
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': original_filename,
            'folder': folder_name,
            'category': category
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        elif file_type == 'dataCorrection':
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

# Run Management: Update Configuration File
@app.route('/update_run_config', methods=['POST'])
def update_run_config():
    try:
        # Read the current config file
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
        
        # Create a timestamp for the new config file
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_config_path = os.path.join(BASE_ECL_ENGINE, 'src', f'run_config_file_{timestamp}.json')
        
        # Clear the specified fields
        config['RUN_SETTING']['DATA_YYMM'] = ""
        config['RUN_SETTING']['RUN_MODE'] = ""
        
        # Save the new config file
        with open(new_config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
        return jsonify({
            'message': 'Configuration file updated successfully',
            'new_config_path': new_config_path
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Test: show run time
@app.route('/test', methods=['GET'])
def test():
    import datetime
    print("test endpoint was called")
    result = f"TIME:{datetime.datetime.now()}"
    return jsonify({'result': result})


if __name__ == '__main__':
    print("Starting consolidated backend server...")
    app.run(host='0.0.0.0', port=5010)
