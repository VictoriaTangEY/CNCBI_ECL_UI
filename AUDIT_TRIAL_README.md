# Audit Trial Implementation

## Overview

This document describes the implementation of the audit trial functionality for the ECL UI system. The audit trial tracks user activities and provides downloadable logs for administrative review.

## Features Implemented

### 1. User & Role Updates Logging
- **File**: `user_role_updates_log.txt`
- **Location**: `/u01/Apps/EY_working/ECL_UI_v0.1/AuditTrial/`
- **Operations Tracked**:
  - Add New User
  - Edit User
  - Add New Role
  - Edit Role
  - Add New Function
  - Edit Function
  - Edit Role-Function Mapping

### 2. Download Activity Logging
- **File**: `download_log.txt`
- **Location**: `/u01/Apps/EY_working/ECL_UI_v0.1/AuditTrial/`
- **Pages Tracked**:
  - Parameter page downloads
  - Run Management page downloads (log files)
  - Reporting page downloads (ECL reports)

### 3. ECL Result Confirmation Logging
- **File**: `ecl_result_confirmation_log.txt`
- **Location**: `/u01/Apps/EY_working/ECL_UI_v0.1/AuditTrial/`
- **Operations Tracked**:
  - User approval of ECL results in Run Management
  - Records timestamp and settings of approved records

### 4. Parameter Updates Logging
- **File**: `parameter_update_log.txt`
- **Location**: `/u01/Apps/EY_working/ECL_UI_v0.1/AuditTrial/`
- **Operations Tracked**:
  - Parameter file uploads
  - Adjustment file uploads
  - Parameter approval operations
  - Adjustment approval operations

## Backend Implementation

### Audit Logging Functions

#### `create_audit_trial_folder()`
Creates the AuditTrial directory if it doesn't exist.

#### `log_user_role_update(operation, user_name, page, details)`
Logs user and role management activities.

**Parameters**:
- `operation`: Type of operation (e.g., "Add New User", "Edit Role")
- `user_name`: Name of the user performing the operation
- `page`: Page where operation occurred (default: "Role Management")
- `details`: Additional details about the operation

#### `log_download_activity(user_name, page, file_path)`
Logs download activities from various pages.

**Parameters**:
- `user_name`: Name of the user performing the download
- `page`: Page where download occurred (e.g., "Parameter", "Run Management", "Reporting")
- `file_path`: Description of the downloaded file

#### `log_ecl_result_confirmation(user_name, timestamp, settings)`
Logs ECL result confirmation activities.

**Parameters**:
- `user_name`: Name of the user performing the confirmation
- `timestamp`: Timestamp of the approved record
- `settings`: Settings/configuration of the approved record

#### `log_parameter_update(user_name, operation_type, file_type, file_path)`
Logs parameter update activities.

**Parameters**:
- `user_name`: Name of the user performing the operation
- `operation_type`: Type of operation ("Upload" or "Approve")
- `file_type`: Type of file ("parameter" or "adjustment")
- `file_path`: Path to the uploaded/approved file

### API Endpoints

#### `GET /download_audit_log/<log_type>`
Downloads audit log files.

**Parameters**:
- `log_type`: Type of log to download (`user_role_updates`, `download_activity`, `ecl_result_confirmation`, or `parameter_updates`)
- `user_name`: User requesting the download (for audit trail)

**Response**: File download (text format)

#### `POST /confirm_ecl_result`
Confirms ECL result and logs the confirmation.

**Parameters**:
- `task_id`: Task ID of the ECL record
- `timestamp`: Timestamp of the record

**Response**: JSON confirmation message

## Frontend Implementation

### AuditTrial.vue
- Displays audit log download options for both Admin Logs and System Logs
- Implements download functionality for all audit logs
- Supports both Admin Logs and System Logs sections

### Updated Download Functions
All download functions in the following pages now pass user information for audit logging:
- **Parameter.vue**: Parameter file downloads
- **RunManagement.vue**: ECL log file downloads and ECL result confirmations
- **Reporting.vue**: ECL report downloads

## Log Format

### User & Role Updates Log
```
[2024-01-15 14:30:25] User: John Doe | Page: Role Management | Operation: Add New User | Details: Added new user: Jane Smith with role: Analyst
[2024-01-15 14:35:10] User: Admin User | Page: Role Management | Operation: Edit Role | Details: Updated role: Manager with status: Active
```

### Download Activity Log
```
[2024-01-15 14:30:25] User: John Doe | Page: Parameter | Download File: Parameter files from par_20240115143025
[2024-01-15 14:35:10] User: Admin User | Page: Reporting | Download File: ECL Monthly Report from /u01/Apps/EY_working/99_data/03_output_folder/20240115
```

