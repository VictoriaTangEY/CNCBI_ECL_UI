import pandas as pd
import numpy as np
import os
import warnings
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import threading
warnings.filterwarnings('ignore')


def load_raw_data_files(param_path: str, merge_path: str, SANITY_CHECK_MODE: str = "2.2") -> Dict[str, Any]:
    """Returns: dict with 'excel_files' and 'csv_files'"""
    raw_data = {
        'excel_files': {},
        'csv_files': {}
    }

    test_design_filename = 'PreCheck testdesign table_parameter.xlsx' if SANITY_CHECK_MODE == "2.1" else 'PreCheck testdesign table_full.xlsx'

    # Load Excel files
    for file in os.listdir(param_path):
        if file.endswith(('.xlsx', '.xls')):
            if 'PreCheck testdesign table' in file:
                if file != test_design_filename:
                    continue

            file_path = os.path.join(param_path, file)
            try:
                # Determine engine based on file extension
                if file.endswith('.xlsx'):
                    engine = 'openpyxl'
                elif file.endswith('.xls'):
                    engine = 'xlrd'
                else:
                    engine = None

                xl_file = pd.ExcelFile(file_path, engine=engine)
                raw_data['excel_files'][file] = {}

                for sheet in xl_file.sheet_names:
                    df = pd.read_excel(
                        file_path, sheet_name=sheet, header=None, engine=engine)
                    raw_data['excel_files'][file][sheet] = df
            except Exception as e:
                print(f"Warning: Failed to load Excel file {file}: {e}")
                continue

    # Load CSV files
    for file in os.listdir(merge_path):
        if file.endswith('.csv'):
            file_path = os.path.join(merge_path, file)
            raw_data['csv_files'][file] = pd.read_csv(file_path)
    return raw_data


def process_raw_data(raw_data: Dict[str, Any]) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
    """Process raw data with special format handling"""
    data = {}
    test_designs = {}

    # Process Excel files with special format
    for filename, sheets in raw_data.get('excel_files', {}).items():
        for sheet_name, df in sheets.items():
            # Check if DataFrame has the expected structure
            if df.shape[0] < 4 or df.shape[1] < 2:
                data_df = pd.DataFrame()
            else:
                # Apply special format: column names in row 0, data starts from row 4
                col_names = df.iloc[0, 1:].values
                data_df = df.iloc[4:, 1:].copy()
                data_df.columns = col_names
                data_df = data_df.reset_index(drop=True)

            if 'PreCheck testdesign table' in filename:
                test_designs[sheet_name] = data_df
            else:
                data[f"{filename}_{sheet_name}"] = data_df

    # Add CSV files directly
    for filename, df in raw_data.get('csv_files', {}).items():
        data[filename] = df

    return data, test_designs


