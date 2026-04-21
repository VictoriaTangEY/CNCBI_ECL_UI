import os
import pandas as pd
import json
from typing import Tuple, List, Dict

def check_required_files(logger, data_dir, config, merge_type="cust") -> Tuple[Dict, List[Dict]]:
    """
    Check and load required files
    Returns: (files_dict, errors_list)
    """
    logger.info("=== Finding and loading input files ===")
    
    # Store loaded files
    files = {}
    
    # Track errors
    missing_files = []
    empty_columns_errors = []
    
    # Get regions from config
    regions = config["regions"]
    
    # Map merge_type to config keys
    file_check_map = {
        "cust": "file_checking_exposure",
        "lgd": "file_checking_collateral",
        "bs": "file_checking_schedule",
        "fac": "file_checking_facility"
    }
    
    skip_check_map = {
        "cust": "skip_empty_check_exposure",
        "lgd": "skip_empty_check_collateral",
        "bs": "skip_empty_check_schedule",
        "fac": "skip_empty_check_facility"
    }
    
    calc_columns_map = {
        "cust": "calculation_columns_exposure",
        "lgd": "calculation_columns_collateral",
        "bs": "calculation_columns_schedule",
        "fac": "calculation_columns_facility"
    }
    
    file_types_key = file_check_map[merge_type]
    file_types = config[file_types_key]
    file_patterns = config["product_name"]
    
    # Get skip empty check conditions
    skip_empty_check_key = skip_check_map[merge_type]
    skip_empty_check = config.get(skip_empty_check_key, {})
    
    # Get final required columns based on merge type
    final_required_columns = config.get(calc_columns_map[merge_type], [])
    
    # Store all file patterns to find
    file_patterns_list = []
    
    # Generate file paths for each file type
    for file_id in file_types:
        # Get the file pattern
        if file_id in file_patterns:
            pattern = file_patterns[file_id]
            
            # Check if file requires region replacement
            if "{region}" in pattern:
                for region in regions:
                    # Replace {region} with actual region
                    filename = pattern.replace("{region}", region)
                    key = f"{region}_{file_id}"
                    file_patterns_list.append((filename, key, file_id))
            else:
                # For global files (no region)
                key = file_id
                file_patterns_list.append((pattern, key, file_id))
    
    # Process each file pattern and load files
    for file_pattern, key, file_id in file_patterns_list:
        file_path = os.path.join(data_dir, file_pattern)
        
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                
                # Convert all column names to uppercase
                df.columns = [col.upper() for col in df.columns]
                
                # Check final required columns that exist in this file
                existing_final_cols = [col for col in final_required_columns if col in df.columns]
                if existing_final_cols:
                    # Check if these columns are completely empty
                    empty_cols = []
                    for col in existing_final_cols:
                        # Skip if this column is in skip_empty_check for this file
                        if file_id in skip_empty_check and col in skip_empty_check[file_id]:
                            continue
                        # Also check region-specific key
                        if key in skip_empty_check and col in skip_empty_check[key]:
                            continue
                        if df[col].isna().all() or (df[col].astype(str).str.strip() == '').all():
                            empty_cols.append(col)
                    
                    if empty_cols:
                        empty_columns_errors.append((file_path, empty_cols))
                        continue
                
                files[key] = df
                logger.info(f"Loaded {file_path}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {str(e)}")
                missing_files.append(file_path)
        else:
            logger.debug(f"File not found: {file_path}")
            missing_files.append(file_path)
    
    # Output all errors to logs
    has_errors = False
    
    if missing_files:
        has_errors = True
        logger.error(f"=== Missing Files ({len(missing_files)}) ===")
        for file_path in missing_files:
            logger.error(f"{file_path}")
    
    if empty_columns_errors:
        has_errors = True
        logger.error(f"=== Empty Columns ({len(empty_columns_errors)} files) ===")
        for file_path, cols in empty_columns_errors:
            logger.error(f"{file_path}: {cols}")
    
    if has_errors:    
        logger.error("=== Process failed due to file validation errors ===")
        all_errors = []
        
        for file_path in missing_files:
            all_errors.append({
                'type': 'file_check',
                'message': f'Missing File: {file_path}'
            })
        
        for file_path, cols in empty_columns_errors:
            all_errors.append({
                'type': 'file_check',
                'message': f'Empty Columns in {file_path}: {cols}'
            })
        
        error_details = {
            'original_error': f'File validation failed: {len(missing_files)} missing files, {len(empty_columns_errors)} empty column errors',
            'all_errors': all_errors,
            'config': config.get('config_name', 'unknown'),
            'mode': merge_type
        }
        raise Exception(json.dumps(error_details))

    logger.info(f"=== All required files found and loaded with valid columns ===")
    return files, []