#data_merge/data_merge_service.py

import argparse
import sys
import json
import os
from data_merge.core.dat_converter import run_converter
from data_merge.core.exposure_merge import DataMergeFramework
from data_merge.core.collateral_merge import LGDMergeFramework
from data_merge.core.schedule_merge import BSDataMergeFramework
from data_merge.core.facility_merge import FacDataMergeFramework

def run(run_config_path=None, merge_config_path=None, mode=None):
    if run_config_path is None or mode is None:
        parser = argparse.ArgumentParser(
            description="Data Processing Framework")
        parser.add_argument('--run_config', type=str, required=True,
                            help='Path to run configuration file')
        parser.add_argument('--merge_config', type=str, default='data_merge/config/merge_config.json',
                            help='Path to merge configuration file')
        parser.add_argument('--mode', type=str,
                            choices=['convert_only', 'merge_exposure', 'merge_collateral',
                                     'merge_schedule', 'merge_facility', 'merge_all', 'convert_and_merge'],
                            default='convert_and_merge',
                            help='Operation mode')
        args = parser.parse_args()
        run_config_path = args.run_config
        merge_config_path = args.merge_config
        mode = args.mode

    # Load run config to get details
    run_config_data = {}
    try:
        with open(run_config_path, 'r') as f:
            run_config_data = json.load(f)
    except Exception as e:
        return

    # Prepare merge start details
    reporting_date = str(run_config_data['RUN_SETTING']['DATA_YYMM'])
    used_files = []
    
    if mode in ['convert_only', 'convert_and_merge']:
        merge_settings = run_config_data.get('MERGE_SETTING', {})
        used_files.append("field_positions.json")
        parse_dir = merge_settings.get('PARSE_INPUT_DIR', 'input')
        if '{reporting_date}' in parse_dir:
            parse_dir = parse_dir.replace('{reporting_date}', reporting_date)
        used_files.append(f"{parse_dir}/*.dat")
    if mode in ['merge_exposure', 'merge_all', 'convert_and_merge']:
        used_files.append("exposure table merge input files")
    if mode in ['merge_collateral', 'merge_all', 'convert_and_merge']:
        used_files.append("collateral table merge input files")
    if mode in ['merge_schedule', 'merge_all', 'convert_and_merge']:
        used_files.append("schedule table merge input files")
    if mode in ['merge_facility', 'merge_all', 'convert_and_merge']:
        used_files.append("facility table merge input files")

    # Track all errors and results
    all_errors = []
    results = {}
    
    # Get output paths
    merge_output_dir = run_config_data['RUN_SETTING']['DATA_PATH']

    try:
        # Run converter if mode is convert_only or convert_and_merge
        if mode in ['convert_only', 'convert_and_merge']:
            convert_success, converter_errors = run_converter(run_config_path)

            if not convert_success:
                all_errors.extend(converter_errors)
                raise Exception("DAT conversion failed")
            else:
                merge_settings = run_config_data.get('MERGE_SETTING', {})
                parse_output_dir = merge_settings.get('PARSE_OUTPUT_DIR', 'N/A')
                if '{reporting_date}' in parse_output_dir:
                    parse_output_dir = parse_output_dir.replace('{reporting_date}', reporting_date)
                
                results["Data Conversion"] = {
                    'status': 'Passed',
                    'file': 'Converted .dat files to .csv',
                    'path': parse_output_dir
                }

        # Run exposure table merge
        if mode in ['merge_exposure', 'merge_all', 'convert_and_merge']:
            try:
                cust_merger = DataMergeFramework(run_config_path, merge_config_path)
                cust_merger.run()  # Call the run() method
                
                results["Exposure Table Merge"] = {
                    'status': 'Passed',
                    'file': 'exposure_table.csv',
                    'path': os.path.abspath(merge_output_dir)
                }
            except Exception as e:
                try:
                    nested_errors = json.loads(str(e))
                    if 'all_errors' in nested_errors:
                        all_errors.extend(nested_errors['all_errors'])
                    else:
                        all_errors.append({
                            'type': 'merge',
                            'file': 'Exposure Table Merge',
                            'message': str(e)
                        })
                except:
                    all_errors.append({
                        'type': 'merge',
                        'file': 'Exposure Table Merge',
                        'message': str(e)
                    })

                
                # Record failure
                results["Exposure Table Merge"] = {
                    'status': 'Failed',
                    'file': 'N/A',
                    'path': 'N/A'
                }

                error_details = {
                    'original_error': str(e),
                    'all_errors': all_errors,
                    'run_config': run_config_path,
                    'merge_config': merge_config_path,
                    'mode': mode
                }
                raise Exception(json.dumps(error_details))

        # Run collateral table merge
        if mode in ['merge_collateral', 'merge_all', 'convert_and_merge']:
            try:
                lgd_merger = LGDMergeFramework(run_config_path, merge_config_path)
                lgd_merger.run()  # Call the run() method
                
                results["Collateral Table Merge"] = {
                    'status': 'Passed',
                    'file': 'collateral_table.csv',
                    'path': os.path.abspath(merge_output_dir)
                }
            except Exception as e:
                try:
                    nested_errors = json.loads(str(e))
                    if 'all_errors' in nested_errors:
                        all_errors.extend(nested_errors['all_errors'])
                    else:
                        all_errors.append({
                            'type': 'merge',
                            'file': 'Collateral Table Merge',
                            'message': str(e)
                        })
                except:
                    all_errors.append({
                        'type': 'merge',
                        'file': 'Collateral Table Merge',
                        'message': str(e)
                    })

                
                # Record failure
                results["Collateral Table Merge"] = {
                    'status': 'Failed',
                    'file': 'N/A',
                    'path': 'N/A'
                }

                error_details = {
                    'original_error': str(e),
                    'all_errors': all_errors,
                    'run_config': run_config_path,
                    'merge_config': merge_config_path,
                    'mode': mode
                }
                raise Exception(json.dumps(error_details))

        # Run schedule table merge
        if mode in ['merge_schedule', 'merge_all', 'convert_and_merge']:
            try:
                bs_merger = BSDataMergeFramework(run_config_path, merge_config_path)
                bs_merger.run()  # Call the run() method
                
                results["Schedule Table Merge"] = {
                    'status': 'Passed',
                    'file': 'schedule_table.csv',
                    'path': os.path.abspath(merge_output_dir)
                }
            except Exception as e:
                try:
                    nested_errors = json.loads(str(e))
                    if 'all_errors' in nested_errors:
                        all_errors.extend(nested_errors['all_errors'])
                    else:
                        all_errors.append({
                            'type': 'merge',
                            'file': 'Schedule Table Merge',
                            'message': str(e)
                        })
                except:
                    all_errors.append({
                        'type': 'merge',
                        'file': 'Schedule Table Merge',
                        'message': str(e)
                    })

                
                # Record failure
                results["Schedule Table Merge"] = {
                    'status': 'Failed',
                    'file': 'N/A',
                    'path': 'N/A'
                }

                error_details = {
                    'original_error': str(e),
                    'all_errors': all_errors,
                    'run_config': run_config_path,
                    'merge_config': merge_config_path,
                    'mode': mode
                }
                raise Exception(json.dumps(error_details))

        # Run facility table merge
        if mode in ['merge_facility', 'merge_all', 'convert_and_merge']:
            try:
                fac_merger = FacDataMergeFramework(run_config_path, merge_config_path)
                fac_merger.run()  # Call the run() method
                
                results["Facility Table Merge"] = {
                    'status': 'Passed',
                    'file': 'facility_table.csv',
                    'path': os.path.abspath(merge_output_dir)
                }
            except Exception as e:
                try:
                    nested_errors = json.loads(str(e))
                    if 'all_errors' in nested_errors:
                        all_errors.extend(nested_errors['all_errors'])
                    else:
                        all_errors.append({
                            'type': 'merge',
                            'file': 'Facility Table Merge',
                            'message': str(e)
                        })
                except:
                    all_errors.append({
                        'type': 'merge',
                        'file': 'Facility Table Merge',
                        'message': str(e)
                    })
                
                
                # Record failure
                results["Facility Table Merge"] = {
                    'status': 'Failed',
                    'file': 'N/A',
                    'path': 'N/A'
                }
                
                error_details = {
                    'original_error': str(e),
                    'all_errors': all_errors,
                    'run_config': run_config_path,
                    'merge_config': merge_config_path,
                    'mode': mode
                }
                raise Exception(json.dumps(error_details))

    except Exception as e:
        # Create a custom exception with detailed error info
        error_details = {
            'original_error': str(e),
            'all_errors': all_errors,
            'run_config': run_config_path,
            'merge_config': merge_config_path,
            'mode': mode
        }
        # Re-raise with details
        raise Exception(json.dumps(error_details))