class DataHealthCheck:
    def __init__(self, context):
        """Initialize with run_setting context"""
        self.context = context

        # Load raw data
        raw_data = load_raw_data_files(
            str(context.paramPath),
            str(context.inDataPath),
            context.SANITY_CHECK_MODE if hasattr(context, 'SANITY_CHECK_MODE') else "2.2")
        self.data, self.test_designs = process_raw_data(raw_data)
        self.results = []
        self.merged_data_tables = [
            'exposure_table', 'collateral_table', 'schedule_table', 'facility_table']

        # Cache for frequently accessed data
        self._table_cache = {}
        self._data_source_cache = {}

        # Thread lock for results
        self._results_lock = threading.Lock()

        # Pre-process data sources
        for table in self.merged_data_tables:
            df = self._get_table_data(table)
            if df is not None and 'PRODUCT_TYPE_BRCH' in df.columns:
                sources = df['PRODUCT_TYPE_BRCH'].dropna().unique().tolist()
                if sources:
                    self._data_source_cache[table] = sources

    def run(self) -> str:
        """Execute health checks and generate report"""
        # Phase 1: Execute all independent checks in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            phase1_futures = []

            # Hardcoded checks
            SANITY_CHECK_MODE = getattr(
                self.context, 'SANITY_CHECK_MODE', "2.2")
            if SANITY_CHECK_MODE != "2.1":
                phase1_futures.append(
                    executor.submit(self._check_reporting_date))
                phase1_futures.append(executor.submit(
                    self._check_maturity_vs_asof))

            phase1_futures.append(executor.submit(
                self._check_scenario_weight_sum))

            # Test design-based checks
            independent_checks = {
                'existence_check': self._check_exists,
                'duplicate_missing_rate_check': self._check_dup_miss,
                'data_validity_check_range': self._check_range,
                'data_validity_check_category': self._check_category,
            }

            # Handle existence_check specially - it can run without test design
            if 'existence_check' in self.test_designs:
                phase1_futures.append(executor.submit(
                    self._check_exists, self.test_designs['existence_check']))
            else:
                phase1_futures.append(
                    executor.submit(self._check_exists, None))

            # Other checks require test design
            for check_name, check_func in independent_checks.items():
                if check_name != 'existence_check' and check_name in self.test_designs:
                    phase1_futures.append(executor.submit(
                        check_func, self.test_designs[check_name]))

            # Wait for all checks to complete with detailed error reporting
            for future in as_completed(phase1_futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error in check: {e}")

        # Phase 2: Execute parameter_completeness_check
        if 'parameter_completeness_check' in self.test_designs:
            try:
                self._check_completeness(
                    self.test_designs['parameter_completeness_check'])
            except Exception as e:
                print(f"Error in completeness check: {e}")

        return self._generate_report()

    # ==================== Hardcoded checks ====================

    def _check_reporting_date(self):
        """Check if AS_OF_DT matches reporting date"""
        for table in self.merged_data_tables:
            df = self._get_table_data(table)
            if df is None:
                # Missing table - report with appropriate data source
                data_source_cd = 'PARAMETER_TABLE' if table not in self.merged_data_tables else ''
                self._record_check_result('data_validity_check_category', table, 'AS_OF_DT',
                                          'Fail', 'Tab not found', check_type='Check_Uniq_AsOfDT',
                                          data_source_cd=data_source_cd, handling='User to update')
                continue

            if 'AS_OF_DT' not in df.columns:
                for data_source in self._get_data_sources(table):
                    self._record_check_result('data_validity_check_category', table, 'AS_OF_DT',
                                              'Fail', 'Field not found', check_type='Check_Uniq_AsOfDT',
                                              data_source_cd=data_source, handling='User to update')
                continue

            # Vectorized date normalization
            df['normalized_date'] = df['AS_OF_DT'].apply(self._normalize_date)

            for df_subset, data_source in self._iterate_by_data_source(df, table):
                dates = df_subset['normalized_date'].dropna().unique()
                if len(dates) != 1:
                    status, detail = 'Fail', f'Multiple dates found: {dates}'
                elif dates[0] != str(self.context.data_yymm):
                    status, detail = 'Fail', f'Date mismatch: {dates[0]} != {self.context.data_yymm}'
                else:
                    status, detail = 'Pass', f'Date matches: {dates[0]}'

                self._record_check_result('data_validity_check_category', table, 'AS_OF_DT',
                                          status, detail, check_type='Check_Uniq_AsOfDT',
                                          data_source_cd=data_source, handling='User to update')

    def _check_maturity_vs_asof(self):
        """Check if maturity date is after AS_OF_DT"""
        table = 'exposure_table'
        df = self._get_table_data(table)

        if df is None:
            # Tab not found - use appropriate data source
            data_source_cd = 'PARAMETER_TABLE' if table not in self.merged_data_tables else ''
            self._record_check_result('data_validity_check_range', table, 'MATURITY_DATE',
                                      'Fail', 'Tab not found', check_type='Check_MatDT_after_AsOfDT',
                                      data_source_cd=data_source_cd, handling='User to update')
            return

        if not all(col in df.columns for col in ['MATURITY_DATE', 'AS_OF_DT']):
            # Field not found - use actual data sources
            for data_source in self._get_data_sources(table):
                self._record_check_result('data_validity_check_range', table, 'MATURITY_DATE',
                                          'Fail', 'Field not found', check_type='Check_MatDT_after_AsOfDT',
                                          data_source_cd=data_source, handling='User to update')
            return

        # Filter and convert dates
        df = df[(df['MATURITY_DATE'].notna()) &
                (df['AS_OF_DT'].notna())].copy()
        if len(df) == 0:
            return

        df['maturity_dt'] = pd.to_datetime(
            df['MATURITY_DATE'].apply(self._normalize_date), errors='coerce')
        df['as_of_dt'] = pd.to_datetime(df['AS_OF_DT'].apply(
            self._normalize_date), errors='coerce')
        df = df[(df['maturity_dt'].notna()) & (df['as_of_dt'].notna())].copy()

        for df_subset, data_source in self._iterate_by_data_source(df, table):
            if 'DEAL_ID' in df_subset.columns:
                invalid_deals = df_subset[df_subset['maturity_dt']
                                          <= df_subset['as_of_dt']]

                if len(invalid_deals) > 0:
                    for _, row in invalid_deals.iterrows():
                        deal_id = str(row['DEAL_ID'])
                        detail = f"DEAL_ID {deal_id} has MATURITY_DATE {row['maturity_dt'].strftime('%Y-%m-%d')} not after AS_OF_DT"
                        self._record_check_result('data_validity_check_range', table, 'MATURITY_DATE',
                                                  'Fail', detail, check_type='Check_MatDT_after_AsOfDT',
                                                  data_source_cd=data_source, handling='User to update', deal_ids=[deal_id])
                else:
                    self._record_check_result('data_validity_check_range', table, 'MATURITY_DATE',
                                              'Pass', 'All deals have MATURITY_DATE after AS_OF',
                                              check_type='Check_MatDT_after_AsOfDT', data_source_cd=data_source,
                                              handling='User to update')
            else:
                earliest_maturity = df_subset['maturity_dt'].min()
                as_of_date = df_subset['as_of_dt'].iloc[0]

                status = 'Pass' if earliest_maturity > as_of_date else 'Fail'
                detail = f'Earliest maturity {earliest_maturity.date()} {"is" if status == "Pass" else "is not"} after AS_OF {as_of_date.date()}'

                self._record_check_result('data_validity_check_range', table, 'MATURITY_DATE',
                                          status, detail, check_type='Check_MatDT_after_AsOfDT',
                                          data_source_cd=data_source, handling='User to update')

    def _check_scenario_weight_sum(self):
        """Check if scenario weight sum equals 1"""
        df, valid = self._handle_missing_table_or_field('scenario_weight_param', 'scenario_weight',
                                                        'check_scenarioweightsum', handling='User to update')
        if not valid:
            return

        weight_sum = pd.to_numeric(
            df['scenario_weight'], errors='coerce').sum()
        status = 'Pass' if weight_sum == 1.0 else 'Fail'
        detail = f'Sum = {weight_sum}' + \
            ('' if status == 'Pass' else ', expected 1')

        self._record_check_result('check_scenarioweightsum', 'scenario_weight_param', 'scenario_weight',
                                  status, detail, data_source_cd='PARAMETER_TABLE', handling='User to update')

    # ==================== Test design checks ====================

    def _check_exists(self, test_design: pd.DataFrame = None):
        """Check if tabs and fields exist (including hardcoded files)"""

        # First, handle hardcoded file checks
        SANITY_CHECK_MODE = getattr(self.context, 'SANITY_CHECK_MODE', "2.2")

        # Define hardcoded files to check
        hardcoded_checks = []

        # CSV files - only check when not in mode 2.1
        if SANITY_CHECK_MODE != "2.1":
            csv_files = ['collateral_table.csv', 'exposure_table.csv',
                         'facility_table.csv', 'schedule_table.csv']
            csv_files_found = set(os.listdir(self.context.inDataPath))
            for file in csv_files:
                if file not in csv_files_found:
                    tab_name = file.replace('.csv', '')
                    hardcoded_checks.append(('Tab Level', tab_name, ''))

        # XLSX files - always check
        xlsx_files = [
            'CNCBI ECL engine param table_adjustment data.xlsx',
            'CNCBI ECL engine param table_not regularly updated.xlsx',
            'CNCBI ECL engine param table_regular updated.xlsx',
            'PostCheck testdesign table.xlsx',
            'PreCheck testdesign table_full.xlsx',
            'PreCheck testdesign table_parameter.xlsx'
        ]
        xlsx_files_found = set(os.listdir(self.context.paramPath))
        for file in xlsx_files:
            if file not in xlsx_files_found:
                # Report as file level check, not tab level
                self._record_check_result('existence_check', file, '', 'Fail',
                                          'File not found', 'File Level', data_source_cd='', handling='User to update')

        # Get tabs already in test design to avoid duplicates
        tabs_in_test_design = set()
        if test_design is not None:
            tabs_in_test_design = set(
                test_design[test_design['check_level'] == 'Tab Level']['tab_name'].unique())

        # Process hardcoded checks (avoiding duplicates with test design)
        for level, tab, field in hardcoded_checks:
            if tab not in tabs_in_test_design:
                df = self._get_table_data(tab)
                if df is None:
                    data_source_cd = 'PARAMETER_TABLE' if tab not in self.merged_data_tables else ''
                    self._record_check_result('existence_check', tab, '', 'Fail',
                                              'Tab not found', level, data_source_cd=data_source_cd, handling='')

        # Now process test design checks if provided
        if test_design is not None:
            for _, row in test_design.iterrows():
                level = row['check_level']
                tab = row['tab_name']
                field = row.get('field_name', '')

                if level == 'Tab Level':
                    # Check if tab exists - use exact match
                    df = self._get_table_data(tab)
                    exists = df is not None

                    if exists:
                        self._record_check_result('existence_check', tab, '', 'Pass',
                                                  f"Tab exists", level)
                    else:
                        # Tab not found - use appropriate data source
                        data_source_cd = 'PARAMETER_TABLE' if tab not in self.merged_data_tables else ''
                        self._record_check_result('existence_check', tab, '', 'Fail',
                                                  'Tab not found', level, data_source_cd=data_source_cd,
                                                  handling=row.get('handling', ''))
                else:
                    df = self._get_table_data(tab)
                    if df is None:
                        # Use appropriate data source when tab not found
                        data_source_cd = 'PARAMETER_TABLE' if tab not in self.merged_data_tables else ''
                        self._record_check_result('existence_check', tab, field, 'Fail',
                                                  'Tab not found', level, data_source_cd=data_source_cd,
                                                  handling=row.get('handling', ''))
                    else:
                        # Only iterate by data source when table exists
                        for df_subset, data_source in self._iterate_by_data_source(df, tab):
                            exists = field in df_subset.columns
                            self._record_check_result('existence_check', tab, field,
                                                      'Pass' if exists else 'Fail',
                                                      f"Field {'exists' if exists else 'not found'}", level,
                                                      data_source_cd=data_source, handling=row.get('handling', ''))

    def _check_dup_miss(self, test_design: pd.DataFrame):
        """Check for duplicates and missing values"""
        for tab, checks in test_design.groupby('tab_name'):
            df = self._get_table_data(tab)

            if df is None:
                for _, row in checks.iterrows():
                    check_type = row['check_type']
                    field = row['field_name']
                    necessary_flag = row.get('necessary_flag', 'N')
                    status = 'RED' if check_type == 'Check_Missing' and necessary_flag == 'Y' else (
                        'AMBER' if check_type == 'Check_Missing' else 'Fail')

                    # Use appropriate data source for missing tables
                    data_source_cd = 'PARAMETER_TABLE' if tab not in self.merged_data_tables else ''
                    self._record_check_result('duplicate_missing_rate_check', tab, field, status,
                                              'Tab not found', check_type=check_type, data_source_cd=data_source_cd,
                                              handling=row.get('handling', ''))
                continue

            for _, row in checks.iterrows():
                check_type = row['check_type']
                field = row['field_name']
                condition = row.get('skipping_condition', '')
                necessary_flag = row.get('necessary_flag', 'N')

                if field not in df.columns:
                    status = 'RED' if check_type == 'Check_Missing' and necessary_flag == 'Y' else (
                        'AMBER' if check_type == 'Check_Missing' else 'Fail')
                    for data_source in self._get_data_sources(tab):
                        self._record_check_result('duplicate_missing_rate_check', tab, field, status,
                                                  'Field not found', check_type=check_type, data_source_cd=data_source,
                                                  handling=row.get('handling', ''))
                    continue

                for df_subset, data_source in self._iterate_by_data_source(df, tab):
                    if check_type == 'Check_Missing':
                        # Apply skipping conditions inline
                        df_work = df_subset.copy()
                        if pd.notna(condition) and condition:
                            for cond in condition.split('/'):
                                if '<>' in cond:
                                    parts = cond.split('<>')
                                    if len(parts) == 2:
                                        col, values_str = parts[0].strip(
                                        ), parts[1].strip()
                                        if col in df_work.columns:
                                            values = [v.strip()
                                                      for v in values_str.split(',')]
                                            df_work = df_work[~df_work[col].astype(
                                                str).isin(values)]

                        missing_mask = df_work[field].isna()
                        missing = missing_mask.sum()
                        total = len(df_work)
                        rate = missing / total if total > 0 else 0

                        status = 'GREEN' if missing == 0 else (
                            'RED' if necessary_flag == 'Y' else 'AMBER')

                        detail = f"Missing rate: {rate:.2%} ({missing}/{total})"

                        self._record_check_result('duplicate_missing_rate_check', tab, field, status, detail,
                                                  check_type=check_type, data_source_cd=data_source,
                                                  handling=row.get('handling', ''))

                    else:  # Check_Duplicate
                        value_counts = df_subset[field].value_counts()
                        duplicated_values = value_counts[value_counts > 1]

                        if len(duplicated_values) > 0:
                            status = 'Fail'
                            duplicate_list = sorted(
                                duplicated_values.items(), key=lambda x: x[1], reverse=True)

                            # Include product info if available
                            if 'PRODUCT_TYPE_BRCH' in df.columns:
                                product_info = {}
                                for val in duplicated_values.index:
                                    products = df[df[field] == val]['PRODUCT_TYPE_BRCH'].dropna(
                                    ).unique()
                                    product_info[val] = ','.join(products.astype(
                                        str)) if len(products) > 0 else 'N/A'
                                detail = f"Duplicate values: " + ", ".join([f"'{val}' ({cnt} times in {product_info.get(val, 'N/A')})"
                                                                            for val, cnt in duplicate_list])
                            else:
                                detail = f"Duplicate values: " + \
                                    ", ".join(
                                        [f"'{val}' ({cnt} times)" for val, cnt in duplicate_list])
                        else:
                            status = 'Pass'
                            detail = f"Duplicate count: 0"

                        self._record_check_result('duplicate_missing_rate_check', tab, field, status, detail,
                                                  check_type=check_type, data_source_cd=data_source,
                                                  handling=row.get('handling', ''))

    def _check_range(self, test_design: pd.DataFrame):
        """Check if values are within specified range"""
        for _, row in test_design.iterrows():
            tab = row['tab_name']
            field = row['field_name']
            criteria = row['criteria']

            df, valid = self._handle_missing_table_or_field(tab, field, 'data_validity_check_range',
                                                            handling=row.get('handling', ''))
            if not valid:
                continue

            # Filter and convert to numeric
            df_filtered = df[df[field].notna()].copy()
            if len(df_filtered) == 0:
                continue

            df_filtered[f'{field}_numeric'] = pd.to_numeric(
                df_filtered[field], errors='coerce')
            df_filtered = df_filtered[df_filtered[f'{field}_numeric'].notna()].copy(
            )

            if len(df_filtered) == 0:
                for data_source in self._get_data_sources(tab):
                    self._record_check_result('data_validity_check_range', tab, field, 'Fail',
                                              'Field has no valid numeric data after filtering blanks',
                                              data_source_cd=data_source, handling=row.get('handling', ''))
                continue

            for df_subset, data_source in self._iterate_by_data_source(df_filtered, tab):
                if len(df_subset) == 0:
                    continue

                numeric_col = df_subset[f'{field}_numeric']

                # Inline range evaluation
                try:
                    if criteria.startswith('[') and criteria.endswith(']'):
                        bounds = criteria[1:-1].split(',')
                        lower, upper = float(bounds[0]), float(bounds[1])
                        out_of_range_mask = (numeric_col < lower) | (
                            numeric_col > upper)
                    else:
                        # Handle comparison operators
                        if '>=' in criteria:
                            value = float(criteria.replace('>=', '').strip())
                            out_of_range_mask = numeric_col < value
                        elif '<=' in criteria:
                            value = float(criteria.replace('<=', '').strip())
                            out_of_range_mask = numeric_col > value
                        elif '>' in criteria:
                            value = float(criteria.replace('>', '').strip())
                            out_of_range_mask = numeric_col <= value
                        elif '<' in criteria:
                            value = float(criteria.replace('<', '').strip())
                            out_of_range_mask = numeric_col >= value
                        else:
                            self._record_check_result('data_validity_check_range', tab, field, 'Fail',
                                                      f'Invalid criteria format: {criteria}',
                                                      data_source_cd=data_source, handling=row.get('handling', ''))
                            continue
                except ValueError:
                    self._record_check_result('data_validity_check_range', tab, field, 'Fail',
                                              f'Invalid numeric value in criteria: {criteria}',
                                              data_source_cd=data_source, handling=row.get('handling', ''))
                    continue

                out_of_range_values = numeric_col[out_of_range_mask]

                if len(out_of_range_values) == 0:
                    self._record_check_result('data_validity_check_range', tab, field, 'Pass',
                                              'All values in range', data_source_cd=data_source,
                                              handling=row.get('handling', ''))
                elif 'DEAL_ID' in df_subset.columns:
                    # Create one row per failed deal
                    failed_df = df_subset[out_of_range_mask]
                    for _, fail_row in failed_df.iterrows():
                        deal_id = str(fail_row['DEAL_ID'])
                        value = fail_row[f'{field}_numeric']
                        detail = f"DEAL_ID {deal_id} has value {value} out of expected range ({criteria})"
                        self._record_check_result('data_validity_check_range', tab, field, 'Fail', detail,
                                                  data_source_cd=data_source, handling=row.get(
                                                      'handling', ''),
                                                  deal_ids=[deal_id])
                else:
                    unique_out_of_range = out_of_range_values.unique()
                    values_str = ', '.join([str(v)
                                           for v in unique_out_of_range])
                    self._record_check_result('data_validity_check_range', tab, field, 'Fail',
                                              f"Values out of range ({criteria}): {values_str}",
                                              data_source_cd=data_source, handling=row.get('handling', ''))

    def _check_category(self, test_design: pd.DataFrame):
        """Check category match"""
        for _, row in test_design.iterrows():
            if 'option_param' in row['rule_tab']:
                self._check_option_param(row)
            elif 'rating' in row['field_name'].lower() and row['tab_name'] not in self.merged_data_tables[:3]:
                self._check_rating(row)
            else:
                self._check_category_normal(row)

    def _check_option_param(self, row: pd.Series):
        """Special handling for option_param"""
        tab, field, rule_tab = row['tab_name'], row['field_name'], row['rule_tab']
        check_type = row['check_type']
        handling = row.get('handling', '')

        check_df = self._get_table_data(tab)

        if check_df is None:
            # Tab not found - use appropriate data source
            data_source_cd = 'PARAMETER_TABLE' if tab not in self.merged_data_tables else ''
            self._record_check_result('data_validity_check_category', tab, field, 'Fail', 'Tab not found',
                                      check_type=check_type, data_source_cd=data_source_cd, handling=handling)
            return

        rule_df = self._get_table_data(rule_tab)

        if rule_df is None or field not in check_df.columns or 'option' not in rule_df.columns:
            error_detail = 'Rule tab not found' if rule_df is None else 'Field not found'
            for data_source in self._get_data_sources(tab):
                self._record_check_result('data_validity_check_category', tab, field, 'Fail', error_detail,
                                          check_type=check_type, data_source_cd=data_source, handling=handling)
            return

        expected = pd.to_numeric(rule_df['option'], errors='coerce').dropna()
        if len(expected) == 0:
            for data_source in self._get_data_sources(tab):
                self._record_check_result('data_validity_check_category', tab, field, 'Fail', 'No valid rule values',
                                          check_type=check_type, data_source_cd=data_source, handling=handling)
            return
        expected_count = expected.iloc[0]

        df_filtered = check_df[check_df[field].notna()]
        for df_subset, data_source in self._iterate_by_data_source(df_filtered, tab):
            if len(df_subset) == 0:
                continue

            distinct_count = df_subset[field].nunique()
            if 'quarter' in field.lower():
                distinct_count = distinct_count / 4

            status = 'Pass' if distinct_count == expected_count else 'Fail'
            detail = f"Expects {expected_count} distinct values, but field has {distinct_count:.1f} distinct values."
            if 'quarter' in field.lower():
                detail += " (Note: quarter count divided by 4)"

            self._record_check_result('data_validity_check_category', tab, field, status, detail,
                                      check_type=check_type, data_source_cd=data_source, handling=handling)

    def _check_rating(self, row: pd.Series):
        """Special handling for rating fields"""
        check_type, tab, field = row['check_type'], row['tab_name'], row['field_name']
        rule_tab, rule_field = row['rule_tab'], row['rule_field']
        handling = row.get('handling', '')

        check_df = self._get_table_data(tab)
        rule_df = self._get_table_data(rule_tab)

        if check_df is None or rule_df is None:
            error_detail = 'Tab not found'
            for data_source in self._get_data_sources(tab):
                self._record_check_result('data_validity_check_category', tab, field, 'Fail', error_detail,
                                          check_type=check_type, data_source_cd=data_source, handling=handling)
            return

        # Validate required columns
        if not all(col in check_df.columns for col in ['segment', 'sub_segment', field]) or \
                not all(col in rule_df.columns for col in ['segment', 'sub_segment', rule_field]):
            for data_source in self._get_data_sources(tab):
                self._record_check_result('data_validity_check_category', tab, field, 'Fail',
                                          'Required fields missing', check_type=check_type,
                                          data_source_cd=data_source, handling=handling)
            return

        # Filter and prepare data
        check_df = check_df[check_df[field].notna()].copy()
        rule_df = rule_df[rule_df[rule_field].notna()].copy()

        if len(check_df) == 0 or len(rule_df) == 0:
            return

        # Apply exclusions
        if 'grade_corresponding_stage' in rule_df.columns:
            rule_df = rule_df[rule_df['grade_corresponding_stage'] != 3]
        if 'sicr_notchdown' in check_df.columns:
            check_df = check_df[check_df['sicr_notchdown'] != 99]

        check_df['sub_segment'] = check_df['sub_segment'].fillna('')
        rule_df['sub_segment'] = rule_df['sub_segment'].fillna('')

        # Build rule values dictionary
        rule_values_dict = {}
        rule_original_dict = {}  # For storing original values
        for (seg, sub_seg), group in rule_df.groupby(['segment', 'sub_segment']):
            rule_vals = set()
            rule_orig = {}
            for v in group[rule_field].unique():
                try:
                    rule_vals.add(float(v))
                    rule_orig[float(v)] = v
                except (ValueError, TypeError):
                    lower_v = str(v).lower()
                    rule_vals.add(lower_v)
                    rule_orig[lower_v] = str(v)
            rule_values_dict[(seg, sub_seg)] = rule_vals
            rule_original_dict[(seg, sub_seg)] = rule_orig

        # Check by groups
        failed_details = []
        for (segment, sub_segment), group in check_df.groupby(['segment', 'sub_segment']):
            check_values = set()
            check_orig = {}
            for v in group[field].unique():
                try:
                    check_values.add(float(v))
                    check_orig[float(v)] = v
                except (ValueError, TypeError):
                    lower_v = str(v).lower()
                    check_values.add(lower_v)
                    check_orig[lower_v] = str(v)

            rule_values = rule_values_dict.get((segment, sub_segment), set())
            rule_orig = rule_original_dict.get((segment, sub_segment), {})
            group_name = f"{segment}_{sub_segment}" if sub_segment else segment

            if check_type == 'Check_CateExact':
                if check_values != rule_values:
                    only_in_check = list(check_values - rule_values)
                    only_in_rule = list(rule_values - check_values)
                    if only_in_check:
                        orig_vals = [check_orig.get(v, v)
                                     for v in only_in_check]
                        failed_details.append(
                            f"{group_name}: Field include category that is not expected {orig_vals}")
                    if only_in_rule:
                        orig_vals = [rule_orig.get(v, v) for v in only_in_rule]
                        failed_details.append(
                            f"{group_name}: missing required category {orig_vals}")
            else:  # Check_CateInclude
                only_in_check = list(check_values - rule_values)
                if only_in_check:
                    orig_vals = [check_orig.get(v, v) for v in only_in_check]
                    failed_details.append(
                        f"{group_name}: Field include category that is not expected {orig_vals}")

        status = 'Pass' if not failed_details else 'Fail'
        detail = "; ".join(
            failed_details) if failed_details else "All groups pass"

        self._record_check_result('data_validity_check_category', tab, field, status, detail,
                                  check_type=check_type, data_source_cd='PARAMETER_TABLE', handling=handling)

    def _check_category_normal(self, row: pd.Series):
        """Normal category check"""
        check_type, tab, field = row['check_type'], row['tab_name'], row['field_name']
        rule_tab, rule_field = row['rule_tab'], row['rule_field']
        handling = row.get('handling', '')

        check_df = self._get_table_data(tab)

        if check_df is None:
            # Tab not found - use appropriate data source
            data_source_cd = 'PARAMETER_TABLE' if tab not in self.merged_data_tables else ''
            self._record_check_result('data_validity_check_category', tab, field, 'Fail', 'Tab not found',
                                      check_type=check_type, data_source_cd=data_source_cd, handling=handling)
            return

        rule_data = self._get_field_data(rule_tab, rule_field)
        if rule_data is None:
            for data_source in self._get_data_sources(tab):
                self._record_check_result('data_validity_check_category', tab, field, 'Fail', 'Rule tab not found',
                                          check_type=check_type, data_source_cd=data_source, handling=handling)
            return

        # Get rule values - keep both lowercase for comparison and original for display
        rule_values = set()
        rule_values_original = {}  # lowercase -> original mapping
        for v in rule_data.dropna().unique():
            try:
                rule_values.add(float(v))
                rule_values_original[float(v)] = v
            except (ValueError, TypeError):
                lower_v = str(v).lower()
                rule_values.add(lower_v)
                rule_values_original[lower_v] = str(v)

        if not rule_values:
            for data_source in self._get_data_sources(tab):
                self._record_check_result('data_validity_check_category', tab, field, 'Fail',
                                          'No valid rule values after filtering blanks',
                                          check_type=check_type, data_source_cd=data_source, handling=handling)
            return

        for df_subset, data_source in self._iterate_by_data_source(check_df, tab):
            field_data = self._get_field_data(df_subset, field)
            if field_data is None:
                self._record_check_result('data_validity_check_category', tab, field, 'Fail', 'Field not found',
                                          check_type=check_type, data_source_cd=data_source, handling=handling)
                continue

            # Filter nulls
            field_data = field_data[field_data.notna()]
            if len(field_data) == 0:
                continue

            # Get check values - keep both lowercase for comparison and original for display
            check_values = set()
            check_values_original = {}  # lowercase -> original mapping
            for v in field_data.unique():
                try:
                    check_values.add(float(v))
                    check_values_original[float(v)] = v
                except (ValueError, TypeError):
                    lower_v = str(v).lower()
                    check_values.add(lower_v)
                    check_values_original[lower_v] = str(v)

            if check_type == 'Check_CateExact':
                status = 'Pass' if check_values == rule_values else 'Fail'
                if status == 'Fail':
                    details = []
                    only_in_rule = list(rule_values - check_values)
                    only_in_check = list(check_values - rule_values)
                    if only_in_rule:
                        # Use original values for display
                        original_vals = [rule_values_original.get(
                            v, v) for v in only_in_rule]
                        details.append(
                            f"Missing required category: {original_vals}")
                    if only_in_check:
                        # Use original values for display
                        original_vals = [check_values_original.get(
                            v, v) for v in only_in_check]
                        details.append(
                            f"Field include category that is not expected: {original_vals}")
                    detail = "; ".join(details)
                else:
                    detail = "All values match exactly."
            elif check_type == 'Check_CateInclude':
                status = 'Pass' if check_values.issubset(
                    rule_values) else 'Fail'
                if status == 'Fail':
                    diff_vals = list(check_values - rule_values)
                    original_vals = [check_values_original.get(
                        v, v) for v in diff_vals]
                    detail = f"Field include category that is not expected: {original_vals}"
                else:
                    detail = 'All values are included in rule.'
            else:  # Check_CateContain
                status = 'Pass' if rule_values.issubset(
                    check_values) else 'Fail'
                if status == 'Fail':
                    diff_vals = list(rule_values - check_values)
                    original_vals = [rule_values_original.get(
                        v, v) for v in diff_vals]
                    detail = f"Missing required category: {original_vals}"
                else:
                    detail = 'All required rule values are present.'

            self._record_check_result('data_validity_check_category', tab, field, status, detail,
                                      check_type=check_type, data_source_cd=data_source, handling=handling)

    def _check_completeness(self, test_design: pd.DataFrame):
        """Check completeness based on category results"""
        # Build category results lookup
        category_results = {}
        for r in self.results:
            if r['check_category'] == 'data_validity_check_category':
                data_source = r.get(
                    'data_source_cd', 'PARAMETER_TABLE') or 'PARAMETER_TABLE'
                key = f"{r['tab_name']}_{r['field_name']}_{data_source}"
                category_results[key] = {
                    'flag': r['check_flg'],
                    'detail': r.get('fail_detail', ''),
                    'field': r['field_name']
                }

        for _, row in test_design.iterrows():
            tab = row['tab_name']
            check_group = row.get('check_column', '')
            columns = [c.strip() for c in check_group.split(',')
                       ] if pd.notna(check_group) else []

            df = self._get_table_data(tab)
            for _, data_source in self._iterate_by_data_source(df, tab):
                data_source = data_source or 'PARAMETER_TABLE'

                # Collect failed fields
                failed_fields = []
                for col in columns:
                    key = f"{tab}_{col}_{data_source}"
                    result = category_results.get(key)

                    if result and result['flag'] != 'Pass':
                        failed_fields.append((col, result['detail']))

                if failed_fields:
                    for field, field_detail in failed_fields:
                        self._record_check_result('parameter_completeness_check', tab, check_group,
                                                  'Fail', field_detail, data_source_cd=data_source,
                                                  fail_field=field, handling=row.get('handling', ''))
                else:
                    self._record_check_result('parameter_completeness_check', tab, check_group,
                                              'Pass', 'All fields complete', data_source_cd=data_source)

    # ==================== Helper methods ====================

    def _handle_missing_table_or_field(self, tab: str, field: str, category: str,
                                       check_type: str = '', handling: str = ''):
        """Handle missing table or field error"""
        df = self._get_table_data(tab)
        if df is None:
            # Determine data_source_cd based on table type
            data_source_cd = 'PARAMETER_TABLE' if tab not in self.merged_data_tables else ''
            self._record_check_result(category, tab, field, 'Fail', 'Tab not found',
                                      check_type=check_type, data_source_cd=data_source_cd, handling=handling)
            return None, False

        if field and field not in df.columns:
            for data_source in self._get_data_sources(tab):
                self._record_check_result(category, tab, field, 'Fail', 'Field not found',
                                          check_type=check_type, data_source_cd=data_source, handling=handling)
            return df, False

        return df, True

    def _get_table_data(self, tab_name: str) -> Optional[pd.DataFrame]:
        """Get data for specified table/tab name with caching"""
        if tab_name in self._table_cache:
            return self._table_cache[tab_name]

        # Try exact match first
        result = None
        if tab_name in self.data:
            result = self.data[tab_name]
        elif f"{tab_name}.csv" in self.data:
            result = self.data[f"{tab_name}.csv"]
        else:
            # For Excel sheets, look for keys ending with "_<tab_name>"
            for key in self.data.keys():
                if key.endswith(f"_{tab_name}"):
                    result = self.data[key]
                    break

        self._table_cache[tab_name] = result
        return result

    def _get_field_data(self, tab_name_or_df, field_name: str) -> Optional[pd.Series]:
        """Get field data from table name or dataframe, support compound fields"""
        df = self._get_table_data(tab_name_or_df) if isinstance(
            tab_name_or_df, str) else tab_name_or_df
        if df is None:
            return None

        if '+' in field_name:
            # Handle compound fields
            fields = [f.strip() for f in field_name.split('+')]
            if all(f in df.columns for f in fields):
                result = df[fields[0]].astype(str)
                for f in fields[1:]:
                    result = result + '_' + df[f].astype(str)
                return result
        return df.get(field_name)

    def _get_data_sources(self, table_name: str) -> List[str]:
        """Get data sources for a table with caching"""
        # Always check if table exists first, even if cached
        df = self._get_table_data(table_name)

        # If table doesn't exist
        if df is None:
            # For parameter tables (not in merged_data_tables), return PARAMETER_TABLE
            if table_name not in self.merged_data_tables:
                return ['PARAMETER_TABLE']
            # For merged tables, return blank
            return ['']

        # Check cache for existing tables
        if table_name in self._data_source_cache:
            return self._data_source_cache[table_name]

        # For existing merged tables, get data sources from PRODUCT_TYPE_BRCH
        if table_name in self.merged_data_tables and 'PRODUCT_TYPE_BRCH' in df.columns:
            sources = df['PRODUCT_TYPE_BRCH'].dropna().unique().tolist()
            if sources:
                self._data_source_cache[table_name] = sources
                return sources

        # Default for existing tables without PRODUCT_TYPE_BRCH
        result = ['']
        self._data_source_cache[table_name] = result
        return result

    def _iterate_by_data_source(self, df: pd.DataFrame, table_name: str) -> List[Tuple[pd.DataFrame, str]]:
        """Helper to iterate dataframes by PRODUCT_TYPE_BRCH if applicable"""
        # If df is None (missing table), return empty iteration with blank data source
        if df is None:
            if table_name not in self.merged_data_tables:
                return [(None, 'PARAMETER_TABLE')]
            else:
                return [(None, '')]

        if table_name in self.merged_data_tables and 'PRODUCT_TYPE_BRCH' in df.columns:
            return [(group, pt) for pt, group in df.groupby('PRODUCT_TYPE_BRCH', dropna=True)]
        return [(df, 'PARAMETER_TABLE')]

    @lru_cache(maxsize=10000)
    def _normalize_date(self, date_value) -> str:
        """Normalize date to YYYYMMDD format for comparison"""
        if pd.isna(date_value) or date_value is None:
            return None

        date_str = str(date_value).strip()
        if ':' in date_str:
            date_str = date_str.split(':')[0]

        try:
            return pd.to_datetime(date_str, dayfirst=True).strftime('%Y%m%d')
        except:
            # Try common formats
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d']:
                try:
                    return pd.to_datetime(date_str, format=fmt).strftime('%Y%m%d')
                except:
                    continue
        return None

    def _record_check_result(self, category: str, tab: str, field: str, status: str, detail: str,
                             level: str = '', check_type: str = '', data_source_cd: str = '', fail_field: str = '',
                             handling: str = '', deal_ids: List[str] = None):
        """Record validation check result"""
        result = {
            'check_category': category,
            'check_level': level,
            'check_type': check_type,
            'tab_name': tab,
            'field_name': field,
            'data_source_cd': data_source_cd,
            'check_flg': status,
            'incomplete_field': fail_field,
            'deal_ids': ', '.join(deal_ids) if deal_ids else '',
            'fail_detail': detail,
            'handling': handling
        }

        with self._results_lock:
            self.results.append(result)

    # ==================== Report generation ====================

    def _generate_report(self) -> str:
        """Generate report with optimized DataFrame operations"""
        df_results = pd.DataFrame(self.results)

        # Pre-compute categories and their failed records
        categories = df_results['check_category'].unique()
        failed_mask = df_results['check_flg'].isin(['Fail', 'RED', 'AMBER'])

        # Define columns for each sheet type
        sheet_columns = {
            'data_validity_check_category': ['check_type', 'data_source_cd', 'tab_name', 'field_name', 'check_flg', 'fail_detail', 'handling'],
            'parameter_completeness_check': ['data_source_cd', 'tab_name', 'check_group', 'check_flg', 'incomplete_field', 'fail_detail', 'handling'],
            'duplicate_missing_rate_check': ['check_type', 'data_source_cd', 'tab_name', 'field_name', 'check_flg', 'fail_detail', 'handling'],
            'existence_check': ['check_level', 'data_source_cd', 'tab_name', 'field_name', 'check_flg', 'handling'],
            'data_validity_check_range': ['data_source_cd', 'tab_name', 'field_name', 'check_flg', 'deal_ids', 'fail_detail', 'handling'],
            'check_scenarioweightsum': ['data_source_cd', 'tab_name', 'field_name', 'check_flg', 'fail_detail', 'handling']
        }

        # Determine output filename
        SANITY_CHECK_MODE = getattr(self.context, 'SANITY_CHECK_MODE', "2.2")
        report_suffix = 'parameter' if SANITY_CHECK_MODE == "2.1" else 'full'
        output_path = os.path.join(
            self.context.outReportPath,
            f'pre_data_health_check_report_{report_suffix}_{self.context.data_yymm}.xlsx'
        )

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Generate validreport if applicable
            if 'validtestdesc' in self.test_designs:
                valid_test_desc = self.test_designs['validtestdesc'].copy()

                # Use dictionary mapping to simplify logic
                check_mapping = {
                    'duplicate_key_check': ('duplicate_missing_rate_check', 'Check_Duplicate', ['Fail']),
                    'missing_rate_check': ('duplicate_missing_rate_check', 'Check_Missing', ['RED', 'AMBER', 'GREEN'])
                }

                result_flags = []
                for data_val_test in valid_test_desc['data_validation_test']:
                    if data_val_test in check_mapping:
                        category, check_type, flag_order = check_mapping[data_val_test]
                        subset = df_results[(df_results['check_category'] == category) &
                                            (df_results['check_type'] == check_type)]

                        if data_val_test == 'missing_rate_check':
                            result_flag = 'GREEN'
                            for flag in flag_order:
                                if (subset['check_flg'] == flag).any():
                                    result_flag = flag
                                    break
                        else:
                            result_flag = 'Fail' if (
                                subset['check_flg'] == 'Fail').any() else 'Pass'
                    else:
                        subset = df_results[df_results['check_category']
                                            == data_val_test]
                        result_flag = 'Fail' if (
                            subset['check_flg'] == 'Fail').any() else 'Pass'

                    result_flags.append(result_flag)

                valid_test_desc['result_flag'] = result_flags

                # Reorder columns
                priority_cols = ['data_validation_test',
                                 'result_flag', 'remark']
                other_cols = [
                    col for col in valid_test_desc.columns if col not in priority_cols]
                ordered_cols = [
                    col for col in priority_cols if col in valid_test_desc.columns] + other_cols

                valid_test_desc[ordered_cols].to_excel(
                    writer, sheet_name='validreport', index=False)

            # Process failed checks for each category
            for category in categories:
                failed = df_results[(
                    df_results['check_category'] == category) & failed_mask].copy()

                if len(failed) > 0:
                    failed = failed.sort_values(
                        ['data_source_cd', 'tab_name', 'field_name'])

                    # Special handling for parameter_completeness_check
                    if category == 'parameter_completeness_check':
                        failed = failed.rename(
                            columns={'field_name': 'check_group'})

                    # Get columns
                    if category in sheet_columns:
                        cols = [col for col in sheet_columns[category]
                                if col in failed.columns]
                    else:
                        cols = ['data_source_cd', 'tab_name', 'field_name',
                                'check_flg', 'deal_ids', 'fail_detail']
                        cols = [col for col in cols if col in failed.columns]

                    failed[cols].to_excel(
                        writer, sheet_name=category, index=False)

        print(f"Report generated: {output_path}")
        return output_path
