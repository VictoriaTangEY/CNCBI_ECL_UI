# Load packages
import numpy as np
from pathlib import Path
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')


# setting up environment

class run_setting():
    def __init__(self, run_config):

        c = run_config.copy()

        # General run purpose
        self.data_yymm = c['RUN_SETTING']['DATA_YYMM']
        self.prev_yymm = c['RUN_SETTING']['PREV_YYMM']

        self.ecl_adj_mode = c['RUN_SETTING']['ECL_ADJ_MODE']

        # input data folder path
        self.inDataPath = Path(c['RUN_SETTING']['DATA_PATH'])

        # param folder path
        self.paramPath = Path(c['RUN_SETTING']['PARAM_PATH'])

        # output data folder path
        self.outputPath = Path(c['RUN_SETTING']['OUTPUT_PATH'])

        # Create output folder with or without timestamp based on TEST_MODE
        self.test_mode = c['RUN_SETTING']['TEST_MODE']
        self.test_deal_list = c['RUN_SETTING']['TEST_DEAL_LIST']
        self.timestamp_date = datetime.now().strftime("%Y%m%d")  # for testing purpose
        self.timestamp_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.outPath = self.outputPath / \
            f"{self.data_yymm}_{self.timestamp_date}"

        # if self.test_mode == 'ON':
        #     self.outPath = self.outputPath / \
        #         f"{self.data_yymm}_{self.timestamp_date}"
        # else:
        #     self.outPath = self.outputPath / \
        #         f"{self.data_yymm}_{self.timestamp_datetime}"
        # self.outPath.mkdir(parents=True, exist_ok=True)

        # Create subfolders
        self.outDataPath = self.outPath / '00_data'
        self.outParamPath = self.outPath / '00_param'
        self.outLogPath = self.outPath / '01_log'
        self.outInterimPath = self.outPath / '02_interim'
        self.outResultPath = self.outPath / '03_result'
        self.outReportPath = self.outPath / '04_report'

        # Create all subfolders
        for path in [self.outDataPath, self.outParamPath, self.outLogPath,
                     self.outInterimPath, self.outResultPath, self.outReportPath]:
            path.mkdir(parents=True, exist_ok=True)

        # other config setting
        # TODO: to be chked and updated
        self.RUN_MODE = c['RUN_SETTING']['RUN_MODE']
        self.SANITY_CHECK_MODE = c['RUN_SETTING']['SANITY_CHECK_MODE']
        self.TO_DB = c['RUN_SETTING']['TO_DB']

        # Database settings
        self.db_dsn = c['DB_SETTING']['DSN']
        self.db_name = c['DB_SETTING']['DB_NAME']
        self.db_username = c['DB_SETTING']['USERNAME']
        self.db_password = c['DB_SETTING']['PASSWORD']

        # self.PARAM_VERSION = c['RUN_SETTING']['PARAM_VERSION']
        # self.SCENARIO_VERSION = c['RUN_SETTING']['SCENARIO_VERSION']

        # For scenario generation
        self.extend_yr = c['SCENARIO_SETTING']['EXTEND_YR']

        # Remark: For wholesale, the length of MEF used are different with Retail.  Need to explore the possibility of combining it
        # self.extend_yr_ws = 10
        self.total_yr = c['SCENARIO_SETTING']['TOTAL_YR']

        self.inputDataExtScen = c['SCENARIO_SETTING']['INPUT_DATA_EXT']
        self.dataNameScen = f'scenarioRawData.{self.inputDataExtScen}'

        # For ECL Calculation
        self.run_option = ['Data check only']

        self.run_scope_input = c['RUN_SETTING']['RUN_SCOPE']
        self.run_scope = [x.upper() for x in self.run_scope_input]

        self.bond_valid_scope = [
            'CORP-SRUNSECUREDBOND', 'CORP-SUBORDINATEDBOND']
        self.loan_valid_scope = [
            'RETAIL', 'BUSINESS BANKING', 'CORP-SRUNSECUREDBANKLOAN']

        self.prtflo_scope_fa = [
            m for m in self.run_scope if m in self.bond_valid_scope]
        self.prtflo_scope_ln = [
            m for m in self.run_scope if m in self.loan_valid_scope]

        self.scenario_set = ['BASE', 'GOOD', 'BAD']

        # For Data Preprocessing
        self.dtype_tbl = {
            # DEBUG Comment-out, to check
            # 'date': np.datetime64,
            'date': 'datetime64[ns]',
            'str': str,
            'int': int,
            'float': np.float64,
            'bool': bool,
            'category': 'category',
        }
        self.days_in_year = c['CONSTANT']['days_in_year']
        self.days_in_month = c['CONSTANT']['days_in_month']

        self.inputDataExtECL = c['DATA_IO_SETTING']['INPUT_DATA_EXT']

        self.exposure_table_name = c['DATA_IO_SETTING']['EXPOSURE_TABLE_NAME']
        self.collateral_table_name = c['DATA_IO_SETTING']['COLLATERAL_TABLE_NAME']
        self.schedule_table_name = c['DATA_IO_SETTING']['SCHEDULE_TABLE_NAME']
        self.facility_table_name = c['DATA_IO_SETTING']['FACILITY_TABLE_NAME']

        # print(self.dataPath)
        # self.logPath = masterPath / 'log'
