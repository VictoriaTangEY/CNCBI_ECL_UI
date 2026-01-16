# Lock packages
import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from pathlib import Path
import time
from ._expected_life import OutdatedAdjustment, MissingAdjustment, ExpectedLifeCalculation
from ._stage_allocation import StageAllocation
from ._ccf import ccf_calculation
from ...modules.ecl_adjustment.mid_run_adjustment import mid_run_adj


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
        """Main data preprocessing pipeline (updated for on/off table)"""

        print('\tProcessing Exposure Table...')
        start_time = time.time()
        expo_df = self._process_expo_table(param)
        print(
            f"\tExposure table processing took: {time.time() - start_time:.2f} seconds")

        print('\tProcessing Facility Table...')
        start_time = time.time()
        fac_df = self._process_fac_table(param)
        print(
            f"\tFacility table processing took: {time.time() - start_time:.2f} seconds")

        print('\tProcessing On/Off Table...')
        start_time = time.time()
        on_off_df, stage_3_df = self._process_on_off_table(
            expo_df, fac_df, context, param)
        print(
            f"\tOn/Off processing took: {time.time() - start_time:.2f} seconds")

        print('\tProcessing Schedule Table...')
        start_time = time.time()
        sched_df = self._process_schedule_table(param, on_off_df)
        print(
            f"\tSchedule processing took: {time.time() - start_time:.2f} seconds")

        print('\tProcessing Collateral Table...')
        start_time = time.time()
        coll_df = self._process_collateral_table(param, on_off_df)
        print(
            f"\tCollateral processing took: {time.time() - start_time:.2f} seconds")

        return on_off_df, stage_3_df, coll_df, sched_df

    def _process_expo_table(self, param):
        # 1. Load exposure table (and append)
        start_time = time.time()
        expo_df = self.load_data(
            self.inDataPath, self.exposure_table_name, self.inputDataExtECL)

        # chk
        print(f"Exposure table rows before append: {len(expo_df)}")

        if 'adj_ind' not in expo_df.columns:
            expo_df['adj_ind'] = 'N'

        # 1.1 adjustment: deal append
        expo_df_append = self.load_data(
            self.inDataPath, f'{self.exposure_table_name}_append', self.inputDataExtECL)

        # chk: print the appended deal
        print(
            f"Exposure table appended deals: {expo_df_append['DEAL_ID'].unique()}")

        if not expo_df_append.empty:
            if 'adj_ind' not in expo_df_append.columns:
                expo_df_append['adj_ind'] = 'Append'
            expo_df = pd.concat([expo_df, expo_df_append], ignore_index=True)

        # add source merged table
        expo_df['source_merged_table'] = 'exposure_table'

        # chk
        print(f"Exposure table rows after append: {len(expo_df)}")

        # 1.2 scope define
        expo_df = self.scope_define_expo(expo_df)

        print(
            f"\t\tExposure table loading took: {time.time() - start_time:.2f} seconds")

        # chk
        print(f"Exposure table rows after scope define: {len(expo_df)}")

        # 1.3 test mode
        if self.test_mode == 'ON' and self.test_deal_list:
            expo_df = self.filter_test_data(expo_df, 'exposure')

        start_time = time.time()
        expo_df = self.standardize_data(
            expo_df, param, 'exposure_table')
        print(
            f"\t\tExposure standardization took: {time.time() - start_time:.2f} seconds")

        return expo_df

    def _process_fac_table(self, param):
        # 2. Load facility table and standardize
        start_time = time.time()
        fac_df = self.load_data(
            self.inDataPath, self.facility_table_name, self.inputDataExtECL)

        # add source merged table
        fac_df['source_merged_table'] = 'facility_table'

        # 2.1 scope define
        fac_df = self.scope_define_fac(fac_df)

        fac_df = self.standardize_data(
            fac_df, param, 'facility_table')
        print(
            f"\t\tFacility table processing took: {time.time() - start_time:.2f} seconds")

        return fac_df

    def _process_on_off_table(self, expo_df, fac_df, context, param):
        """
        Unified processing for exposure and facility tables.
        Returns: on_off_df, stage_3_df
        """

        # Align facility columns to exposure columns
        start_time = time.time()
        expo_cols = set(expo_df.columns)
        fac_cols = set(fac_df.columns)
        # Add missing columns to fac_df
        for col in expo_cols - fac_cols:
            fac_df[col] = np.nan
        # Drop extra columns from fac_df
        fac_df = fac_df[[
            col for col in expo_df.columns if col in fac_df.columns]]
        # Ensure column order matches
        fac_df = fac_df[expo_df.columns]
        print(
            f"\t\tColumn alignment took: {time.time() - start_time:.2f} seconds")

        # Concat
        start_time = time.time()
        on_off_df = pd.concat([expo_df, fac_df], ignore_index=True)
        print(
            f"\t\tDataFrame concatenation took: {time.time() - start_time:.2f} seconds")

        # Optimize memory after concatenation
        on_off_df = self.optimize_memory_usage(on_off_df)

        # convert data types using exposure_table param
        start_time = time.time()
        on_off_df = self.convert_dtypes(
            on_off_df, param, 'exposure_table', self.dtype_tbl)
        print(
            f"\t\tData type conversion took: {time.time() - start_time:.2f} seconds")

        # fillna or empty/whitespace deal_id with facility_nr
        mask = (on_off_df['deal_id'].isna()) | (
            on_off_df['deal_id'].astype(str).str.strip() == '')
        on_off_df.loc[mask, 'deal_id'] = on_off_df.loc[mask, 'facility_nr']

        # if the source_merged_table is facility_table, then let the cur_bal=prin_amt (the prin_amt is undrawn_amount in fac table)
        mask = on_off_df['source_merged_table'] == 'facility_table'
        on_off_df.loc[mask, 'cur_bal'] = on_off_df.loc[mask, 'prin_amt'].values

        # TODO: add amt_col_ind into xx_table_param
        start_time = time.time()
        on_off_df = self.data_curr_conversion(on_off_df, amount_cols=['ccy_amount', 'cur_bal', 'drawn_amount', 'int_accr',
                                                                      'int_susp_amt', 'pmt_amt', 'prin_amt'])
        print(
            f"\t\tCurrency conversion took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        on_off_df = self.amrt_type_cd_standardize(on_off_df)
        print(
            f"\t\tAMRT type standardization took: {time.time() - start_time:.2f} seconds")

        # Scope define (uses source_merged_table)
        start_time = time.time()
        on_off_df = self.on_off_define(on_off_df)
        print(
            f"\t\tScope definition took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        on_off_df = self.segmentation(on_off_df, param)
        print(f"\t\tSegmentation took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        on_off_df, stage_3_df = self.stage_allocation(on_off_df, param)
        print(
            f"\t\tStage allocation took: {time.time() - start_time:.2f} seconds")

        if context.ecl_adj_mode == "ON":
            start_time = time.time()
            on_off_df = mid_run_adj(context, param, on_off_df,
                                    'exposure_table_staged')
            print(
                f"\t\tMid-run adjustment took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        on_off_df = self.expected_life_calculation(on_off_df, param)
        print(
            f"\t\tExpected life calculation took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        on_off_df = self.eir_calculation(on_off_df, param)
        print(
            f"\t\tEIR calculation took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        on_off_df = self.patch_expo(on_off_df)
        print(
            f"\t\tPatching and adding columns took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        on_off_df = ccf_calculation(param, on_off_df)
        print(
            f"\t\tCCF calculation took: {time.time() - start_time:.2f} seconds")

        return on_off_df, stage_3_df

    def _process_schedule_table(self, param, expo_df):
        """Process schedule table"""
        sched_df = self.load_data(
            self.inDataPath, self.schedule_table_name, self.inputDataExtECL)

        if self.test_mode == 'ON' and self.test_deal_list:
            sched_df = self.filter_test_data(sched_df, 'schedule')

        if not sched_df.empty:
            sched_df = self.standardize_data(
                sched_df, param, 'schedule_table')
            sched_df = self.convert_dtypes(
                sched_df, param, 'schedule_table', self.dtype_tbl)
            sched_df = self._sched_curr_conversion(
                sched_df, expo_df, amount_cols=['instl_flat_amt'])

        return sched_df

    def _process_collateral_table(self, param, expo_df):
        """Process collateral table"""
        coll_df = self.load_data(
            self.inDataPath, self.collateral_table_name, self.inputDataExtECL)

        if self.test_mode == 'ON' and self.test_deal_list:
            coll_df = self.filter_test_data(coll_df, 'collateral', expo_df)

        if not coll_df.empty:
            coll_df = self.standardize_data(
                coll_df, param, 'collateral_table')
            coll_df = self.convert_dtypes(
                coll_df, param, 'collateral_table', self.dtype_tbl)
            coll_df = self.data_curr_conversion(
                coll_df, amount_cols=['collateral_amount'])
            print('coll_df after conversion\n', coll_df.head())

        return coll_df

    def optimize_memory_usage(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize DataFrame memory usage by downcasting numeric columns.
        """
        print(
            f"\t\tOptimizing memory usage for DataFrame with {len(df)} rows...")

        # Downcast numeric columns
        for col in df.columns:
            if df[col].dtype == 'float64':
                df[col] = pd.to_numeric(df[col], downcast='float')
            elif df[col].dtype == 'int64':
                df[col] = pd.to_numeric(df[col], downcast='integer')

        # Calculate memory usage
        memory_usage = df.memory_usage(deep=True).sum() / 1024**2  # MB
        print(f"\t\tMemory usage: {memory_usage:.2f} MB")

        return df

    def _vectorize_decorator(self, func):
        """Vectorize a function for numpy operations."""
        return np.vectorize(func)

    def load_data(self,
                  inDataPath: Path,
                  rawDataName: str,
                  inputDataExt: str) -> pd.DataFrame:
        """
        Purely load raw data from CSV file (no filtering, no dtype mapping).
        """
        try:
            df = pd.read_csv(
                f'{inDataPath}/{rawDataName}.{inputDataExt}', encoding='utf-8-sig')
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

    def standardize_data(self,
                         df: pd.DataFrame,
                         param: Dict[str, pd.DataFrame],
                         rawDataName: str) -> pd.DataFrame:
        """
        Standardize data by keeping columns, renaming, and converting dtypes.
        """
        if df.empty:
            return df

        # Get column configuration from parameters
        rawKeepList = param[f'{rawDataName}_param'].query("keep_ind == 'Y'")[
            'colname'].to_list()
        dtypeList = param[f'{rawDataName}_param'].query(
            "keep_ind == 'Y'")['data_type'].to_list()
        renameList = param[f'{rawDataName}_param'].query(
            "keep_ind == 'Y'")['colname_std'].to_list()

        # Only keep columns in keep list
        df = df[rawKeepList]

        # Convert column names to lower case and rename
        df.columns = df.columns.str.lower()
        rename_mapping = {raw.lower(): std.lower()
                          for raw, std in zip(rawKeepList, renameList)}
        df = df.rename(columns=rename_mapping)

        return df

    def convert_dtypes(self,
                       df: pd.DataFrame,
                       param: Dict[str, pd.DataFrame],
                       rawDataName: str,
                       dtype_tbl: Dict[str, type]) -> pd.DataFrame:
        """
        Convert DataFrame columns to specified dtypes using dtypeList and renameList from param.
        """
        dtypeList = param[f'{rawDataName}_param'].query(
            "keep_ind == 'Y'")['data_type'].to_list()
        renameList = param[f'{rawDataName}_param'].query(
            "keep_ind == 'Y'")['colname_std'].to_list()

        def try_parse_date(series):
            for fmt in ["%d%b%Y:%H:%M:%S", "%d/%m/%Y", "%Y-%m-%d", "%Y%m%d"]:
                try:
                    parsed = pd.to_datetime(
                        series, format=fmt, errors='coerce')
                    if parsed.notna().sum() > 0:
                        return parsed
                except Exception:
                    continue
            return pd.to_datetime(series, errors='coerce')

        total_cols = len(renameList)
        print(f"\t\tConverting {total_cols} columns...")

        for i, (col, dtype) in enumerate(zip(renameList, dtypeList)):
            if i % 10 == 0 and i > 0:  # Log progress every 10 columns
                print(f"\t\tConverted {i}/{total_cols} columns...")

            key = col.lower()
            val = dtype_tbl[dtype]
            try:
                if val == 'datetime64' or val == 'datetime64[ns]':
                    df[key] = try_parse_date(df[key])
                elif val == 'float' or val == float or val == np.float64:
                    df[key] = pd.to_numeric(
                        df[key], errors='coerce', downcast='float')
                elif val == 'int' or val == int or val == 'Int64' or val == np.int64:
                    df[key] = pd.to_numeric(
                        df[key], errors='coerce', downcast='integer').astype('Int64')
                elif val == 'str' or val == str:
                    df[key] = df[key].fillna('').astype(str)
                else:
                    df[key] = df[key].astype(val)
            except Exception as e:
                print(f'Report error on data casting for {key} to type {val}.')
                print(e)
                df[key] = df[key].astype('object')
                continue

        print(f"\t\tCompleted converting {total_cols} columns.")
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
        Standardize all relevant currency columns to HKE using optimized vectorized operations.
        """
        # Work directly on the table instead of creating a copy
        for col in amount_cols:
            if col in table.columns:
                # Pre-allocate the new column
                table[f"{col}_hke"] = 0.0

                # Create mask for non-null values
                mask = pd.notna(table[col])

                if mask.any():
                    # Vectorized conversion in one operation
                    multiply_mask = table.loc[mask,
                                              'multiply_divide_ind'] == 'M'

                    # Calculate conversion values
                    conversion_values = np.where(
                        multiply_mask,
                        table.loc[mask, col] * table.loc[mask, 'rate'],
                        table.loc[mask, col] / table.loc[mask, 'rate']
                    )

                    # Apply final conversion to HKE
                    table.loc[mask, f"{col}_hke"] = conversion_values * \
                        table.loc[mask, 'lcy_to_hkd']

        return table

    # @staticmethod
    # def _convert_to_lcy(value: float, ex_rate: float, action: str) -> float:
    #     """Convert a value based on exchange rate and action type."""
    #     if action == 'M':
    #         return value * ex_rate
    #     else:
    #         return value / ex_rate

    def scope_define_expo(self,
                          table: pd.DataFrame) -> pd.DataFrame:
        """
        Filter the expo table to only keep rows where INT_ACCR + PRIN_AMT != 0.
        """
        return table[table['INT_ACCR'] + table['PRIN_AMT'] != 0]

    def scope_define_fac(self,
                         table: pd.DataFrame) -> pd.DataFrame:
        """
        Filter the fac table to only keep rows where PRIN_AMT > 0.
        """
        return table[table['UNDRAWN_AMOUNT'] > 0]

    def on_off_define(self,
                      table: pd.DataFrame) -> pd.DataFrame:
        """
        Filter the expo table to only keep rows where INT_ACCR + PRIN_AMT != 0.
        """
        # TODO: to confirm if to use the prin_amt or cur_bal
        required_cols = ['source_merged_table', 'on_off_ind']
        for col in required_cols:
            if col not in table.columns:
                print(
                    f"Warning: Required column '{col}' not found in DataFrame. Skipping scope filter.")
                return table

        # Add on_off_ind_final column efficiently
        table['on_off_ind_final'] = np.where(
            (table['source_merged_table'] == 'exposure_table') & (
                table['on_off_ind'] == 'N'),
            'ON',
            'OFF'
        )
        table.reset_index(drop=True, inplace=True)

        return table

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

    def segmentation(self, df, param):
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

        # Optimize merge by setting index on the smaller DataFrame
        seg_map_subset = seg_map_subset.set_index(data_cols['seg_id'])

        # Merge with segmentation mapping using index
        df = df.merge(
            seg_map_subset,
            left_on=data_cols['seg_id'],
            right_index=True,
            how='left'
        )

        # Further segment unsecured portfolio
        df['sub_segment'] = np.where(
            df['sub_segment'] == 'Unsecured',
            np.where(df['source_system'].str.strip() == 'CARDLINK',
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
        import time

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

        # Process life calculations with timing
        print(
            f"\t\tProcessing expected life calculation for {len(expo_df)} records...")

        start_time = time.time()
        OutdatedProcessor = OutdatedAdjustment(loan_table=expo_df)
        expo_df = OutdatedProcessor.process_all()
        print(
            f"\t\tOutdated adjustment took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        MissingProcessor = MissingAdjustment(
            loan_table=expo_df, missing_life_param=missing_life_param)
        expo_df = MissingProcessor.process_all()
        print(
            f"\t\tMissing adjustment took: {time.time() - start_time:.2f} seconds")

        start_time = time.time()
        LifeProcessor = ExpectedLifeCalculation(
            loan_table=expo_df, lifetime_param=lifetime_param, floor_param=stage_2_floor_value)
        expo_df = LifeProcessor.process_all()
        print(
            f"\t\tLife calculation took: {time.time() - start_time:.2f} seconds")

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
        # TODO： confirm the proxy approach with dr.ye
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
