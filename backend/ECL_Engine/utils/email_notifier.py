import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import List, Dict, Optional, Any

class EmailNotifier:
    """Email notifier for ECL Engine"""
    def __init__(self, email_config: Dict[str, Any] = None):
        """Initialize with email config from run_config"""
        if email_config:
            self.enabled = email_config.get('SEND_EMAIL', 'OFF').upper() == 'ON'
            self.smtp = {
                'smtp_server': email_config.get('SMTP_SERVER'),
                'smtp_port': email_config.get('SMTP_PORT'),
                'sender_email': email_config.get('SENDER_EMAIL'),
                'sender_password': email_config.get('SENDER_PASSWORD')
            }
            self.recipients = {
                'to': email_config.get('RECIPIENTS_TO', []),
                'cc': email_config.get('RECIPIENTS_CC', []),
                'bcc': email_config.get('RECIPIENTS_BCC', [])
            }
        else:
            self.enabled = False
            
    def send(self, subject: str, body: str, priority: str = "normal", files: List[str] = None) -> bool:
        """Send email with HTML body"""
        if not self.enabled:
            print(f"Email disabled - {subject}")
            return True
            
        try:
            # Create message
            msg = MIMEMultipart()
            msg['Subject'] = f"[ECL Calculation Engine] {subject}"
            msg['From'] = self.smtp['sender_email']
            msg['To'] = ', '.join(self.recipients['to'])
            if self.recipients.get('cc'):
                msg['Cc'] = ', '.join(self.recipients['cc'])
            # Priority
            if priority == "high":
                msg['X-Priority'] = '1'
            # HTML body
            html = f"""
<html>
<body style="font-family: Arial; margin: 20px;">
<div style="background: #f0f0f0; padding: 20px; border-radius: 5px;">
<h2 style="color: #333;">ECL Calculation Engine</h2>
<p>{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
</div>
<div style="padding: 20px;">
{body}
</div>
<hr>
<p style="color: #666; font-size: 12px;">Automated message - Do not reply</p>
</body>
</html>
            """
            msg.attach(MIMEText(html, 'html'))
            # Attachments
            if files:
                for f in files:
                    if os.path.exists(f) and os.path.getsize(f) < 10*1024*1024:  # 10MB limit
                        with open(f, 'rb') as file:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(file.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(f)}"')
                            msg.attach(part)
            # Send
            server = smtplib.SMTP(self.smtp['smtp_server'], self.smtp['smtp_port'])
            if self.smtp.get('sender_password'):
                server.starttls()
                server.login(self.smtp['sender_email'], self.smtp['sender_password'])
            all_recipients = self.recipients['to'] + self.recipients.get('cc', []) + self.recipients.get('bcc', [])
            server.send_message(msg, to_addrs=all_recipients)
            server.quit()
            print(f"✓ Email sent: {subject}")
            return True
        except Exception as e:
            print(f"✗ Email failed: {e}")
            return False
        
    def module_start(self, module_name: str, details: Dict = None) -> bool:
        """Send module start notification"""
        body = f"""
<h3 style="color: #3498db;"> {module_name} Started</h3>
        """
        if details:
            body += "<table style='border-collapse: collapse; width: 100%; font-size: 14px;'>"
            for k, v in details.items():
                if k == "Files" and isinstance(v, list):
                    body += f"<tr><td style='border: 1px solid #ddd; padding: 10px;'><b>{k}:</b></td>"
                    body += f"<td style='border: 1px solid #ddd; padding: 10px;'>"
                    if v:
                        body += "<ul style='margin: 5px 0;'>"
                        for file in v:
                            body += f"<li>{file}</li>"
                        body += "</ul>"
                    else:
                        body += "None"
                    body += "</td></tr>"
                else:
                    body += f"<tr><td style='border: 1px solid #ddd; padding: 10px;'><b>{k}:</b></td>"
                    body += f"<td style='border: 1px solid #ddd; padding: 10px;'>{v}</td></tr>"
            body += "</table>"
        return self.send(f"STARTED - {module_name}", body)
    
    def module_success(self, module_name: str, message: str = "", details: Dict = None, log_files: List[str] = None) -> bool:
        """Send module success notification"""
        body = f"""
<h3 style="color: #27ae60;"> {module_name} Completed Successfully</h3>
<p>{message or f'The {module_name} has completed successfully.'}</p>
        """
        if details:
            # Handle different detail formats
            if any(isinstance(v, dict) for v in details.values()):
                body += self._format_module_table(details)
            else:
                body += self._format_simple_table(details)
        return self.send(f"SUCCESS - {module_name}", body, files=log_files)
    
    def module_failure(self, module_name: str, error: Any, details: List[Dict] = None, log_files: List[str] = None) -> bool:
        """Send module failure notification"""
        body = f"""
<h3 style="color: #e74c3c;"> {module_name} Failed</h3>
        """
        
        # Handle error as exception or string
        if isinstance(error, Exception):
            body += f"""
<p><b>Error Type:</b> {type(error).__name__}<br>
<b>Error Message:</b> {str(error)}</p>
            """
        else:
            body += f"<p><b>Error:</b> {str(error)}</p>"
        return self.send(f"FAILURE - {module_name}", body, "high", files=log_files)
    
    def _format_module_table(self, details: Dict) -> str:
        """Format module details as table"""
        body = "<table style='border-collapse: collapse; width: 100%; font-size: 14px;'>"
        body += "<tr style='background-color: #f8f9fa;'>"
        body += "<th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Category</th>"
        body += "<th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Output File</th>"
        body += "<th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Output Path</th>"
        body += "</tr>"
        for module, info in details.items():
            if isinstance(info, dict):
                body += f"<tr>"
                body += f"<td style='border: 1px solid #ddd; padding: 10px;'><b>{module}</b></td>"
                body += f"<td style='border: 1px solid #ddd; padding: 10px;'>{info.get('file', 'N/A')}</td>"
                body += f"<td style='border: 1px solid #ddd; padding: 10px;'>{info.get('path', 'N/A')}</td>"
                body += f"</tr>"
        body += "</table>"
        return body
    
    def _format_simple_table(self, details: Dict) -> str:
        """Format simple key-value pairs as table"""
        body = "<table style='border-collapse: collapse; width: 100%; font-size: 14px;'>"
        for k, v in details.items():
            body += f"<tr><td style='border: 1px solid #ddd; padding: 10px;'><b>{k}</b></td>"
            body += f"<td style='border: 1px solid #ddd; padding: 10px;'>{v:,}</td></tr>" if isinstance(v, int) else f"<td style='border: 1px solid #ddd; padding: 10px;'>{v}</td></tr>"
        body += "</table>"
        return body

    def data_merge_success(self, data_yymm: str, run_mode: str, data_path: str, log_files: List[str] = None) -> bool:
        """Send data merge success notification with predefined format"""
        details = {
            "Exposure Table": {
                'file': 'exposure_table.csv',
                'path': str(data_path)
            },
            "Collateral Table": {
                'file': 'collateral_table.csv',
                'path': str(data_path)
            },
            "Schedule Table": {
                'file': 'schedule_table.csv',
                'path': str(data_path)
            },
            "Facility Table": {
                'file': 'facility_table.csv',
                'path': str(data_path)
            }
        }
        return self.module_success(
            "Data Merge Module",
            "Data merge completed successfully and supposed to generate following files. Please check the attached log for detailed messages.",
            details,
            log_files=log_files
        )

    def data_merge_failure(self, error: Exception, config_path: str = None, mode: str = None, log_files: List[str] = None) -> bool:
        """Send data merge failure notification with formatted error details"""
        error_msg = str(error)
        error_table = ""
        config_info = ""
        
        try:
            error_details = json.loads(str(error))
            error_msg = error_details.get('original_error', str(error))
            all_errors = error_details.get('all_errors', [])
            config_path = error_details.get('config', config_path or '')
            mode = error_details.get('mode', mode or '')
            
            if config_path or mode:
                config_info = f"<b>Config:</b> {config_path}<br><b>Mode:</b> {mode}<br><br>"
            
            if all_errors:
                error_table = self._build_data_merge_error_table(all_errors)
        except:
            pass
        
        full_error_msg = f"""Data merge failed, please check the Error Details for detailed messages.

    <p><b>Error Message:</b> Data merge failed<br>
    {config_info}</p>
    {error_table}"""
        
        return self.module_failure("Data Merge Module", full_error_msg, log_files=log_files)

    def ecl_calculation_success(self, data_yymm: str, run_mode: str, interim_path: str, log_files: List[str] = None) -> bool:
        """Send ECL calculation success notification"""
        details = {
            "EAD Schedule": {
                'file': 'interim_output_ead_schedule.csv',
                'path': str(interim_path)
            },
            "ECL Detailed": {
                'file': 'interim_output_ecl_detailed.csv',
                'path': str(interim_path)
            },
            "ECL by Deal": {
                'file': 'interim_output_ecl_by_deal.csv',
                'path': str(interim_path)
            }
        }
        return self.module_success(
            "ECL Calculation Module",
            "ECL calculation completed successfully and supposed to generate following files. Please check the attached log for detailed messages.",
            details,
            log_files=log_files
        )

    def ecl_calculation_failure(self, error: Exception, log_files: List[str] = None) -> bool:
        """Send ECL calculation failure notification"""
        error_table = f"""
    <b>Error Details</b>
    <table style='border-collapse: collapse; width: 100%; font-size: 14px; margin-top: 10px;'>
    <tr style='background-color: #f8f9fa;'>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Module</th>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Error Type</th>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Error Details</th>
    </tr>
    <tr>
    <td style='border: 1px solid #ddd; padding: 10px;'>ECL Engine</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{type(error).__name__}</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{str(error)}</td>
    </tr>
    </table>"""
        
        full_error_msg = f"""ECL calculation failed, please check the log for detailed messages.

    <p><b>Error Message:</b> ECL calculation failed</p>
    {error_table}"""
        
        return self.module_failure("ECL Calculation Module", full_error_msg, log_files=log_files)

    def reporting_success(self, data_yymm: str, run_mode: str, result_path: str, log_files: List[str] = None) -> bool:
        """Send reporting success notification"""
        details = {
            "Summary Report": {
                'file': 'reporting_ecl_result_summary.xlsx',
                'path': str(result_path)
            },
            "RMG Report": {
                'file': 'reporting_ecl_result_to_rmg.xlsx',
                'path': str(result_path)
            },
            "IMH Files": {
                'file': 'ecl_imh_basel_rwa_calc.dat, ecl_imh_basel_rwa_calc.ctl',
                'path': str(result_path)
            },
            "BU Reports": {
                'file': 'ecl_result_by_BU_*.xlsx (multiple files)',
                'path': str(result_path)
            }
        }
        return self.module_success(
            "Reporting Module",
            "Reporting completed successfully and supposed to generate following files. Please check the attached log for detailed messages.",
            details,
            log_files=log_files
        )

    def reporting_failure(self, error: Exception, log_files: List[str] = None) -> bool:
        """Send reporting failure notification"""
        error_table = f"""
    <b>Error Details</b>
    <table style='border-collapse: collapse; width: 100%; font-size: 14px; margin-top: 10px;'>
    <tr style='background-color: #f8f9fa;'>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Module</th>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Error Type</th>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Error Details</th>
    </tr>
    <tr>
    <td style='border: 1px solid #ddd; padding: 10px;'>Reporting Service</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{type(error).__name__}</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{str(error)}</td>
    </tr>
    </table>"""
        
        full_error_msg = f"""Reporting failed, please check the log for detailed messages.

    <p><b>Error Message:</b> Reporting failed</p>
    {error_table}"""
        
        return self.module_failure("Reporting Module", full_error_msg, log_files=log_files)

    def _build_data_merge_error_table(self, all_errors: List[Dict]) -> str:
        """Build HTML error table for data merge errors"""
        error_table = """
    <b>Error Details</b>
    <table style='border-collapse: collapse; width: 100%; font-size: 14px; margin-top: 10px;'>
    <tr style='background-color: #f8f9fa;'>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>File Name</th>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Error Type</th>
    <th style='border: 1px solid #ddd; padding: 10px; text-align: left;'>Error Details</th>
    </tr>"""
        
        for err in all_errors:
            error_type = err.get('type', 'unknown')
            
            if error_type == 'converter':
                file_name = err.get('file', 'Unknown')
                message = err.get('message', 'Unknown')
                error_table += f"""
    <tr>
    <td style='border: 1px solid #ddd; padding: 10px;'>{file_name}</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>Convert Error</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{message}</td>
    </tr>"""
            
            elif error_type == 'file_check':
                message = err.get('message', '')
                if 'Missing File:' in message:
                    file_path = message.replace('Missing File:', '').strip()
                    file_name = os.path.basename(file_path)
                    error_table += f"""
    <tr>
    <td style='border: 1px solid #ddd; padding: 10px;'>{file_name}</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>Missing File</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{file_path}</td>
    </tr>"""
                
                elif 'Empty Columns in' in message:
                    parts = message.split(': ')
                    if len(parts) == 2:
                        file_path = parts[0].replace('Empty Columns in', '').strip()
                        file_name = os.path.basename(file_path)
                        columns_str = parts[1].strip()
                        error_table += f"""
    <tr>
    <td style='border: 1px solid #ddd; padding: 10px;'>{file_name}</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>Empty Columns</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{columns_str}</td>
    </tr>"""
                    else:
                        error_table += f"""
    <tr>
    <td style='border: 1px solid #ddd; padding: 10px;'>Unknown</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>File Check Error</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{message}</td>
    </tr>"""
            
            else:
                file_name = err.get('file', 'Unknown')
                message = err.get('message', 'Unknown')
                error_table += f"""
    <tr>
    <td style='border: 1px solid #ddd; padding: 10px;'>{file_name}</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>Merge Error</td>
    <td style='border: 1px solid #ddd; padding: 10px;'>{message}</td>
    </tr>"""
        
        error_table += "</table>"
        return error_table


# Global instance management
_notifier = None

def init_notifier(email_config: Dict[str, Any]) -> EmailNotifier:
    """Initialize the global notifier with config"""
    global _notifier
    _notifier = EmailNotifier(email_config)
    return _notifier

def get_notifier() -> Optional[EmailNotifier]:
    """Get the global notifier instance"""
    return _notifier