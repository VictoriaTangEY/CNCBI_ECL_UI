"""
data_preprocessor.py
-------------------
Unified data preprocessing utilities for loan data.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from pathlib import Path
from ._expected_life import OutdatedAdjustment, MissingAdjustment, ExpectedLifeCalculation
from ._stage_allocation import StageAllocation
from modules.ecl_adjustment.mid_run_adjustment import mid_run_adj


class DataPreprocessor:
    """
    Unified data preprocessing class that handles data loading, standardization,
    currency conversion, and scope filtering.
    """

    def __init__(self, context):
        """
        Initialize the DataPreprocessor with context parameters.
        """
        # TODO: update the context
        # Paths
        self.inDataPath = context.inDataPath
        self.outInterimPath = context.outInterimPath
        self.inputDataExtECL = context.inputDataExtECL
        self.dtype_tbl = context.dtype_tbl
        self.test_mode = context.test_mode
        self.test_deal_list = context.test_deal_list
        # Table names
        self.exposure_table_name = context.exposure_table_name
        self.collateral_table_name = context.collateral_table_name
        self.schedule_table_name = context.schedule_table_name
        self.facility_table_name = context.facility_table_name

    def run(self, context, param):
        """Main data preprocessing pipeline"""

        print('\tProcessing Exposure Table...')
        expo_df, expo_df_stage_3 = self._process_exposure_table(context, param)

        print('\tProcessing Schedule Table...')
        sched_df = self._process_schedule_table(param, expo_df)

        print('\tProcessing Collateral Table...')
        coll_df = self._process_collateral_table(param, expo_df)

        print('\tProcessing Facility Table...')
        fac_df, fac_df_stage_3 = self._process_facility_table(param, expo_df)

        print('\tON/OFF separation...')
        expo_df, off_df_deal = self.expo_on_off(expo_df)
        off_df_fac = self.fac_on_off(fac_df)

        print('\tExporting results...')
        self._export_results(expo_df, expo_df_stage_3, coll_df,
                             sched_df, fac_df, fac_df_stage_3, off_df_deal, off_df_fac)

        return expo_df, expo_df_stage_3, coll_df, sched_df, fac_df, fac_df_stage_3, off_df_deal, off_df_fac

    def _process_exposure_table(self, context, param):
        """Process exposure table with all business logic"""
        expo_df = self.load_data(
            param, self.inDataPath, self.exposure_table_name, self.inputDataExtECL)

        if 'ADJ_IND' not in expo_df.columns:
            expo_df['ADJ_IND'] = 'N'

        expo_df_append = self.load_data(
            param, self.inDataPath, f'{self.exposure_table_name}_append', self.inputDataExtECL)
        if not expo_df_append.empty:
            if 'ADJ_IND' not in expo_df_append.columns:
                expo_df_append['ADJ_IND'] = 'Append'
            expo_df = pd.concat([expo_df, expo_df_append], ignore_index=True)

        if self.test_mode == 'ON' and self.test_deal_list:
            expo_df = self.filter_test_data(expo_df, 'exposure')

        expo_df = self.standardize_data(
            expo_df, param, 'exposure_table', self.dtype_tbl)
        expo_df = self.data_curr_conversion(expo_df, amount_cols=['ccy_amount', 'cur_bal', 'drawn_amount', 'int_accr',
                                                                  'int_susp_amt', 'pmt_amt', 'prin_amt', 'undrawn_amount'])
        expo_df = self.amrt_type_cd_standardize(expo_df)

        expo_df = self.scope_define(expo_df)
        expo_df = self.segmentation(expo_df, param, 'deal_id')
        expo_df, expo_df_stage_3 = self.stage_allocation(expo_df, param)

        if context.ecl_adj_mode == "ON":
            expo_df = mid_run_adj(context, param, expo_df,
                                  'exposure_table_staged')

        expo_df = self.expected_life_calculation(expo_df, param)
        expo_df = self.eir_calculation(expo_df, param)
        expo_df = self.patch_expo(expo_df)
        expo_df = self.expo_add_cols(param, expo_df)

        return expo_df, expo_df_stage_3

    def _process_schedule_table(self, param, expo_df):
        """Process schedule table"""
        sched_df = self.load_data(
            param, self.inDataPath, self.schedule_table_name, self.inputDataExtECL)

        if self.test_mode == 'ON' and self.test_deal_list:
            sched_df = self.filter_test_data(sched_df, 'schedule')

        if not sched_df.empty:
            sched_df = self.standardize_data(
                sched_df, param, 'schedule_table', self.dtype_tbl)
            sched_df = self._sched_curr_conversion(
                sched_df, expo_df, amount_cols=['instl_flat_amt'])

        return sched_df

    def _process_collateral_table(self, param, expo_df):
        """Process collateral table"""
        coll_df = self.load_data(
            param, self.inDataPath, self.collateral_table_name, self.inputDataExtECL)

        if self.test_mode == 'ON' and self.test_deal_list:
            coll_df = self.filter_test_data(coll_df, 'collateral', expo_df)

        if not coll_df.empty:
            coll_df = self.standardize_data(
                coll_df, param, 'collateral_table', self.dtype_tbl)
            coll_df = self.data_curr_conversion(
                coll_df, amount_cols=['collateral_amount'])

        return coll_df

    def _process_facility_table(self, param, expo_df):
        """Process facility table"""
        fac_df = self.load_data(
            param, self.inDataPath, self.facility_table_name, self.inputDataExtECL)

        if self.test_mode == 'ON' and self.test_deal_list:
            fac_df = self.filter_test_data(fac_df, 'facility', expo_df)

        if not fac_df.empty:
            fac_df = self.standardize_data(
                fac_df, param, 'facility_table', self.dtype_tbl)
            fac_df = self.data_curr_conversion(
                fac_df, amount_cols=['ccy_amount', 'drawn_amount', 'undrawn_amount'])
            fac_df = self.segmentation(fac_df, param, 'facility_nr')
            # Only use stage 1&2 for facility
            fac_df, fac_df_stage_3 = self.stage_allocation(fac_df, param)
            # # TODO: updae the fake logic to real logic
            fac_df = self.expected_life_calculation_fac(fac_df, param)
            fac_df['maturity_date_final'].fillna(
                pd.to_datetime('2026-12-31'), inplace=True)

        return fac_df, fac_df_stage_3

    def _export_results(self, expo_df, expo_df_stage_3, coll_df, sched_df, fac_df, fac_df_stage_3, off_df_deal, off_df_fac):
        """Export all processed results"""
        coll_df.to_csv(self.outInterimPath / "collateral.csv", index=False)
        sched_df.to_csv(self.outInterimPath / "schedule.csv", index=False)
        fac_df.to_csv(self.outInterimPath / "facility.csv", index=False)
        expo_df.to_csv(self.outInterimPath / "exposure.csv", index=False)
        expo_df_stage_3.to_csv(self.outInterimPath /
                               "exposure_stage3.csv", index=False)
        fac_df_stage_3.to_csv(self.outInterimPath /
                              "facility_stage3.csv", index=False)
        off_df_deal.to_csv(self.outInterimPath /
                           "exposure_off_deal.csv", index=False)
        off_df_fac.to_csv(self.outInterimPath /
                          "exposure_off_fac.csv", index=False)

    def _vectorize_decorator(self, func):
        """Vectorize a function for numpy operations."""
        return np.vectorize(func)

    def load_data(self,
                  param_dict: Dict[str, pd.DataFrame],
                  inDataPath: Path,
                  rawDataName: str,
                  inputDataExt: str) -> pd.DataFrame:
        """
        Load raw data from CSV file based on parameter configuration.

        Parameters:
        - param_dict: Dictionary containing parameter configurations
        - inDataPath: Path to input data directory
        - rawDataName: Name of the raw data file (without extension)
        - inputDataExt: File extension

        Returns:
        - pd.DataFrame: Raw loaded data
        """
        param = param_dict.copy()

        # Get column configuration from parameters
        if rawDataName == 'exposure_table' or rawDataName == 'exposure_table_append':
            rawKeepList = param['exposure_table_param'].query("keep_ind == 'Y'")[
                'colname'].to_list()
            str_list = param['exposure_table_param'].query("data_type == 'str' and keep_ind == 'Y'")[
                'colname'].to_list()
        else:
            rawKeepList = param[f'{rawDataName}_param'].query("keep_ind == 'Y'")[
                'colname'].to_list()
            str_list = param[f'{rawDataName}_param'].query("data_type == 'str' and keep_ind == 'Y'")[
                'colname'].to_list()

        # Create data type mappings
        init_dtype_mapping = {}
        for var in str_list:
            init_dtype_mapping[var] = str

        try:
            df = pd.read_csv(f'{inDataPath}/{rawDataName}.{inputDataExt}',
                             usecols=rawKeepList,
                             dtype=init_dtype_mapping,
                             encoding='utf-8-sig')
            # Sort columns according to rawKeepList order
            df = df[rawKeepList]
            return df

        except FileNotFoundError:
            if rawDataName == 'exposure_table_append':
                print("\t\tNo deals to append. Skipping...")
                return pd.DataFrame()
            else:
                print(
                    f"\t\tFile not found: {inDataPath}/{rawDataName}.{inputDataExt}")
                print(
                    "\t\tPlease check if the input file name, location and file extension is correct.")
                return pd.DataFrame()

        except PermissionError:
            print(
                f"\t\tPermission error: {inDataPath}/{rawDataName}.{inputDataExt}")
            print("\t\tPlease check if the file is being opened by another user.")
            return pd.DataFrame()

        except Exception as e:
            print(f"\t\tError loading {rawDataName}: {e}")
            return pd.DataFrame()

    def filter_test_data(self, df: pd.DataFrame, table_name: str, expo_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        Filter data based on test list using table-specific logic.

        Parameters:
        - df: Input DataFrame
        - table_name: Name of the table to filter ('exposure', 'schedule', 'collateral', 'facility')
        - expo_df: Exposure DataFrame (required for collateral and facility tables)

        Returns:
        - pd.DataFrame: Filtered DataFrame (empty if no matches found)
        """
        if df.empty:
            return df

        if table_name == 'exposure':
            # Filter by deal_id
            filtered_df = df[df['DEAL_ID'].isin(self.test_deal_list)]
            if filtered_df.empty:
                print(
                    f"\t\tTest mode: No exposure data found for test IDs {self.test_deal_list}")
            else:
                print(
                    f"\t\tTest mode: Filtered exposure table to {len(filtered_df)} rows for test IDs {self.test_deal_list}")

        elif table_name == 'schedule':
            # Filter by acct_id
            filtered_df = df[df['ACCT_ID'].isin(self.test_deal_list)]
            if filtered_df.empty:
                print(
                    f"\t\tTest mode: No schedule data found for test IDs {self.test_deal_list}")
            else:
                print(
                    f"\t\tTest mode: Filtered schedule table to {len(filtered_df)} rows for test IDs {self.test_deal_list}")

        elif table_name in ['collateral', 'facility']:
            # Filter by facility_nr (requires expo_df)
            if expo_df is None:
                print(
                    f"\t\tError: expo_df is required for filtering {table_name} table")
                return df

            test_fac_nr_list = expo_df[expo_df['deal_id'].isin(
                self.test_deal_list)]['facility_nr'].to_list()
            filtered_df = df[df['FACILITY_NR'].isin(test_fac_nr_list)]
            if filtered_df.empty:
                print(
                    f"\t\tTest mode: No {table_name} data found for test IDs {self.test_deal_list}")
            else:
                print(
                    f"\t\tTest mode: Filtered {table_name} table to {len(filtered_df)} rows for test IDs {self.test_deal_list}")

        else:
            print(
                f"\t\tWarning: Unknown table_name '{table_name}'. No filtering applied.")
            return df

        return filtered_df

    def filter_expo_test_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter exposure data based on test list.

        Parameters:
        - df: Input DataFrame

        Returns:
        - pd.DataFrame: Filtered DataFrame (empty if no matches found)
        """
        return self.filter_test_data(df, 'exposure')

    def filter_sched_test_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter schedule data based on test list.

        Parameters:
        - df: Input DataFrame

        Returns:
        - pd.DataFrame: Filtered DataFrame (empty if no matches found)
        """
        return self.filter_test_data(df, 'schedule')

    def filter_coll_and_fac_test_data(self, df: pd.DataFrame, expo_df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter collateral data based on test list.

        Parameters:
        - df: Input DataFrame
        - expo_df: Exposure DataFrame

        Returns:
        - pd.DataFrame: Filtered DataFrame (empty if no matches found)
        """
        return self.filter_test_data(df, 'collateral', expo_df)

    def standardize_data(self,
                         df: pd.DataFrame,
                         param_dict: Dict[str, pd.DataFrame],
                         rawDataName: str,
                         dtype_tbl: Dict[str, type]) -> pd.DataFrame:
        """
        Standardize data by applying data type conversions and column renaming.

        Parameters:
        - df: Input DataFrame
        - param_dict: Dictionary containing parameter configurations
        - rawDataName: Name of the raw data table
        - dtype_tbl: Data type mapping table

        Returns:
        - pd.DataFrame: Standardized DataFrame
        """
        if df.empty:
            return df

        param = param_dict.copy()

        # Get column configuration from parameters
        rawKeepList = param[f'{rawDataName}_param'].query("keep_ind == 'Y'")[
            'colname'].to_list()
        dtypeList = param[f'{rawDataName}_param'].query("keep_ind == 'Y'")[
            'data_type'].to_list()

        # Add programmatically added columns that aren't in parameter file
        if rawDataName == 'exposure_table' and 'ADJ_IND' in df.columns:
            rawKeepList.append('ADJ_IND')
            dtypeList.append('str')  # Add corresponding data type

        # Create mappings
        dtype_mapping = {}

        for var, dtype in zip(rawKeepList, dtypeList):
            dtype_mapping[var] = dtype_tbl[dtype]

        # Date parsing function
        def try_parse_date(series):
            # Try the most common formats in your data
            for fmt in ["%d%b%Y:%H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%Y%m%d"]:
                try:
                    parsed = pd.to_datetime(
                        series, format=fmt, errors='coerce')
                    # If at least some values were parsed, use this format
                    if parsed.notna().sum() > 0:
                        return parsed
                except Exception:
                    continue
            # Fallback: let pandas try to infer
            return pd.to_datetime(series, errors='coerce')

        # Type Casting
        for key, val in dtype_mapping.items():
            try:
                if val == 'datetime64' or val == 'datetime64[ns]':
                    df[key] = try_parse_date(df[key])
                elif val == 'float':
                    df[key] = pd.to_numeric(df[key], errors='coerce')
                elif val == 'int' or val == int or val == 'Int64':
                    # Use pandas nullable Int64 type to allow NA
                    df[key] = pd.to_numeric(
                        df[key], errors='coerce').astype('Int64')
                elif val == 'str' or val == str:
                    df[key] = df[key].fillna('').astype(str)
                else:
                    # fallback: try astype, but catch errors
                    df[key] = df[key].astype(val)
            except Exception as e:
                print(f'Report error on data casting for {key} to type {val}.')
                print(e)
                # Instead of returning empty, keep the column as object and continue
                df[key] = df[key].astype('object')
                continue

        # Convert column names to lowercase
        df.columns = df.columns.str.lower()

        return df

    def data_curr_conversion(self,
                             table: pd.DataFrame,
                             amount_cols: List[str]) -> pd.DataFrame:
        """
        Standardize all relevant currency columns to HKE.
        """
        # Check if required currency columns exist in the table
        required_currency_cols = ['rate', 'multiply_divide_ind', 'lcy_to_hkd']
        missing_cols = [
            col for col in required_currency_cols if col not in table.columns]

        if missing_cols:
            print(
                f"\t\tWarning: Missing currency columns in exposure data: {missing_cols}")
            print(f"\t\tSkipping currency standardization for exposure data")
            # Return the original table without currency conversion
            return table

        return self._curr_conversion(table, amount_cols)

    def _sched_curr_conversion(self,
                               table: pd.DataFrame,
                               expo_df: pd.DataFrame,
                               amount_cols: List[str]) -> pd.DataFrame:
        """
        Standardize all relevant currency columns to HKE.
        Map the rate and multiply_divide_ind in expo_df to the table:
        - if table == sched_df, map using the deal_id of expo_df and acct_id of sched_df
        """
        # Check if required currency columns exist in expo_df
        required_currency_cols = ['deal_id', 'rate',
                                  'multiply_divide_ind', 'lcy_to_hkd']
        missing_cols = [
            col for col in required_currency_cols if col not in expo_df.columns]

        if missing_cols:
            print(
                f"\t\tWarning: Missing currency columns in exposure data: {missing_cols}")
            print(f"\t\tSkipping currency standardization for schedule data")
            # Return the original table without currency conversion
            return table

        df = pd.merge(table, expo_df[[
                      'deal_id', 'rate', 'multiply_divide_ind', 'lcy_to_hkd']], left_on='acct_id', right_on='deal_id', how='left')
        df = self._curr_conversion(df, amount_cols)
        return df

    def _curr_conversion(self,
                         table: pd.DataFrame,
                         amount_cols: List[str]) -> pd.DataFrame:
        """
        Standardize all relevant currency columns to HKE using vectorized operations.
        """
        df = table.copy()

        for col in amount_cols:
            if col in df.columns:
                # Vectorized conversion
                mask = pd.notna(df[col])
                lcy_values = np.where(
                    df.loc[mask, 'multiply_divide_ind'] == 'M',
                    df.loc[mask, col] * df.loc[mask, 'rate'],
                    df.loc[mask, col] / df.loc[mask, 'rate']
                )
                df.loc[mask, f"{col}_hke"] = lcy_values * \
                    df.loc[mask, 'lcy_to_hkd']

        return df

    # @staticmethod
    # def _convert_to_lcy(value: float, ex_rate: float, action: str) -> float:
    #     """Convert a value based on exchange rate and action type."""
    #     if action == 'M':
    #         return value * ex_rate
    #     else:
    #         return value / ex_rate

    def scope_define(self,
                     table: pd.DataFrame) -> pd.DataFrame:
        """
        Filter the expo table to only keep rows where INT_ACCR + PRIN_AMT != 0.
        """
        df = table.copy()
        required_cols = ['int_accr', 'prin_amt']
        for col in required_cols:
            if col not in df.columns:
                print(
                    f"Warning: Required column '{col}' not found in DataFrame. Skipping scope filter.")
                return df

        mask = (df['int_accr'] + df['prin_amt']) != 0
        df = df[mask].copy()
        df.reset_index(drop=True, inplace=True)
        return df

    def amrt_type_cd_standardize(self,
                                 table: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize the AMRT_TYPE_CD column.
        """
        df = table.copy()
        # Count NA values in AMRT_TYPE_CD column
        empty_count = (df['amrt_type_cd'] == '').sum()
        # print(f"Number of empty values in AMRT_TYPE_CD: {empty_count}")
        df['amrt_type_cd'] = df['amrt_type_cd'].replace('', '9999')

        # Convert to int then back to str to remove decimals
        df['amrt_type_cd'] = df['amrt_type_cd'].astype(
            float).astype(int).astype(str)

        # chk the unique values in AMRT_TYPE_CD column
        unique_values = df['amrt_type_cd'].unique()
        print(f"\t\tUnique values in AMRT_TYPE_CD: {unique_values}")
        return df

    def segmentation(self, df, param, key):
        """
        Apply segmentation logic to the exposure DataFrame.

        Parameters:
        - expo_df (pd.DataFrame): Exposure DataFrame
        - param (Dict): Parameter dictionary containing segmentation mapping

        Returns:
        - pd.DataFrame: DataFrame with segmentation applied
        """
        # Create segmentation mapping DataFrame
        seg_map_param = pd.DataFrame(param['segmentation_mapping_param'])

        # Define data columns mapping
        data_cols = {
            'seg_id': 'pit_pd_seg'
        }

        # Only keep segment and sub_segment in seg_map_param
        seg_map_subset = seg_map_param[
            [data_cols['seg_id'], 'segment', 'sub_segment']
        ]

        # Merge with segmentation mapping
        df = pd.merge(
            df,
            seg_map_subset,
            left_on=data_cols['seg_id'],
            right_on=data_cols['seg_id'],
            how='left'
        )

        # Further segment unsecured portfolio
        df['sub_segment'] = np.where(
            df['sub_segment'] == 'Unsecured',
            np.where(df[key].str.contains('CARDLINK', case=False, na=False),
                     'unsecured_cc', 'unsecured_ot'),
            df['sub_segment']
        )

        return df

    def stage_allocation(self, expo_df, param):
        """
        Apply stage allocation logic to the exposure DataFrame.

        Parameters:
        - expo_df (pd.DataFrame): Exposure DataFrame
        - param (Dict): Parameter dictionary containing stage allocation parameters

        Returns:
        - Tuple[pd.DataFrame, pd.DataFrame]: (stage_1_2_df, stage_3_df)
        """
        stage_allocator = StageAllocation()
        return stage_allocator.apply_stage_allocation(expo_df, param)

    # The following methods were moved to _stage_allocation.py:
    # _standardize_ratings
    # _apply_notchdown_criteria
    # _apply_rating_criteria
    # _apply_loan_class_criteria
    # _apply_dpd_criteria
    # _determine_final_stage

    def expected_life_calculation(self, expo_df, param):
        """
        Apply expected life calculation logic to the exposure DataFrame.

        Parameters:
        - expo_df (pd.DataFrame): Exposure DataFrame
        - param (Dict): Parameter dictionary containing lifetime parameters

        Returns:
        - pd.DataFrame: DataFrame with expected life calculations applied
        """
        # Prepare lifetime parameters
        lifetime_adjustment_param = param['lifetime_param']
        lifetime_adjustment_param['lifetime_val_std'] = np.where(
            lifetime_adjustment_param['unit'] == 'YEAR',
            lifetime_adjustment_param['lifetime_val'] * 4,
            np.where(
                lifetime_adjustment_param['unit'] == 'QUARTER',
                lifetime_adjustment_param['lifetime_val'],
                np.where(
                    lifetime_adjustment_param['unit'] == 'DAY',
                    lifetime_adjustment_param['lifetime_val'] / 365 * 4,
                    np.nan
                )
            )
        )

        lifetime_param = lifetime_adjustment_param[lifetime_adjustment_param['missing_control_only'] == 'N']
        missing_life_param = lifetime_adjustment_param[
            lifetime_adjustment_param['missing_control_only'] == 'Y']
        option_param = param['option_param']
        stage_2_floor_value = option_param.loc[option_param['function']
                                               == 'stage_2_floor', 'option'].values[0]

        # Process life calculations
        OutdatedProcessor = OutdatedAdjustment(loan_table=expo_df)
        expo_df = OutdatedProcessor.process_all()

        MissingProcessor = MissingAdjustment(
            loan_table=expo_df, missing_life_param=missing_life_param)
        expo_df = MissingProcessor.process_all()

        LifeProcessor = ExpectedLifeCalculation(
            loan_table=expo_df, lifetime_param=lifetime_param, floor_param=stage_2_floor_value)
        expo_df = LifeProcessor.process_all()

        return expo_df

    # TODO: update the life calc logic for both expo and fac
    def expected_life_calculation_fac(self, df, param):
        """
        Apply expected life calculation logic to the facility DataFrame.
        Skip outdated processing since facility table doesn't need it.

        Parameters:
        - df (pd.DataFrame): Facility DataFrame
        - param (Dict): Parameter dictionary containing lifetime parameters

        Returns:
        - pd.DataFrame: DataFrame with expected life calculations applied
        """
        # Prepare lifetime parameters
        lifetime_adjustment_param = param['lifetime_param']
        lifetime_adjustment_param['lifetime_val_std'] = np.where(
            lifetime_adjustment_param['unit'] == 'YEAR',
            lifetime_adjustment_param['lifetime_val'] * 4,
            np.where(
                lifetime_adjustment_param['unit'] == 'QUARTER',
                lifetime_adjustment_param['lifetime_val'],
                np.where(
                    lifetime_adjustment_param['unit'] == 'DAY',
                    lifetime_adjustment_param['lifetime_val'] / 365 * 4,
                    np.nan
                )
            )
        )

        lifetime_param = lifetime_adjustment_param[lifetime_adjustment_param['missing_control_only'] == 'N']
        missing_life_param = lifetime_adjustment_param[
            lifetime_adjustment_param['missing_control_only'] == 'Y']
        option_param = param['option_param']
        stage_2_floor_value = option_param.loc[option_param['function']
                                               == 'stage_2_floor', 'option'].values[0]

        # Add missing columns that ExpectedLifeCalculation expects
        if 'maturity_date_final_outdated' not in df.columns:
            df['maturity_date_final_outdated'] = pd.NaT
        if 'maturity_date_final_missing' not in df.columns:
            df['maturity_date_final_missing'] = pd.NaT
        if 'remaining_life_missing' not in df.columns:
            df['remaining_life_missing'] = np.nan

        # Process life calculations (skip outdated processing for facility)
        MissingProcessor = MissingAdjustment(
            loan_table=df, missing_life_param=missing_life_param)
        df = MissingProcessor.process_all()

        LifeProcessor = ExpectedLifeCalculation(
            loan_table=df, lifetime_param=lifetime_param, floor_param=stage_2_floor_value)
        df = LifeProcessor.process_all()

        return df

    def eir_calculation(self, expo_df, param):
        """
        Apply effective interest rate calculation logic to the exposure DataFrame.

        Parameters:
        - expo_df (pd.DataFrame): Exposure DataFrame
        - param (Dict): Parameter dictionary containing EIR calculation parameters

        Returns:
        - pd.DataFrame: DataFrame with effective interest rate calculations applied
        """
        # Define data columns mapping
        data_cols = {
            'eir_rate': 'cur_rt'
        }

        # Apply EIR calculations
        expo_df = self._adopt_contract_rate(expo_df, data_cols)
        expo_df = self._apply_proxy_approach(expo_df)

        return expo_df

    def _adopt_contract_rate(self, expo_df, data_cols):
        """Adopt contract rate as EIR"""
        expo_df['eir'] = expo_df[data_cols['eir_rate']] / 100
        return expo_df

    def _apply_proxy_approach(self, expo_df):
        """Apply proxy approach for invalid EIR values"""
        invalid_mask = (expo_df['eir'].isna()) | (expo_df['eir'] <= 0)

        if invalid_mask.any():
            group_avg = expo_df[~invalid_mask].groupby(
                ['segment', 'sub_segment']
            )['eir'].mean().reset_index()

            expo_df = pd.merge(
                expo_df,
                group_avg.rename(columns={'eir': 'eir_avg'}),
                on=['segment', 'sub_segment'],
                how='left'
            )

            expo_df.loc[invalid_mask,
                        'eir'] = expo_df.loc[invalid_mask, 'eir_avg']
            expo_df.drop(columns=['eir_avg'], inplace=True)

        return expo_df

    def patch_expo(self, expo_df):
        """Patch exposure table"""
        # Patch exposure table
        # for product = IBA, assign loan_class_cd = "PA" and on_off_ind = "ON"
        expo_df.loc[expo_df['product_type_brch'] == 'IBA',
                    'loan_class_cd'] = 'PA'
        expo_df.loc[expo_df['product_type_brch'] == 'IBA',
                    'on_off_ind'] = 'N'

        return expo_df

    def expo_add_cols(self, param, expo_df):
        df = expo_df.copy()

        # 1. Add c800 column
        if 'deal_type' in df.columns and 'chart_of_accounts_param' in param:
            chart_df = param['chart_of_accounts_param']
            df['c800'] = df['deal_type'].apply(
                lambda x: self._get_c800(x, chart_df) if pd.notna(x) else None)
        else:
            df['c800'] = None

        # 2. Add product column
        if 'c800' in df.columns and 'c800_product_param' in param:
            product_df = param['c800_product_param']
            df['product'] = df['c800'].apply(
                lambda x: self._get_product(x, product_df))
        else:
            df['product'] = None

        # 3. Add interco_cd column
        if 'interco_cd_param' in param:
            interco_df = param['interco_cd_param']
            df['interco_cd'] = df.apply(
                lambda row: self._get_interco_cd(row, interco_df), axis=1)
        else:
            df['interco_cd'] = None

        return df

    def _get_c800(self, deal_type, chart_df):
        """Get c800 value based on deal_type range"""
        for _, row in chart_df.iterrows():
            low = row.get('child value low')
            high = row.get('child value high')

            if pd.notna(low) and pd.notna(high):
                try:
                    if float(low) <= float(deal_type) <= float(high):
                        return row.get('c800')
                except:
                    continue
        return None

    def _get_product(self, c800, product_df):
        """Get product value based on c800"""
        if pd.isna(c800):
            return None
        match = product_df[product_df['c800'] == c800]
        if not match.empty:
            return match.iloc[0].get('product')
        return None

    def _get_interco_cd(self, row, interco_df):
        """Get interco_cd based on multiple fields"""
        condition_fields = ['entity', 'cust_id', 'remarks',
                            'resd_country_cd', 'country_of_risk']

        # Build query conditions
        mask = pd.Series([True] * len(interco_df))

        for field in condition_fields:
            if field in row.index and field in interco_df.columns:
                if pd.notna(row[field]):
                    mask = mask & (interco_df[field] == row[field])

        matches = interco_df[mask]
        if not matches.empty:
            return matches.iloc[0].get('interco_cd')
        return None

    def expo_on_off(self,
                    table: pd.DataFrame) -> pd.DataFrame:
        """
        Separate the ON/OFF balance sheet.
        """
        df = table.copy()
        # Separate the ON/OFF balance sheet
        on_df = df[df['on_off_ind'] == 'N']
        off_df_deal = df[df['on_off_ind'] == 'F']

        on_df.reset_index(drop=True, inplace=True)
        off_df_deal.reset_index(drop=True, inplace=True)

        # add col "on_off_ind_final"
        on_df['on_off_ind_final'] = 'ON'
        off_df_deal['on_off_ind_final'] = 'OFF_DEAL'
        return on_df, off_df_deal

    def fac_on_off(self,
                   table: pd.DataFrame) -> pd.DataFrame:
        """
        Filter the facility table to only keep rows where UNDRAWN_AMOUNT > 0.
        """
        df = table.copy()
        if not df.empty:
            off_df_fac = df[df['undrawn_amount'] > 0]
            off_df_fac.reset_index(drop=True, inplace=True)

            # add col "on_off_ind_final"
            off_df_fac['on_off_ind_final'] = 'OFF_FAC'
            return off_df_fac
