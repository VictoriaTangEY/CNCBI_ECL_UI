import pandas as pd
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional, Callable
import warnings
warnings.filterwarnings('ignore')


class DataHealthCheck:
    def __init__(self, context):
        self.snp_yymm = context.snp_yymm
        self.paramPath = context.paramPath
        self.inDataPath = context.inDataPath
        self.outReportPath = context.outReportPath
        self.raw_data = self.load_raw_data_files()
        self.data, self.test_designs = self._process_raw_data(self.raw_data)
        self.results = []

    def load_raw_data_files(self) -> Dict[str, Any]:
        """Returns: dict with 'excel_files' and 'csv_files'"""
        raw_data = {
            'excel_files': {},
            'csv_files': {}
        }
        # Load Excel files as raw data
        for file in os.listdir(self.paramPath):
            if file.endswith(('.xlsx', '.xls')):
                file_path = os.path.join(self.paramPath, file)
                xl_file = pd.ExcelFile(file_path)
                raw_data['excel_files'][file] = {}

                for sheet in xl_file.sheet_names:
                    df = pd.read_excel(
                        file_path, sheet_name=sheet, header=None)
                    raw_data['excel_files'][file][sheet] = df
        # Load CSV files
        for file in os.listdir(self.inDataPath):
            if file.endswith('.csv'):
                file_path = os.path.join(self.inDataPath, file)
                raw_data['csv_files'][file] = pd.read_csv(file_path)
        return raw_data

    def _process_raw_data(self, raw_data: Dict[str, Any]) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
        """Process raw data with special format handling"""
        data = {}
        test_designs = {}

        # Process Excel files with special format
        for filename, sheets in raw_data.get('excel_files', {}).items():
            for sheet_name, df in sheets.items():
                # Check if DataFrame has the expected structure
                if df.shape[0] < 4 or df.shape[1] < 2:
                    # Create empty DataFrame with warning - let validation checks handle this
                    data_df = pd.DataFrame()
                else:
                    # Apply special format: column names in row 0, data starts from row 3
                    col_names = df.iloc[0, 1:].values
                    data_df = df.iloc[3:, 1:].copy()
                    data_df.columns = col_names
                    data_df = data_df.reset_index(drop=True)

                if 'PreCheck_testdesign_table' in filename:
                    test_designs[sheet_name] = data_df
                else:
                    data[f"{filename}_{sheet_name}"] = data_df

        # Add CSV files directly
        for filename, df in raw_data.get('csv_files', {}).items():
            data[filename] = df

        return data, test_designs

    def run(self) -> str:
        """Execute health checks and generate report"""
        # load and process data
        # TODO:if need to update here?

        # Hardcoded checks
        self._check_reporting_date()
        self._check_maturity_vs_asof()
        self._check_scenario_weight_sum()
        # Test design-based checks
        check_mapping = {
            'Check_Exists': self._check_exists,
            'Check_DupMiss': self._check_dup_miss,
            'Check_Range': self._check_range,
            'Check_Category': self._check_category,
            'Check_Completeness': self._check_completeness
        }
        for check_name, check_func in check_mapping.items():
            if check_name in self.test_designs:
                check_func(self.test_designs[check_name])
        return self._generate_report()

    # ==================== Hardcoded checks ====================

    def _check_reporting_date(self):
        """Check if AS_OF_DT matches reporting date"""
        df = self._get_data('Cust_merged_data')
        # 使用新的_validate_columns方法
        is_valid, error_detail = self._validate_columns(
            df, ['AS_OF_DT'], 'Cust_merged_data')
        if not is_valid:
            self._add_result('Check_Category', 'Cust_merged_data', 'AS_OF_DT',
                             'Fail', error_detail, check_type='Check_Uniq_AsOfDT')
            return

        dates = df['AS_OF_DT'].apply(self._normalize_date).dropna().unique()

        if len(dates) != 1:
            status, detail = 'Fail', f'Multiple dates found: {dates}'
        elif dates[0] != self.snp_yymm:
            status, detail = 'Fail', f'Date mismatch: {dates[0]} != {self.snp_yymm}'
        else:
            status, detail = 'Pass', f'Date matches: {dates[0]}'

        self._add_result('Check_Category', 'Cust_merged_data',
                         'AS_OF_DT', status, detail, check_type='Check_Uniq_AsOfDT')

    def _check_maturity_vs_asof(self):
        """Check if earliest maturity date is after AS_OF_DT"""
        df = self._get_data('Cust_merged_data')
        is_valid, error_detail = self._validate_columns(
            df, ['MATURITY_DATE', 'AS_OF_DT'], 'Cust_merged_data')
        if not is_valid:
            self._add_result('Check_Range', 'Cust_merged_data', 'MATURITY_DATE',
                             'Fail', error_detail, check_type='Check_MatDT_after_AsOfDT')
            return

        maturity = pd.to_datetime(df['MATURITY_DATE'].apply(
            self._normalize_date), errors='coerce')
        as_of = pd.to_datetime(df['AS_OF_DT'].apply(
            self._normalize_date), errors='coerce')

        earliest_maturity = maturity.dropna().min()
        as_of_date = as_of.dropna().iloc[0] if len(
            as_of.dropna()) > 0 else pd.NaT

        if pd.isna(earliest_maturity) or pd.isna(as_of_date):
            status, detail = 'Fail', 'Invalid dates found'
        elif earliest_maturity > as_of_date:
            status, detail = 'Pass', f'Earliest maturity {earliest_maturity.date()} is after AS_OF {as_of_date.date()}'
        else:
            status, detail = 'Fail', f'Earliest maturity {earliest_maturity.date()} is not after AS_OF {as_of_date.date()}'

        self._add_result('Check_Range', 'Cust_merged_data', 'MATURITY_DATE',
                         status, detail, check_type='Check_MatDT_after_AsOfDT')

    def _check_scenario_weight_sum(self):
        """Check if scenario weight sum equals 1"""
        df = self._get_data('Scenario weight_Param')
        is_valid, error_detail = self._validate_columns(
            df, ['Scenario_weight'], 'Scenario weight_Param')
        if not is_valid:
            self._add_result('Check_ScenarioWeightSum', 'Scenario weight_Param', 'Scenario_weight',
                             'Fail', error_detail)
            return

        weight_sum = pd.to_numeric(
            df['Scenario_weight'], errors='coerce').sum()

        if weight_sum == 1.0:
            status, detail = 'Pass', f'Sum = {weight_sum}'
        else:
            status, detail = 'Fail', f'Sum = {weight_sum}, expected 1'

        self._add_result('Check_ScenarioWeightSum',
                         'Scenario weight_Param', 'Scenario_weight', status, detail)

    # ==================== Test design checks ====================

    def _check_exists(self, test_design: pd.DataFrame):
        """Check if tabs and fields exist"""
        for _, row in test_design.iterrows():
            level = row['Check Level']
            tab = row['Tab Name']
            field = row.get('Field Name', '')

            if level == 'Tab Level':
                exists = any(tab in key for key in self.data.keys())
                self._add_result('Check_Exists', tab, '', 'Pass' if exists else 'Fail',
                                 f"Tab {'exists' if exists else 'not found'}", level)
            else:
                df = self._get_data(tab)
                if df is None:
                    self._add_result('Check_Exists', tab, field,
                                     'Fail', 'Tab and columns not found', level)
                else:
                    exists = field in df.columns
                    self._add_result('Check_Exists', tab, field, 'Pass' if exists else 'Fail',
                                     f"Field {'exists' if exists else 'Column not found'}", level)

    def _check_dup_miss(self, test_design: pd.DataFrame):
        """Check for duplicates and missing values"""
        for _, row in test_design.iterrows():
            check_type = row['Check Type']
            tab = row['Tab Name']
            field = row['Field Name']
            condition = row.get('Skipping Condition', '')

            df = self._get_data(tab)
            is_valid, error_detail = self._validate_columns(df, [field], tab)
            if not is_valid:
                self._add_result('Check_DupMiss', tab, field,
                                 'Fail', error_detail, check_type=check_type)
                continue

            # Apply skipping conditions
            if pd.notna(condition) and condition:
                df = self._apply_condition(df, condition)

            if check_type == 'Check_Missing':
                missing = df[field].isna().sum()
                total = len(df)
                rate = missing / total if total > 0 else 0
                status = 'Pass' if missing == 0 else 'Fail'
                detail = f"Missing rate: {rate:.2%} ({missing}/{total})"
            else:
                # Check for duplicates
                # Find all duplicated values (including first occurrence)
                duplicated_mask = df[field].duplicated(keep=False)
                # Count of duplicate rows (excluding first occurrence)
                dup_count = df[field].duplicated().sum()

                if dup_count > 0:
                    # Get the actual duplicate values
                    duplicate_values = df.loc[duplicated_mask,
                                              field].value_counts()
                    # Sort by count (descending) and convert to list of tuples
                    duplicate_list = [(value, count)
                                      for value, count in duplicate_values.items()]
                    duplicate_list.sort(key=lambda x: x[1], reverse=True)

                    # Format detail message
                    status = 'Fail'
                    detail = f"Duplicate count: {dup_count}. Duplicate values: "

                    # Show top 10 duplicate values if there are many
                    if len(duplicate_list) > 10:
                        top_duplicates = duplicate_list[:10]
                        detail += ", ".join(
                            [f"'{val}' ({cnt} times)" for val, cnt in top_duplicates])
                        detail += f", ... and {len(duplicate_list) - 10} more unique duplicate values"
                    else:
                        detail += ", ".join(
                            [f"'{val}' ({cnt} times)" for val, cnt in duplicate_list])
                else:
                    status = 'Pass'
                    detail = f"Duplicate count: {dup_count}"

            self._add_result('Check_DupMiss', tab, field,
                             status, detail, check_type=check_type)

    def _check_range(self, test_design: pd.DataFrame):
        """Check if values are within specified range"""
        for _, row in test_design.iterrows():
            tab = row['Tab Name']
            field = row['Field name']
            criteria = row['Criteria']

            df = self._get_data(tab)
            is_valid, error_detail = self._validate_columns(df, [field], tab)
            if not is_valid:
                self._add_result('Check_Range', tab, field,
                                 'Fail', error_detail)
                continue

            numeric_col = pd.to_numeric(df[field], errors='coerce').dropna()
            if len(numeric_col) == 0:
                self._add_result('Check_Range', tab, field,
                                 'Fail', 'No numeric data')
                continue

            status, detail = self._evaluate_range(numeric_col, criteria)
            self._add_result('Check_Range', tab, field, status, detail)

    def _check_category(self, test_design: pd.DataFrame):
        """Check category match"""
        for _, row in test_design.iterrows():
            check_type = row['Check Type']
            tab = row['Tab Name']
            field = row['Field Name']
            rule_tab = row['Rule Tab']

            # Special handling logic
            if 'Option_Param' in rule_tab:
                self._check_option_param(row)
            elif 'rating' in field.lower() and tab not in ['Cust_merged_data', 'LGD_merged_data']:
                self._check_rating(row)
            else:
                self._check_category_normal(row)

    def _check_completeness(self, test_design: pd.DataFrame):
        """Check completeness"""
        category_results = {
            f"{r['Tab Name']}_{r['Field Name']}": r['Status']
            for r in self.results
            if r['Check Category'] == 'Check_Category'
        }

        for _, row in test_design.iterrows():
            tab = row['Tab Name']
            columns = [c.strip() for c in row['Check Column'].split(
                ',')] if pd.notna(row['Check Column']) else []

            failed = [col for col in columns if category_results.get(
                f"{tab}_{col}") != 'Pass']

            status = 'Pass' if not failed else 'Fail'
            detail = 'All columns complete' if not failed else f"Failed columns: {', '.join(failed)}"
            self._add_result('Check_Completeness', tab,
                             ', '.join(columns), status, detail)

    # ==================== Helper methods ====================

    def _get_data(self, tab_name: str) -> Optional[pd.DataFrame]:
        """Get data table"""
        keys = [k for k in self.data.keys() if tab_name in k]
        return self.data[keys[0]] if keys else None

    def _validate_columns(self, df: pd.DataFrame, columns: List[str], tab_name: str) -> Tuple[bool, str]:
        """Validate if columns exist, returns (is_valid, error_detail)"""
        if df is None:
            return False, 'Tab not found'

        missing = [col for col in columns if col not in df.columns]
        if missing:
            return False, f'Columns not found: {missing}'

        return True, ''

    def _normalize_date(self, date_value) -> str:
        """Normalize date to YYYYMMDD format for comparison """
        if pd.isna(date_value) or date_value is None:
            return None
        date_str = str(date_value).strip()

        # Handle special case with colon separator
        if ':' in date_str:
            date_str = date_str.split(':')[0]

        formats = [
            '%Y-%m-%d',      # 2024-01-15
            '%Y/%m/%d',      # 2024/01/15
            '%d/%m/%Y',      # 15/01/2024
            '%m/%d/%Y',      # 01/15/2024
            '%d-%m-%Y',      # 15-01-2024
            '%m-%d-%Y',      # 01-15-2024
            '%d%b%Y',        # 15Jan2024
            '%d %b %Y',      # 15 Jan 2024
            '%d %B %Y',      # 15 January 2024
            '%Y%m%d',        # 20240115
            '%d.%m.%Y',      # 15.01.2024
            '%Y.%m.%d',      # 2024.01.15
        ]
        try:
            return pd.to_datetime(date_str, dayfirst=True).strftime('%Y%m%d')
        except:
            pass
        for fmt in formats:
            try:
                return pd.to_datetime(date_str, format=fmt).strftime('%Y%m%d')
            except:
                continue
        try:
            return pd.to_datetime(date_str, infer_datetime_format=True).strftime('%Y%m%d')
        except:
            return None

    def _apply_condition(self, df: pd.DataFrame, condition: str) -> pd.DataFrame:
        """Apply skipping conditions"""
        for cond in condition.split('/'):
            if '<>' in cond:
                parts = cond.split('<>')
                if len(parts) == 2:
                    col, values_str = parts[0].strip(), parts[1].strip()
                    if col in df.columns:
                        values = [v.strip() for v in values_str.split(',')]
                        df = df[~df[col].astype(str).isin(values)]
        return df

    def _evaluate_range(self, data: pd.Series, criteria: str) -> Tuple[str, str]:
        """Evaluate range criteria"""
        try:
            if criteria.startswith('[') and criteria.endswith(']'):
                bounds = criteria[1:-1].split(',')
                lower, upper = float(bounds[0]), float(bounds[1])
                out_of_range = ((data < lower) | (data > upper)).sum()
            else:
                # Handle comparison operators
                ops = {'>=': lambda x, v: x < v,
                       '<=': lambda x, v: x > v,
                       '>': lambda x, v: x <= v,
                       '<': lambda x, v: x >= v}

                for op, func in ops.items():
                    if op in criteria:
                        value = float(criteria.replace(op, '').strip())
                        out_of_range = func(data, value).sum()
                        break
                else:
                    return 'Fail', f'Invalid criteria format: {criteria}'
        except ValueError:
            return 'Fail', f'Invalid numeric value in criteria: {criteria}'

        status = 'Pass' if out_of_range == 0 else 'Fail'
        detail = f"Out of range count: {out_of_range}/{len(data)}"
        return status, detail

    def _check_option_param(self, row: pd.Series):
        """Special handling for Option_Param"""
        tab = row['Tab Name']
        field = row['Field Name']
        rule_tab = row['Rule Tab']

        check_data = self._get_field_data(tab, field)
        rule_df = self._get_data(rule_tab)

        if check_data is None or rule_df is None or 'Option' not in rule_df.columns:
            self._add_result('Check_Category', tab, field, 'Fail',
                             'Column not found', check_type=row['Check Type'])
            return

        # Get all unique values for detailed reporting
        unique_values = sorted(check_data.dropna().unique())

        # Calculate distinct count
        distinct_count = check_data.dropna().nunique()
        if 'quarter' in field.lower():
            distinct_count = distinct_count / 4

        # Get expected value
        expected = pd.to_numeric(rule_df['Option'], errors='coerce').dropna()
        if len(expected) == 0:
            self._add_result('Check_Category', tab, field, 'Fail',
                             'No valid rule values', check_type=row['Check Type'])
            return

        expected_count = expected.iloc[0]
        status = 'Pass' if distinct_count == expected_count else 'Fail'

        # Create detailed description
        detail = f"Rule expects {expected_count} distinct values, Check has {distinct_count:.1f} distinct values. "
        detail += f"Check values: {unique_values}"

        if 'quarter' in field.lower():
            detail += " (Note: count divided by 4 for quarterly data)"

        self._add_result('Check_Category', tab, field, status,
                         detail, check_type=row['Check Type'])

    def _check_rating(self, row: pd.Series):
        """Special handling for rating fields"""
        check_type = row['Check Type']
        tab = row['Tab Name']
        field = row['Field Name']
        rule_tab = row['Rule Tab']
        rule_field = row['Rule Field']

        check_df = self._get_data(tab)
        rule_df = self._get_data(rule_tab)

        if check_df is None or rule_df is None:
            self._add_result('Check_Category', tab, field,
                             'Fail', 'Column not found', check_type=check_type)
            return

        # Validate required columns
        required_cols = ['Segment', 'Sub_segment', field]
        if not all(col in check_df.columns for col in required_cols):
            self._add_result('Check_Category', tab, field, 'Fail',
                             'Required columns missing', check_type=check_type)
            return

        if not all(col in rule_df.columns for col in ['Segment', 'Sub_segment', rule_field]):
            self._add_result('Check_Category', tab, field, 'Fail',
                             'Required columns missing in rule', check_type=check_type)
            return

        # Prepare data
        check_df = check_df.copy()
        rule_df = rule_df.copy()

        # Apply exclusions
        if 'Stage' in rule_df.columns:
            rule_df = rule_df[rule_df['Stage'] != 3]

        if 'SICR_Notchdown' in check_df.columns:
            check_df = check_df[check_df['SICR_Notchdown'] != 99]

        check_df['Sub_segment'] = check_df['Sub_segment'].fillna('')
        rule_df['Sub_segment'] = rule_df['Sub_segment'].fillna('')

        # Check by groups
        failed_groups = []
        failed_details = []
        unique_combos = check_df[['Segment', 'Sub_segment']].drop_duplicates()

        for _, combo in unique_combos.iterrows():
            segment, sub_segment = combo['Segment'], combo['Sub_segment']

            mask_check = (check_df['Segment'] == segment) & (
                check_df['Sub_segment'] == sub_segment)
            mask_rule = (rule_df['Segment'] == segment) & (
                rule_df['Sub_segment'] == sub_segment)

            check_values = set(
                check_df.loc[mask_check, field].dropna().unique())
            rule_values = set(
                rule_df.loc[mask_rule, rule_field].dropna().unique())

            if not check_values:
                continue

            group_pass = (check_values == rule_values if check_type == 'Check_CateExact'
                          else check_values.issubset(rule_values))

            if not group_pass:
                group_name = f"{segment}_{sub_segment}" if sub_segment else segment
                failed_groups.append(group_name)

                # Collect specific mismatches
                if check_type == 'Check_CateExact':
                    only_in_check = list(check_values - rule_values)
                    only_in_rule = list(rule_values - check_values)
                    if only_in_check:
                        failed_details.append(
                            f"{group_name}: only in check {only_in_check}")
                    if only_in_rule:
                        failed_details.append(
                            f"{group_name}: only in rule {only_in_rule}")
                else:
                    not_in_rule = list(check_values - rule_values)
                    if not_in_rule:
                        failed_details.append(f"{group_name}: {not_in_rule}")

        # Generate result
        status = 'Pass' if not failed_groups else 'Fail'
        if not failed_groups:
            detail = 'All groups pass'
        else:
            # Calculate total statistics
            all_check_values = set(check_df[field].dropna().unique())
            all_rule_values = set(rule_df[rule_field].dropna().unique())

            detail = f"Rule has {len(all_rule_values)} values, Check has {len(all_check_values)} values. "
            detail += f"Failed groups: {', '.join(failed_groups)}. "

            # Add all specific value mismatches
            if failed_details:
                detail += "Detailed mismatches: " + "; ".join(failed_details)

        # Add exclusion info
        exclusions = []
        if 'Stage' in rule_df.columns:
            exclusions.append("Stage=3")
        if 'SICR_Notchdown' in check_df.columns:
            exclusions.append("SICR_Notchdown=99")
        if exclusions:
            detail += f" (Excl: {', '.join(exclusions)})"

        self._add_result('Check_Category', tab, field, status,
                         detail, check_type=check_type)

    def _check_category_normal(self, row: pd.Series):
        """Normal category check"""
        check_type = row['Check Type']
        tab = row['Tab Name']
        field = row['Field Name']
        rule_tab = row['Rule Tab']
        rule_field = row['Rule Field']

        check_data = self._get_field_data(tab, field)
        rule_data = self._get_field_data(rule_tab, rule_field)

        if check_data is None or rule_data is None:
            self._add_result('Check_Category', tab, field,
                             'Fail', 'Column not found', check_type=check_type)
            return

        check_values = set(check_data.dropna().unique())
        rule_values = set(rule_data.dropna().unique())

        # Start with general statistics
        detail = f"Rule has {len(rule_values)} values, Check has {len(check_values)} values. "

        if check_type == 'Check_CateExact':
            status = 'Pass' if check_values == rule_values else 'Fail'
            if status == 'Pass':
                detail += "All values match exactly."
            else:
                only_in_check = list(check_values - rule_values)
                only_in_rule = list(rule_values - check_values)
                detail_parts = []

                if only_in_check:
                    detail_parts.append(
                        f"<Values only in check>: {only_in_check}")
                if only_in_rule:
                    detail_parts.append(
                        f"<Values only in rule>: {only_in_rule}")

                detail += "; ".join(detail_parts)
        else:  # Check_CateInclude
            status = 'Pass' if check_values.issubset(rule_values) else 'Fail'
            if status == 'Pass':
                detail += 'All check values are included in rule.'
            else:
                not_in_rule = list(check_values - rule_values)
                detail += f"Values not in rule: {not_in_rule}"

        self._add_result('Check_Category', tab, field, status,
                         detail, check_type=check_type)

    def _get_field_data(self, tab_name: str, field_name: str) -> Optional[pd.Series]:
        """Get field data, support compound fields"""
        df = self._get_data(tab_name)
        if df is None:
            return None

        if '+' in field_name:
            fields = [f.strip() for f in field_name.split('+')]
            if all(f in df.columns for f in fields):
                combined = df[fields[0]].astype(str)
                for f in fields[1:]:
                    combined = combined + '_' + df[f].astype(str)
                return combined
        else:
            return df.get(field_name)

    def _add_result(self, category: str, tab: str, field: str, status: str, detail: str,
                    level: str = '', check_type: str = ''):
        """Add check result"""
        self.results.append({
            'Check Category': category,
            'Check Level': level,
            'Check Type': check_type,
            'Tab Name': tab,
            'Field Name': field,
            'Status': status,
            'Detail': detail
        })

    def _generate_report(self) -> str:
        """Generate report with customized column display"""
        df_results = pd.DataFrame(self.results)

        # Define columns to exclude for each check category
        column_exclusions = {
            'Check_Category': ['Check Level'],
            'Check_Completeness': ['Check Level', 'Check Type'],
            'Check_DupMiss': ['Check Level'],
            'Check_Exists': ['Check Type'],
            'Check_Range': ['Check Level'],
            'Check_ScenarioWeightSum': ['Check Level', 'Check Type']
        }

        # Generate summary
        summary = []
        for category in df_results['Check Category'].unique():
            category_df = df_results[df_results['Check Category'] == category]

            # Determine groupby columns
            groupby_cols = ['Check Category']
            excluded_cols = column_exclusions.get(category, [])

            if 'Check Level' not in excluded_cols and category_df['Check Level'].notna().any():
                groupby_cols.append('Check Level')
            if 'Check Type' not in excluded_cols and category_df['Check Type'].notna().any():
                groupby_cols.append('Check Type')

            # Group and calculate stats
            for key, group in category_df.groupby(groupby_cols):
                total = len(group)
                fail = (group['Status'] == 'Fail').sum()
                pass_ = (group['Status'] == 'Pass').sum()

                summary_row = {
                    'Check Category': key[0] if isinstance(key, tuple) else key,
                    'Total Checks': total,
                    'Fail': fail,
                    'Pass': pass_,
                    'Pass %': f"{pass_/total:.1%}" if total > 0 else "0.0%"
                }

                if len(groupby_cols) > 1:
                    for i, col in enumerate(groupby_cols[1:], 1):
                        summary_row[col] = key[i]

                summary.append(summary_row)

        # Output to Excel
        output_path = os.path.join(
            self.outReportPath,
            f'data_health_check_report_{self.snp_yymm}.xlsx'
        )

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_df = pd.DataFrame(summary)
            col_order = ['Check Category']
            if 'Check Level' in summary_df.columns:
                col_order.append('Check Level')
            if 'Check Type' in summary_df.columns:
                col_order.append('Check Type')
            col_order.extend(['Total Checks', 'Fail', 'Pass', 'Pass %'])

            summary_df = summary_df[col_order]
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

            # Failed checks for each category
            for category in df_results['Check Category'].unique():
                failed = df_results[(df_results['Check Category'] == category) &
                                    (df_results['Status'] == 'Fail')].copy()

                if len(failed) > 0:
                    # Remove excluded columns
                    excluded_cols = column_exclusions.get(category, [])
                    columns_to_keep = [col for col in failed.columns
                                       if col != 'Check Category' and col not in excluded_cols]

                    # Keep only non-empty columns
                    columns_to_keep = [col for col in columns_to_keep
                                       if failed[col].notna().any() or col in ['Tab Name', 'Field Name', 'Status', 'Detail']]

                    failed = failed[columns_to_keep]
                    failed.to_excel(writer, sheet_name=category, index=False)

        print(f"Report generated: {output_path}")
        return output_path
