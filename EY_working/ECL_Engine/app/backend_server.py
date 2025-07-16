# Standard library imports for file operations and date/time handling
import os
# Flask framework imports for web server functionality
from flask import Flask, request, jsonify
# CORS (Cross-Origin Resource Sharing) for handling requests from different domains
from flask_cors import CORS
# DateTime utilities for timestamp generation
from datetime import datetime

# Initialize Flask application instance
app = Flask(__name__)
# Enable CORS for all routes to allow cross-origin requests (useful for frontend integration)
CORS(app)

# Configuration: Base directory where uploaded files will be stored
# This path should be adjusted based on the deployment environment
BASE_UPLOAD_FOLDER = r'C:/Users/UV665AR/OneDrive - EY/3.CNCBI/File_upload'


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    File upload endpoint that handles POST requests for file uploads.

    This endpoint:
    1. Validates that a file is present in the request
    2. Extracts file type and user suffix from form data
    3. Generates unique folder and filename based on timestamp and parameters
    4. Creates organized folder structure for different file types
    5. Saves the uploaded file with proper naming convention

    Expected form data:
    - file: The actual file to upload
    - fileType: Type of file ('parameter' or 'dataCorrection')
    - suffix: Optional user-provided suffix for file naming

    Returns:
    - JSON response with success/error message and file details
    """

    # Check if 'file' key exists in the uploaded files
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    # Extract the uploaded file from the request
    file = request.files['file']
    # Get file type from form data (defaults to 'unknown' if not provided)
    file_type = request.form.get('fileType', 'unknown')
    # Get user-provided suffix for custom file naming (optional)
    user_suffix = request.form.get('suffix', '')

    # Validate that a file was actually selected (not just empty filename)
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Process the file if it exists
    if file:
        try:
            # Generate timestamp in format: YYYYMMDDHHMMSS for unique file naming
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # Extract original filename and file extension for preservation
            original_filename = file.filename
            # Get file extension (e.g., '.csv', '.xlsx') or empty string if no extension
            file_extension = os.path.splitext(original_filename)[
                1] if '.' in original_filename else ''

            # Generate folder name and filename based on file type and user suffix
            if file_type == 'parameter':
                # Parameter files get 'param_' prefix
                folder_name = f"param_{timestamp}_{user_suffix}" if user_suffix else f"param_{timestamp}"
                new_filename = f"param_{timestamp}_{user_suffix}{file_extension}" if user_suffix else f"param_{timestamp}{file_extension}"
            elif file_type == 'dataCorrection':
                # Data correction files get 'dc_' prefix
                folder_name = f"dc_{timestamp}_{user_suffix}" if user_suffix else f"dc_{timestamp}"
                new_filename = f"dc_{timestamp}_{user_suffix}{file_extension}" if user_suffix else f"dc_{timestamp}{file_extension}"
            else:
                # Fallback for unknown file types - use timestamp as folder and original filename
                folder_name = timestamp
                new_filename = original_filename

            # Create the full path for the new folder within the base upload directory
            new_upload_folder = os.path.join(BASE_UPLOAD_FOLDER, folder_name)

            # Create the folder structure if it doesn't exist (mkdir -p equivalent)
            os.makedirs(new_upload_folder, exist_ok=True)

            # Create the complete file path including the new filename
            file_path = os.path.join(new_upload_folder, new_filename)

            # Save the uploaded file to the specified path
            file.save(file_path)

            # Return success response with file details
            return jsonify({
                'message': f'File "{new_filename}" uploaded successfully',
                'path': file_path,  # Full path where file was saved
                'original_name': original_filename,  # Original filename from user
                'new_name': new_filename  # New filename with timestamp and prefix
            }), 200

        except Exception as e:
            # Handle any errors during file processing (e.g., permission issues, disk full)
            return jsonify({'error': f'Error saving file: {str(e)}'}), 500


@app.route('/test', methods=['GET'])
def test():
    """
    Simple test endpoint to verify the server is running and responding.

    This endpoint:
    1. Prints a message to console for debugging
    2. Returns current timestamp as JSON response

    Useful for:
    - Health checks
    - Verifying server connectivity
    - Testing basic API functionality

    Returns:
    - JSON response with current timestamp
    """
    import datetime
    # Print debug message to console/logs
    print("test endpoint was called")
    # Get current timestamp for response
    result = f"TIME:{datetime.datetime.now()}"
    return jsonify({'result': result})


# Main execution block - only runs when script is executed directly
if __name__ == '__main__':
    # Print startup messages to console
    print("Starting consolidated backend server...")
    print("Upload endpoint available at: http://localhost:5001/upload")
    print("Test endpoint available at: http://localhost:5001/test")

    # Start the Flask development server
    # debug=True enables debug mode with auto-reload and detailed error messages
    # port=5001 specifies the port number for the server
    app.run(debug=True, port=5001)