### ECL Result Confirmation Log
```
[2024-01-15 14:30:25] User: Default | Page: Run Management | Operation: Approve Record | Timestamp: 20240115 | Settings: {"task_id": "task_123", "runMode": "3-5", "reportingDate": "2024-12-31"}
```

### Parameter Updates Log
```
[2024-01-15 14:30:25] User: Default | Page: Parameter | Operation: Upload | Type: parameter | File Path: /u01/Apps/EY_working/ECL_UI_v0.1/interim/par_20240115143025
[2024-01-15 14:35:10] User: Default | Page: Parameter | Operation: Approve | Type: adjustment | File Path: /u01/Apps/EY_working/ECL_UI_v0.1/interim/adj_20240115143510
```

## Database Integration

The audit logging is integrated with existing database operations:

### Role Management Functions Updated
- `save_user_record()`: Logs "Add New User" operations
- `update_user_record()`: Logs "Edit User" operations
- `save_role_record()`: Logs "Add New Role" operations
- `update_role_record()`: Logs "Edit Role" operations
- `save_function_record()`: Logs "Add New Function" operations
- `update_function_record()`: Logs "Edit Function" operations
- `update_role_function_record()`: Logs "Edit Role-Function" operations

### Download Endpoints Updated
- `/download_files/<record_id>`: Parameter downloads
- `/download_log_files/<task_id>`: ECL log downloads
- `/download_ecl_monthly_report`: ECL monthly report downloads
- `/download_ecl_summary_report`: ECL summary report downloads
- `/download_bu_excel_reports`: BU Excel report downloads

### Parameter Management Updated
- `/upload`: Parameter and adjustment file uploads
- `/update_approval_status`: Parameter and adjustment approvals

### ECL Management Updated
- `/confirm_ecl_result`: ECL result confirmations

## File Structure

```
/u01/Apps/EY_working/ECL_UI_v0.1/AuditTrial/
├── user_role_updates_log.txt        # User and role management activities
├── download_log.txt                 # Download activities
├── ecl_result_confirmation_log.txt  # ECL result confirmation activities
└── parameter_update_log.txt         # Parameter update activities
```

## Testing

Test scripts are provided to verify the implementation:

```bash
# Test Admin Logs functionality
python test_audit_logging.py

# Test System Logs functionality  
python test_system_logs.py
```

The test scripts check:
- Backend server connectivity
- Audit folder creation
- Log file existence
- Download functionality

## Usage

### For Administrators
1. Navigate to the Audit Trail page
2. Select "Admin Logs" tab for user/role management and download history
3. Select "System Logs" tab for ECL confirmations and parameter updates
4. Click "Download" on any log type to get the corresponding audit history

### For Developers
The audit logging is automatically triggered by:
- User management operations in Role Management
- Download operations in Parameter, Run Management, and Reporting pages
- Parameter upload and approval operations in Parameter page
- ECL result confirmation operations in Run Management page

## Configuration

### Audit Folder Path
The audit folder path is configured in the backend:
```python
audit_folder = r'/u01/Apps/EY_working/ECL_UI_v0.1/AuditTrial'
```

### User Information
Currently, user information is hardcoded as "Default" in the backend. In a production environment, this should be replaced with actual user authentication information.

## Security Considerations

1. **File Permissions**: Ensure the AuditTrial folder has appropriate read/write permissions
2. **User Authentication**: Implement proper user authentication to get real user names
3. **Log Rotation**: Consider implementing log rotation for large audit files
4. **Access Control**: Restrict access to audit logs to authorized administrators only

## Future Enhancements

1. **Real User Authentication**: Integrate with LDAP or other authentication systems
2. **Log Rotation**: Implement automatic log rotation to manage file sizes
3. **Advanced Filtering**: Add date range and user filtering to audit log downloads
4. **Real-time Monitoring**: Add real-time audit log monitoring capabilities
5. **Encryption**: Implement encryption for sensitive audit logs

## Troubleshooting

### Common Issues

1. **Audit folder not created**: Check file permissions and ensure the backend has write access
2. **Log files not generated**: Verify that the backend server is running and database connections are working
3. **Download failures**: Check network connectivity and ensure the backend server is accessible

### Debug Information

Enable debug logging in the backend to see detailed audit logging information:
```python
logger.setLevel(logging.DEBUG)
```

## Dependencies

- Flask (backend web framework)
- pyodbc (database connectivity)
- axios (frontend HTTP client)
- Vue.js (frontend framework) 