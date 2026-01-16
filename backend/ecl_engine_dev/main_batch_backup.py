##############################################################################################
'''
CNCBI ECL Tool
'''
##############################################################################################
# Load packages

import warnings
from ecl_calc.modules.io_handler.data_transfer import DataTransfer
from ecl_calc.modules.io_handler.run_status_recorder import RunStatusRecorder
from ecl_calc.services import ecl_engine_service
from ecl_calc.services import post_run_sanity_check_service
from ecl_calc.services import pre_run_sanity_check_service
from ecl_calc.services import ecl_adjustment_service
from ecl_calc.modules.io_handler.output_handler import OutputHandler
from ecl_calc.modules.io_handler.parameter_loader import load_parameters
from ecl_calc.config.env_setting import run_setting
from data_merge.service.data_merge_service import run as data_merge_run
import pyodbc
import pandas as pd
import argparse as ap
import json
import time
import shutil
import glob
from pathlib import Path
from datetime import datetime
from utils.loggers import createLogHandler
from utils.schedule_run import check_and_exit_if_not_scheduled
from utils.email_notifier import init_notifier, get_notifier

# Check if today is a scheduled run day
check_and_exit_if_not_scheduled("batch_calendar.txt")


warnings.filterwarnings('ignore')


def main(run_config):
    # Start the timer
    start_time = time.time()
    c = run_config.copy()

    # Load environment context
    rc = run_setting(run_config=c)

    # Initialize logger
    logger = createLogHandler(
        'main', rc.outLogPath/'Log_file_main.log')
    logger.info('Starting ECL Engine Process...')
    logger.info(f'Run Mode: {rc.RUN_MODE}')

    # Initialize email notifier
    email_config = run_config.get('EMAIL_SETTING', {})
    init_notifier(email_config)
    notifier = get_notifier()
    data_yymm = run_config.get('RUN_SETTING', {}).get('DATA_YYMM', 'N/A')

    # Initialize run status recorder
    status_recorder = RunStatusRecorder(rc)

    # Get current timestamp for database record
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    # Insert initial running status record
    status_recorder.insert_status_record(
        maker="Batch Run",
        time=current_timestamp,
        settings="",
        action="Batch run",
        status="running",
        checker="",
        created_at=current_timestamp
    )

    try:
        ##############################################################################################
        '''
        Data Merge
        '''
        ##############################################################################################
        logger.info('Starting Data Merge...')
        merge_log_file = rc.outLogPath / 'Log_file_data_merge.log'

        # Send start notification
        if notifier:
            notifier.module_start("Data Merge Module", {
                "Reporting Date": data_yymm,
                "Run Mode": rc.RUN_MODE
            })

        # Run data merge service
        data_merge_run(
            run_config_path=args.configPath,
            merge_config_path='data_merge/config/merge_config.json',
            mode='convert_and_merge',
        )
        logger.info('Completed Data Merge')

        # Send success notification
        if notifier:
            notifier.data_merge_success(
                data_yymm=data_yymm,
                run_mode=rc.RUN_MODE,
                data_path=rc.inDataPath,
                log_files=[str(merge_log_file)
                           ] if merge_log_file.exists() else None
            )

        ##############################################################################################
        '''
        ECL Calculation
        '''
        ##############################################################################################

        # Load parameters
        param = load_parameters(paramPath=rc.paramPath)
        logger.info('\tParameters loaded successfully')

        # **********************************************************
        # Copy param and data to output folder
        # **********************************************************
        # # Get param files to output param folder
        # param_files = glob.glob(str(rc.paramPath / "*.xlsx"))
        # for file in param_files:
        #     shutil.copy2(file, rc.outParamPath)

        # # Copy data files to output data folder with timestamp
        # data_files = glob.glob(str(rc.inDataPath / "*.csv"))
        # for file in data_files:
        #     # Read the CSV file
        #     df = pd.read_csv(file, encoding='utf-8-sig')

        #     # Apply OutputHandler to process the DataFrame
        #     output_handler = OutputHandler(rc)
        #     df_processed = output_handler.process_general(df)

        #     # Save to output data folder with timestamp
        #     output_file = rc.outDataPath / Path(file).name
        #     df_processed.to_csv(output_file, index=False)
        #     print(f"Copied {Path(file).name} to output data folder with timestamp")

        # **********************************************************
        # ECL Adjustment - Deal Append (inclued in batch run)
        # **********************************************************
        logger.info('Starting ECL Adjustment - Deal Append...')
        ecl_adjustment_service.pre_run_deal_append(context=rc, param=param)
        logger.info('Completed ECL Adjustment - Deal Append')

        # **********************************************************
        # Pre-Run Data Sanity Check
        # **********************************************************
        logger.info('Starting Pre-Run Data Sanity Check...')
        pre_run_sanity_check_service.run_sanity_chk(context=rc)
        logger.info('Completed Pre-Run Data Sanity Check')

        # **********************************************************
        # ECL Calculation
        # **********************************************************
        logger.info('Starting ECL Calculation...')
        ecl_log_file = rc.outLogPath / 'Log_file_ecl_calculation.log'

        # Send start notification
        if notifier:
            notifier.module_start("ECL Calculation Module", {
                "Reporting Date": data_yymm,
                "Run Mode": rc.RUN_MODE,
                "Test Mode": rc.test_mode if hasattr(rc, 'test_mode') else 'N/A'
            })

        # 1. Run ECL engine and get all DataFrames
        result_dfs = ecl_engine_service.run_ecl_engine(
            context=rc, param=param)

        if result_dfs is not None:
            # unpack
            ead_df, pwa_ecl_detailed, pwa_ecl_by_deal = result_dfs
            logger.info('Completed ECL Calculation')
        else:
            logger.warning(
                'ECL Calculation completed but no data returned')

        logger.info('Starting Output Handle - ECL Results Export...')

        # 2. Output handle
        dataframes_to_export = [
            (ead_df, "interim_output_ead_schedule.csv"),
            (pwa_ecl_detailed, "interim_output_ecl_detailed.csv"),
            (pwa_ecl_by_deal, "interim_output_ecl_by_deal.csv"),
        ]

        for df, filename in dataframes_to_export:
            if df is not None and not df.empty:
                try:
                    # Apply OutputHandler to process the DataFrame
                    output_handler = OutputHandler(rc)
                    if filename == "interim_output_ecl_by_deal.csv":
                        df_processed = output_handler.process_all(
                            df, param)
                    else:
                        df_processed = output_handler.process_general(df)

                    # Export to CSV
                    output_path = rc.outInterimPath / filename
                    df_processed.to_csv(output_path, index=False)
                    logger.info(f"Exported {filename} with timestamp")

                except Exception as e:
                    logger.error(f"Error exporting {filename}: {str(e)}")
            else:
                logger.info(
                    f"Skipping {filename} - DataFrame is None or empty")

        # Send success notification
        if notifier:
            notifier.ecl_calculation_success(
                data_yymm=data_yymm,
                run_mode=rc.RUN_MODE,
                interim_path=rc.outInterimPath,
                log_files=[str(ecl_log_file)
                           ] if ecl_log_file.exists() else None
            )

        # **********************************************************
        # ECL Adjustment - 1. stage 3 adj; 2. ecl result adj
        # This mode must be run after ECL calculation
        # **********************************************************
        logger.info('Starting ECL Adjustment - Post-Run...')
        ecl_adjustment_service.post_run_stage_3_adj(
            context=rc, param=param)
        ecl_adjustment_service.post_run_output_adj(
            context=rc, param=param)
        logger.info('Completed ECL Adjustment - Post-Run')

        # **********************************************************
        # Post-Run Result Validation
        # **********************************************************
        logger.info('Starting Post-Run Result Validation...')
        post_run_sanity_check_service.run_post_sanity_chk(context=rc)
        logger.info('Completed Post-Run Result Validation')

        # **********************************************************
        # Data transfer to DB server
        # **********************************************************
        if rc.TO_DB == "ON":
            logger.info('Starting Output to ECL calc server...')
            # Initialize DataTransfer with config
            data_transfer = DataTransfer(context=rc)

            # Manual file paths - edit this list to specify which files to process
            files_to_process = [
                # Example file paths - modify these as needed:
                str(rc.outDataPath / "exposure_table.csv"),
                str(rc.outDataPath / "schedule_table.csv"),
                str(rc.outDataPath / "facility_table.csv"),
                str(rc.outDataPath / "collateral_table.csv"),
                str(rc.outInterimPath / "interim_output_ead_schedule.csv"),
                str(rc.outInterimPath / "interim_output_ecl_detailed.csv"),
                str(rc.outInterimPath / "interim_output_ecl_by_deal.csv")
            ]

            if not files_to_process:
                print(
                    "No files specified for processing. Edit the files_to_process list.")
                return

            print(f"\nProcessing {len(files_to_process)} files...")

            # Process each manually specified file
            for file_path_str in files_to_process:
                file_path = Path(file_path_str)
                print(f"\nProcessing file: {file_path}")

                if not file_path.exists():
                    print(f"Error: File not found - {file_path}")
                    continue

                # Generate table name from file name (remove extension and replace special chars)
                table_name = file_path.stem.replace(
                    '-', '_').replace(' ', '_')

                try:
                    # Create table first
                    print(f"Creating table: {table_name}")
                    table_created = data_transfer.create_table(
                        file_path, table_name)

                    if not table_created:
                        logger.warning(
                            f"Failed to create table {table_name}, table may already exist, proceeding with import")

                    # Import data to the table
                    print(f"Importing data to table: {table_name}")
                    import_success = data_transfer.import_data(
                        file_path, table_name)

                    if import_success:
                        logger.info(
                            f"Successfully processed {file_path.name} -> table: {table_name}")
                    else:
                        logger.error(
                            f"Failed to import data to table {table_name}")
                except Exception as e:
                    logger.error(
                        f"Error processing {file_path.name}: {str(e)}")
                    continue

            logger.info('Completed Output to ECL calc server')
        else:
            logger.info(
                'Skipping Output to ECL calc server (TO_DB is OFF)')

        # Update status to completed
        status_recorder.update_status_record(
            current_timestamp, "completed")
        logger.info('ECL Engine Process completed successfully')

    except Exception as e:
        # Update status to failed
        status_recorder.update_status_record(current_timestamp, "failed")
        logger.error(f"ECL Engine Process failed: {str(e)}")

        # Send failure notifications if notifier is available
        if notifier:
            notifier.data_merge_failure(
                error=e,
                config_path='data_merge/config/merge_config.json',
                mode='convert_and_merge',
                log_files=[str(rc.outLogPath / 'Log_file_main.log')]
            )

        raise


###########################################################
# Main Function
###########################################################
if __name__ == "__main__":
    parser = ap.ArgumentParser()
    parser.add_argument('--configPath', type=str)
    args = parser.parse_args()

    with open(Path(args.configPath), 'r') as fp:
        c = json.load(fp)

    main(run_config=c)
