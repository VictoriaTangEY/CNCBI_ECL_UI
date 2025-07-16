##############################################################################################
'''
CNCBI ECL Tool
'''
##############################################################################################
# Load packages

import pandas as pd
import argparse as ap
import json
import time
import shutil
import glob
from pathlib import Path
from datetime import datetime
import pyodbc


from config.env_setting import run_setting
from modules.io_handler.parameter_loader import load_parameters
from services import ecl_adjustment_service
from services import pre_run_sanity_check_service
from services import ecl_engine_service
from utils.data_transfer import DataTransfer
from utils.loggers import createLogHandler
import warnings
warnings.filterwarnings('ignore')


##############################################################################################
# Main Process
##############################################################################################

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

    # test mode on/off
    if rc.test_mode == 'ON':
        logger.info('\tTEST MODE')
    else:
        logger.info('\tFULL SET MODE')

    # Load parameters
    try:
        # Load parameters
        param = load_parameters(paramPath=rc.paramPath)
        logger.info('\tParameters loaded successfully')

    except Exception as e:
        logger.exception("\tFailed to load parameters")
        raise

###########################################################
# ECL Adjustment - Deal Append
###########################################################
# TODO: add indicator(action override or overlay) col to the result file
    if (rc.RUN_MODE in [1, 3, 15]):
        ecl_adjustment_service.pre_run_deal_append(context=rc, param=param)


###########################################################
# Pre-Run Data Sanity Check
###########################################################
    # if (rc.RUN_MODE in [2.1, 3, 15]):
    #         pre_run_sanity_check_service.run_sanity_chk(context=rc)
    # if (rc.RUN_MODE in [2.2, 3, 15]):
    #     pre_run_sanity_check_service.run_sanity_chk(context=rc)

###########################################################
# ECL Calculation
###########################################################
    if (rc.RUN_MODE in [4, 5, 15]):
        # Run ECL engine and get EAD DataFrame
        ecl_engine_service.run_ecl_engine(
            context=rc, param=param)

###########################################################
# ECL Adjustment - 1. stage 3 adj; 2. ecl result adj
# This mode must be run after ECL calculation
###########################################################
    if (rc.RUN_MODE in [6, 5, 15]):
        ecl_adjustment_service.post_run_stage_3_adj(
            context=rc, param=param)
        ecl_adjustment_service.post_run_output_adj(
            context=rc, param=param)

###########################################################
# Post-Run Result Validation
# TODO: To be implemented
###########################################################
    if (rc.RUN_MODE in [6, 10, 15]):
        pass

###########################################################
# Reporting
# TODO: To be implemented
###########################################################
    if (rc.RUN_MODE in [6, 12, 15]):
        pass

###########################################################
# Output to ECL calc server
###########################################################

    # for testing
    if (rc.RUN_MODE in [99]):
        # copy the param and data used in the run to the output folder

        # Get param files to output param folder
        param_files = glob.glob(str(rc.paramPath / "*.xlsx"))
        for file in param_files:
            shutil.copy2(file, rc.outParamPath)

        # Copy data files to output data folder
        data_files = glob.glob(str(rc.inDataPath / "converted/*.csv"))
        for file in data_files:
            shutil.copy2(file, rc.outDataPath)

        if rc.TO_DB == "ON":
            # Initialize DataTransfer with config
            data_transfer = DataTransfer(context=rc)

            # Specify the file path directly
            data_file_path = rc.inDataPath / "converted/Cust_merged_data.csv"

            if not data_file_path.exists():
                print(f"Error: {data_file_path} not found")
                return

            # Create table
            data_transfer.create_table(data_file_path, "Cust_merged_data")

            # Import data to table
            data_transfer.import_data(data_file_path, "Cust_merged_data")


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
