import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Base upload folder
BASE_UPLOAD_FOLDER = r'C:/Users/UV665AR/OneDrive - EY/Documents/GitHub/CNCBI_ECL_UI/EY_working/99_data/02_param_upload_folder'

@app.route('/get_uploaded_files', methods=['GET'])
def get_uploaded_files():
    try:
        file_type = request.args.get('type', 'all')  # 'parameter', 'dataCorrection', or 'all'
        
        # List all directories in the upload folder
        all_dirs = [d for d in os.listdir(BASE_UPLOAD_FOLDER) 
                   if os.path.isdir(os.path.join(BASE_UPLOAD_FOLDER, d))]
        
        # Filter based on file type
        if file_type == 'parameter':
            files = [d for d in all_dirs if d.startswith('param_')]
        elif file_type == 'dataCorrection':
            files = [d for d in all_dirs if d.startswith('dc_')]
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

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    file_type = request.form.get('fileType', 'unknown')  # Get file type from form data
    user_suffix = request.form.get('suffix', '')  # Get user input suffix

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file:
        try:
            # Get current timestamp in format yyyymmddHHMMSS
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Get original file extension
            original_filename = file.filename
            file_extension = os.path.splitext(original_filename)[1] if '.' in original_filename else ''
            
            # Generate folder name and filename based on file type and suffix
            if file_type == 'parameter':
                folder_name = f"param_{timestamp}_{user_suffix}" if user_suffix else f"param_{timestamp}"
                new_filename = f"param_{timestamp}_{user_suffix}{file_extension}" if user_suffix else f"param_{timestamp}{file_extension}"
            elif file_type == 'dataCorrection':
                folder_name = f"dc_{timestamp}_{user_suffix}" if user_suffix else f"dc_{timestamp}"
                new_filename = f"dc_{timestamp}_{user_suffix}{file_extension}" if user_suffix else f"dc_{timestamp}{file_extension}"
            else:
                # Fallback to original filename if file type is unknown
                folder_name = timestamp
                new_filename = original_filename

            # Create new folder path using the generated folder name
            new_upload_folder = os.path.join(BASE_UPLOAD_FOLDER, folder_name)

            # Create folder if it doesn't exist
            os.makedirs(new_upload_folder, exist_ok=True)

            # Create full file path with new filename
            file_path = os.path.join(new_upload_folder, new_filename)

            # Save the file
            file.save(file_path)

            return jsonify({
                'message': f'File "{new_filename}" uploaded successfully',
                'path': file_path,
                'original_name': original_filename,
                'new_name': new_filename
            }), 200

        except Exception as e:
            return jsonify({'error': f'Error saving file: {str(e)}'}), 500

@app.route('/test', methods=['GET'])
def test():
    import datetime
    print("test endpoint was called")
    result = f"TIME:{datetime.datetime.now()}"
    return jsonify({'result': result})

if __name__ == '__main__':
    print("Starting consolidated backend server...")
    print("Upload endpoint available at: http://localhost:5010/upload")
    print("Test endpoint available at: http://localhost:5010/test")
    app.run(host='0.0.0.0', port=5010) 