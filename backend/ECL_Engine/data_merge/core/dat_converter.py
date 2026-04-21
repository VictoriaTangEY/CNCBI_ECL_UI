import os
import re
import json
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from utils.loggers import createLogHandler


class DatConverter:

    def __init__(self, run_config_path: str):
        # Load run config
        with open(run_config_path, 'r') as f:
            self.run_config = json.load(f)
        
        merge_settings = self.run_config.get('MERGE_SETTING', {})
        self.reporting_date = str(self.run_config['RUN_SETTING']['DATA_YYMM'])
        
        # Set paths from run config
        self.dat_input_dir = merge_settings.get('PARSE_INPUT_DIR', '')
        self.dat_output_dir = merge_settings.get('PARSE_OUTPUT_DIR', '')
        self.field_position_file = merge_settings.get('FIELD_POSITION_FILE', '')
        
        # Replace {reporting_date} in paths
        self.dat_input_dir = self.dat_input_dir.replace('{reporting_date}', self.reporting_date)
        self.dat_output_dir = self.dat_output_dir.replace('{reporting_date}', self.reporting_date)
        
        # Setup logger
        output_path = Path(self.run_config['RUN_SETTING']['OUTPUT_PATH'])
        data_yymm = self.run_config['RUN_SETTING']['DATA_YYMM']
        timestamp_date = datetime.now().strftime("%Y%m%d")
        log_path = output_path / f"{data_yymm}_{timestamp_date}" / '01_log'
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / 'Log_file_data_merge.log'
        self.logger = createLogHandler("DatConverter", str(log_file))
        
        os.makedirs(self.dat_output_dir, exist_ok=True)
        self.field_positions = self._load_field_positions()
        self.errors = []  # Add error collection
        
        # Load skip check configurations from merge_config
        merge_config_path = merge_settings.get('MERGE_CONFIG_PATH', 
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                        'config', 'merge_config.json'))
        try:
            with open(merge_config_path, 'r') as f:
                merge_config = json.load(f)
            self.skip_header_check = merge_config.get('skip_header_check_file', [])
            self.skip_footer_check = merge_config.get('skip_footer_check_file', [])
        except (IOError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not load merge_config for skip check settings: {str(e)}")
            self.skip_header_check = []
            self.skip_footer_check = []

    def _load_field_positions(self) -> Dict[str, List[Tuple[str, int, int]]]:
        """Load field position information from JSON file."""
        full_path = os.path.abspath(self.field_position_file)
        try:
            # Check if file exists and is readable
            if not os.path.exists(full_path):
                self.logger.error(
                    f"Field position file {full_path} does not exist")
                return {}
            if not os.access(full_path, os.R_OK):
                self.logger.error(
                    f"Field position file {full_path} is not readable")
                return {}
            with open(full_path, 'r') as f:
                field_positions = json.load(f)
                return field_positions
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load field positions: {str(e)}")
            return {}

    def _extract_info_from_filename(self, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract product and region from filename. Returns (product, region)."""
        # Special handling for deal_subtype and deal_type
        special_files = {
            "onesumx_deal_subtype.dat": "deal_subtype",
            "onesumx_deal_type.dat": "deal_type",
            "onesumx_tfi_type.dat": "tfi_type",
            "onesumx_tfi_subtype.dat": "tfi_subtype",
            "onesumx_prod_class.dat": "prod_class",
            "onesumx_product_list.dat": "product_list",
            "onesumx_profit_centre.dat": "profit_centre"
        }
        
        if filename in special_files:
            product = special_files[filename]
            self.logger.debug(
                f"Extracted special product: {product} from {filename}")
            return product, None

        # Standard pattern with region: onesumx_@region_@product.dat
        pattern_with_region = r'onesumx_([A-Za-z0-9]+)_(.+?)\.dat'
        match = re.match(pattern_with_region, filename)

        if match:
            region = match.group(1).upper()  # Convert region to uppercase
            product = match.group(2).strip()
            self.logger.debug(
                f"Extracted region: {region}, product: {product} from {filename}")
        else:
            # Pattern without region: onesumx_@product.dat
            pattern_without_region = r'onesumx_(.+?)\.dat'
            match = re.match(pattern_without_region, filename)

            if not match:
                self.logger.warning(
                    f"Filename {filename} does not match any expected pattern")
                return None, None

            product = match.group(1).strip()
            region = None
            self.logger.debug(
                f"Extracted product: {product} from {filename} (no region)")

        # Check if product is in field_positions (case-insensitive)
        if product in self.field_positions:
            return product, region

        # Try case-insensitive match
        for key in self.field_positions:
            if key.lower() == product.lower():
                self.logger.warning(
                    f"Found case-insensitive match for {product}: {key}")
                return key, region
        return None, region

    def _convert_dat_file(self, dat_file: str) -> bool:
        """Convert a single DAT file."""
        filename = os.path.basename(dat_file)

        # Extract product and region
        product, region = self._extract_info_from_filename(filename)
        region_prefix = f"{region} | " if region else ""

        # Log start of processing
        self.logger.info(
            f"{region_prefix}Started loading files for {filename} for COB {self.reporting_date}")

        header_matched = False
        footer_matched = False
        total_records = 0

        try:
            # Verify we have field positions for product
            if not product or product not in self.field_positions:
                self.logger.warning(
                    f"{region_prefix}No configuration found for product from filename {filename} - skipping")
                return True

            # Get output CSV filename
            csv_file = os.path.join(
                self.dat_output_dir, filename.replace('.dat', '.csv'))

            # Get and sort field positions
            field_positions = sorted(
                self.field_positions[product], key=lambda x: x[1])
            headers = [pos[0] for pos in field_positions]

            # Read DAT file
            with open(dat_file, 'r') as f:
                lines = f.readlines()

            # Filter data lines - skip first and last
            data_lines = []
            if len(lines) > 2:
                for temp_line in lines[1:-1]:
                    if temp_line.strip():
                        data_lines.append(temp_line)

            total_records = len(data_lines)

            # Check header date against first column dates
            skip_header = filename in self.skip_header_check
            if not skip_header and lines and len(lines) > 0:
                header_date = lines[0].strip().rstrip(
                    ';')  # Remove trailing semicolon

                # Extract unique dates from first column of data lines
                unique_dates = set()
                if data_lines and field_positions:
                    # Get first field position (assuming first column is date)
                    first_field = field_positions[0]
                    start_pos = first_field[1] - 1
                    length = first_field[2]

                    for line in data_lines:
                        if len(line) >= start_pos + length:
                            date_value = line[start_pos:start_pos +
                                            length].strip()
                            if date_value:
                                unique_dates.add(date_value)

                # Check if header date matches the unique date(s) in data
                if unique_dates:
                    if len(unique_dates) == 1 and header_date in unique_dates:
                        self.logger.info(
                            f"{region_prefix}Header date and data first column date MATCHED")
                        self.logger.info(
                            f"{region_prefix}value of header check: Y")
                        header_matched = True
                    else:
                        self.logger.info(
                            f"{region_prefix}Header date and data first column date NOT MATCHED")
                        self.logger.info(
                            f"{region_prefix}value of header check: N")
                        if len(unique_dates) > 1:
                            self.logger.info(
                                f"{region_prefix}Multiple dates found in data: {unique_dates}")
                else:
                    self.logger.info(
                        f"{region_prefix}No dates found in data first column")
                    self.logger.info(
                        f"{region_prefix}value of header check: N")
            elif skip_header:
                self.logger.info(
                    f"{region_prefix}Header check skipped for {filename} (file is empty)")
                self.logger.info(f"{region_prefix}value of header check: SKIP")
                header_matched = True  # Set to True when skipping
            else:
                # Empty file case
                self.logger.info(
                    f"{region_prefix}Header date and data first column date NOT MATCHED")
                self.logger.info(f"{region_prefix}value of header check: N")

            # Check footer row count (last line)
            skip_footer = filename in self.skip_footer_check
            if not skip_footer and len(lines) > 1:
                # Remove trailing semicolon
                footer_count = lines[-1].strip().rstrip(';')
                try:
                    # int() handles leading zeros automatically
                    expected_count = int(footer_count)

                    # Log footer from file
                    self.logger.info(
                        f"{region_prefix}Footer for {filename}: {footer_count}")

                    # Log loaded records - Modified to use filename directly
                    self.logger.info(
                        f"{region_prefix}Total no. of records loaded on {filename}: {total_records}")

                    if expected_count == total_records:
                        self.logger.info(
                            f"{region_prefix}value of footer check: Y")
                        footer_matched = True
                    else:
                        self.logger.info(
                            f"{region_prefix}Current processing footer and row count NOT MATCHED")
                        self.logger.info(
                            f"{region_prefix}value of footer check: N")
                except ValueError:
                    self.logger.info(
                        f"{region_prefix}Current processing footer and row count NOT MATCHED")
                    self.logger.info(
                        f"{region_prefix}value of footer check: N")
            elif skip_footer:
                self.logger.info(
                    f"{region_prefix}Footer check skipped for {filename} (file is empty)")
                self.logger.info(
                    f"{region_prefix}Total no. of records loaded on {filename}: {total_records}")
                self.logger.info(f"{region_prefix}value of footer check: SKIP")
                footer_matched = True  # Set to True when skipping
            else:
                # Not enough lines for footer
                self.logger.info(
                    f"{region_prefix}Footer for {filename}: N/A (insufficient lines)")
                # Modified to use filename directly
                self.logger.info(
                    f"{region_prefix}Total no. of records loaded on {filename}: {total_records}")
                self.logger.info(
                    f"{region_prefix}Current processing footer and row count NOT MATCHED")
                self.logger.info(f"{region_prefix}value of footer check: N")

            # Create CSV file - ALWAYS CREATE even if empty
            with open(csv_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)

                # Process each line
                for line_num, line in enumerate(data_lines, 2):
                    row = []

                    for field_name, start, length in field_positions:
                        # Convert positions to 0-based indexing
                        start_pos = start - 1
                        end_pos = start_pos + length

                        # Extract field value safely
                        if len(line) >= end_pos:
                            value = line[start_pos:end_pos].strip()
                        else:
                            value = line[start_pos:].strip() if len(
                                line) > start_pos else ""

                        row.append(value)

                    writer.writerow(row)

            # Log completion with appropriate status
            if not header_matched or not footer_matched:
                error_msg = []
                if not header_matched and filename not in self.skip_header_check:
                    error_msg.append("Header check failed")
                    self.errors.append({
                        'type': 'converter',
                        'file': filename,
                        'message': 'Header check failed'
                    })
                if not footer_matched and filename not in self.skip_footer_check:
                    error_msg.append(
                        "Current processing footer and row count NOT MATCHED")
                    self.errors.append({
                        'type': 'converter',
                        'file': filename,
                        'message': 'Footer check failed'
                    })
                if error_msg:  # Only log error if there are actual errors
                    self.logger.info(
                        f"{region_prefix}Finished with error: {'; '.join(error_msg)}")
                    return False
                else:
                    self.logger.info(
                        f"{region_prefix}Successfully finished converting file for {filename}")
                    return True
            else:
                self.logger.info(
                    f"{region_prefix}Successfully finished converting file for {filename}")
                return True

        except Exception as e:
            self.logger.error(f"{region_prefix}Finished with error: {str(e)}")
            self.errors.append({
                'type': 'converter',
                'file': filename,
                'message': str(e)
            })
            return False

    def convert_all_files(self) -> bool:
        """Convert all DAT files in the input directory that have configurations."""
        self.logger.info(
            f"=== Starting to convert DAT files from {self.dat_input_dir} ===")

        # Check if input directory exists
        if not os.path.exists(self.dat_input_dir):
            self.logger.error(
                f"Input directory {self.dat_input_dir} does not exist")
            return False

        # Get list of all DAT files
        all_dat_files = [f for f in os.listdir(
            self.dat_input_dir) if f.endswith('.dat')]

        if not all_dat_files:
            self.logger.warning(f"No DAT files found in {self.dat_input_dir}")
            return True

        # Extract products from available DAT files
        available_products = set()
        available_files_by_product = {}

        for dat_file in all_dat_files:
            product, _ = self._extract_info_from_filename(dat_file)
            if product:
                available_products.add(product)
                if product not in available_files_by_product:
                    available_files_by_product[product] = []
                available_files_by_product[product].append(dat_file)

        # Check which products from config are missing DAT files
        configured_products = set(self.field_positions.keys())
        missing_products = configured_products - available_products
        extra_products = available_products - configured_products

        if missing_products:
            for product in missing_products:
                self.logger.error(
                    f"Product {product} is needed but no corresponding DAT file found")
            return False

        # Process files that have configurations
        files_to_process = []
        for product in configured_products:
            if product in available_files_by_product:
                files_to_process.extend(available_files_by_product[product])

        self.logger.info(
            f"Found {len(files_to_process)} DAT files to process from field_positions.json")

        # Process each file
        success_count = 0
        for dat_file in files_to_process:
            if self._convert_dat_file(os.path.join(self.dat_input_dir, dat_file)):
                success_count += 1

        # Calculate failed files
        failed_count = len(files_to_process) - success_count

        if success_count == len(files_to_process):
            self.logger.info(
                f"=== All {success_count} configured DAT files processed successfully ===")
            return True
        else:
            self.logger.error(
                f"=== Processed {success_count} out of {len(files_to_process)} configured DAT files ===")
            self.logger.error(
                f"=== Failed to process {failed_count} files ===")
            return False


def run_converter(run_config_path: str) -> Tuple[bool, List[Dict]]:
    """Run the DAT converter with the specified run config file. Returns (success, errors)"""
    errors = []
    try:
        # Initialize and run converter
        converter = DatConverter(run_config_path)
        success = converter.convert_all_files()

        print(
            f"DAT conversion completed {'successfully' if success else 'with errors'}")
        if not success:
            print("Check logs for details.")

        return success, converter.errors

    except Exception as e:
        print(f"Error in converter: {str(e)}")
        errors.append({
            'type': 'converter',
            'file': 'Data Converter Module',
            'message': str(e)
        })
        return False, errors