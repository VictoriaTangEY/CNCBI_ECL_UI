import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
import warnings
warnings.filterwarnings('ignore')


def load_raw_data_files(context) -> Dict[str, Any]:
    """Load raw data files for post-check using context paths"""
    raw_data = {
        'excel_files': {},
        'csv_files': {}
    }
    
    # Load Excel files (test design) from param path
    param_path = context.paramPath
    for filename in os.listdir(param_path):
        if 'PostCheck testdesign table' in filename and (filename.endswith('.xlsx') or filename.endswith('.xls')):
            filepath = os.path.join(param_path, filename)
            try:
                xl_file = pd.ExcelFile(filepath)
                raw_data['excel_files'][filename] = {}
                for sheet in xl_file.sheet_names:
                    df = pd.read_excel(filepath, sheet_name=sheet, header=None)
                    raw_data['excel_files'][filename][sheet] = df
            except Exception as e:
                print(f"Error reading {filename}: {e}")
    
    # Load CSV files from intermediate data
    interm_path = context.outInterimPath
    csv_files = ['interim_output_ecl_by_deal.csv', 'interim_output_ecl_detailed.csv', 'on_off_df.csv']
    for filename in csv_files:
        filepath = os.path.join(interm_path, filename)
        if os.path.exists(filepath):
            raw_data['csv_files'][filename] = pd.read_csv(filepath)
    
    return raw_data


def process_raw_data(raw_data: Dict[str, Any]) -> Tuple[Dict[str, pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Process raw data with special format handling for post-check"""
    test_designs = {}
    ecl_final_result = None
    ecl_detail_result = None
    exposure_table = None
    
    # Process test design Excel files
    for filename, sheets in raw_data.get('excel_files', {}).items():
        for sheet_name, df_raw in sheets.items():
            if df_raw.shape[0] >= 4 and df_raw.shape[1] >= 2:
                col_names = df_raw.iloc[0, 1:].dropna().values
                data_df = df_raw.iloc[4:, 1:len(col_names)+1].copy()
                data_df.columns = col_names
                data_df = data_df.reset_index(drop=True)
                data_df.columns = data_df.columns.str.lower()
                test_designs[sheet_name] = data_df
            else:
                test_designs[sheet_name] = pd.DataFrame()
    
    # Process CSV files
    csv_data = raw_data.get('csv_files', {})
    
    # ECL final result
    if 'interim_output_ecl_by_deal.csv' in csv_data:
        df = csv_data['interim_output_ecl_by_deal.csv']
        df.columns = df.columns.str.lower()
        ecl_final_result = df
    
    # ECL detail result
    if 'interim_output_ecl_detailed.csv' in csv_data:
        df = csv_data['interim_output_ecl_detailed.csv']
        df.columns = df.columns.str.lower()
        ecl_detail_result = df
    
    # Exposure table
    if 'on_off_df.csv' in csv_data:
        df = csv_data['on_off_df.csv']
        df.columns = df.columns.str.lower()
        exposure_table = df
    
    return test_designs, ecl_final_result, ecl_detail_result, exposure_table


class PostDataHealthCheck:
    """Post-processing data health check class"""
    def __init__(self, context):
        self.context = context
        
        # Load raw data
        raw_data = load_raw_data_files(context)
        test_designs, ecl_final_result, ecl_detail_result, exposure_table = process_raw_data(raw_data)
        
        self.test_design = test_designs
        self.ecl_final_result = ecl_final_result
        self.ecl_detail_result = ecl_detail_result
        self.exposure_table = exposure_table
        self.results = []
        self._table_cache = {}
        
    def run(self) -> str:
        """Execute all post-checks and generate report"""
        # 1. Existence check
        if 'existence_check' in self.test_design:
            self._existence_check(self.test_design['existence_check'])
        
        # 2. ECL check
        if 'ecl_check' in self.test_design:
            self._ecl_check(self.test_design['ecl_check'])
        
        # 3. Consistency checks(hardcode)
        self._consistency_check()
        
        # 4. Range check
        if 'result_range_check' in self.test_design:
            self._range_check(self.test_design['result_range_check'])
        
        # 5. Stage final check(hardcode)
        self._missing_check()
        
        return self._generate_report()
    
    # ==================== Check Functions ====================
    def _existence_check(self, test_design: pd.DataFrame):
        """Check existence of tabs and fields"""
        results = []
        for _, row in test_design.iterrows():
            level = row['check_level']
            tab = row['tab_name']
            field = row.get('field_name', '')
            
            if level == 'Tab Level':
                df = self._get_table_by_name(tab)
                exists = df is not None
                results.append({
                    'check_category': 'existence_check',
                    'check_level': level,
                    'tab_name': tab,
                    'field_name': '',
                    'check_flg': 'Pass' if exists else 'Fail',
                    'deal_ids': '',
                    'fail_detail': 'Tab exists' if exists else 'Tab not found',
                    'handling': row.get('handling', ''),
                    'check_type': ''
                })
            else:
                df = self._get_table_by_name(tab)
                if df is None:
                    results.append({
                        'check_category': 'existence_check',
                        'check_level': level,
                        'tab_name': tab,
                        'field_name': field,
                        'check_flg': 'Fail',
                        'deal_ids': '',
                        'fail_detail': 'Tab not found',
                        'handling': row.get('handling', ''),
                        'check_type': ''
                    })
                else:
                    exists = field in df.columns
                    results.append({
                        'check_category': 'existence_check',
                        'check_level': level,
                        'tab_name': tab,
                        'field_name': field,
                        'check_flg': 'Pass' if exists else 'Fail',
                        'deal_ids': '',
                        'fail_detail': 'Field exists' if exists else 'Field not found',
                        'handling': row.get('handling', ''),
                        'check_type': ''
                    })
        
        self.results.extend(results)
                    
    def _ecl_check(self, test_design: pd.DataFrame):
        """ECL range check based on test design"""
        for _, row in test_design.iterrows():
            tab = row['tab_name']
            field = row['field_name']
            criteria = row.get('criteria', '')
            
            df = self._get_table_by_name(tab)
            if df is None or field not in df.columns:
                error_detail = 'Tab not found' if df is None else 'Field not found'
                self._record_check_result('ecl_check', tab, field, 'Fail', error_detail,
                                        handling=row.get('handling', ''))
                continue
            
            values = pd.to_numeric(df[field], errors='coerce')
            valid_mask = values.notna()
            
            if not valid_mask.any():
                continue
            
            status, detail, out_of_range_mask = self._evaluate_range_vectorized(values[valid_mask], criteria)

            if status == 'Fail' and 'deal_id' in df.columns:
                fail_indices = df.index[valid_mask][out_of_range_mask]
                failed_df = df.loc[fail_indices]
                failed_values = values.loc[fail_indices]
                
                fail_results = pd.DataFrame({
                    'check_category': 'ecl_check',
                    'check_level': '',
                    'tab_name': tab,
                    'field_name': field,
                    'check_flg': 'Fail',
                    'deal_ids': failed_df['deal_id'].astype(str),
                    'fail_detail': failed_values.apply(lambda x: f"Out of expected range ({criteria}), fail value: {x}"),
                    'handling': row.get('handling', '')
                })
                
                self.results.extend(fail_results.to_dict('records'))
            elif status == 'Fail':
                fail_value = values[valid_mask][out_of_range_mask].iloc[0] if out_of_range_mask.any() else 'N/A'
                self._record_check_result('ecl_check', tab, field, 'Fail', 
                                        f"Out of expected range ({criteria}), fail value: {fail_value}",
                                        handling=row.get('handling', ''))
            else:
                self._record_check_result('ecl_check', tab, field, 'Pass', 'All values in range',
                                        handling=row.get('handling', ''))
                
    def _consistency_check(self):
        """Check data consistency between final output and exposure table"""
        # Load stage_3_df for complete validation
        stage_3_df = None
        stage_3_path = os.path.join(self.context.outInterimPath, 'stage_3_df.csv')
        if os.path.exists(stage_3_path):
            stage_3_df = pd.read_csv(stage_3_path)
            stage_3_df.columns = stage_3_df.columns.str.lower()
        
        if self.exposure_table is None:
            self.results.append({
                'check_category': 'data_consistency_check',
                'check_type': 'N/A',
                'check_flg': 'Fail',
                'deal_ids': '',
                'fail_detail': 'Preprocessed exposure table not found'
            })
            return
        
        if self.ecl_final_result is None:
            self.results.append({
                'check_category': 'data_consistency_check',
                'check_type': 'N/A',
                'check_flg': 'Fail',
                'deal_ids': '',
                'fail_detail': 'ECL final result not found'
            })
            return
        
        # Deal ID consistency check - include stage_3
        output_ids = set(self.ecl_final_result['deal_id'].dropna())
        exposure_ids = set(self.exposure_table['deal_id'].dropna())
        
        # Add stage_3 deal_ids
        if stage_3_df is not None and 'deal_id' in stage_3_df.columns:
            exposure_ids.update(stage_3_df['deal_id'].dropna())
        
        missing_ids = exposure_ids - output_ids
        extra_ids = output_ids - exposure_ids
        
        if missing_ids:
            missing_results = pd.DataFrame({
                'check_category': 'data_consistency_check',
                'check_type': 'deal_id_consistency_check',
                'check_flg': 'Fail',
                'deal_ids': list(missing_ids),
                'fail_detail': 'DEAL_ID missing in final ECL result'
            })
            self.results.extend(missing_results.to_dict('records'))
                    
        if extra_ids:
            extra_results = pd.DataFrame({
                'check_category': 'data_consistency_check',
                'check_type': 'deal_id_consistency_check',
                'check_flg': 'Fail',
                'deal_ids': list(extra_ids),
                'fail_detail': 'DEAL_ID missing in preprocessed exposure table'
            })
            self.results.extend(extra_results.to_dict('records'))
                    
        if not missing_ids and not extra_ids:
            self.results.append({
                'check_category': 'data_consistency_check',
                'check_type': 'deal_id_consistency_check',
                'check_flg': 'Pass',
                'deal_ids': '',
                'fail_detail': 'All deal_id match'
            })
        
        # Balance consistency checks
        consistency_checks = {
            'current_balance_consistency_check': ('cur_bal_hke_m', 'cur_bal_hke'),  
            'accural_interest_consistency_check': ('int_accr_hke_m', 'int_accr_hke')  
        }

        for check_name, (output_field, exposure_field) in consistency_checks.items():
            if output_field not in self.ecl_final_result.columns:
                self.results.append({
                    'check_category': 'data_consistency_check',
                    'check_type': check_name,
                    'check_flg': 'Fail',
                    'deal_ids': '',
                    'fail_detail': f'{output_field} not found in ECL final result'
                })
                continue
            
            # Combine exposure and stage_3 data for validation
            exposure_data = []
            
            if exposure_field in self.exposure_table.columns:
                exposure_data.append(self.exposure_table[['deal_id', exposure_field]])
            
            if stage_3_df is not None and exposure_field in stage_3_df.columns:
                exposure_data.append(stage_3_df[['deal_id', exposure_field]])
            
            if not exposure_data:
                self.results.append({
                    'check_category': 'data_consistency_check',
                    'check_type': check_name,
                    'check_flg': 'Fail',
                    'deal_ids': '',
                    'fail_detail': f'{exposure_field} not found'
                })
                continue
            
            # Merge all exposure data
            exposure_df_temp = pd.concat(exposure_data, ignore_index=True)
            exposure_df_temp[exposure_field] = exposure_df_temp[exposure_field] / 1_000_000
            
            merged = pd.merge(
                self.ecl_final_result[['deal_id', output_field]],
                exposure_df_temp,
                on='deal_id',
                how='inner'
            )
            
            merged = merged.fillna(0)
            diff_mask = abs(merged[output_field] - merged[exposure_field]) > 0
            
            if diff_mask.any():
                failed_df = merged[diff_mask]
                
                fail_results = []
                for _, row in failed_df.iterrows():
                    fail_results.append({
                        'check_category': 'data_consistency_check',
                        'check_type': check_name,
                        'check_flg': 'Fail',
                        'deal_ids': str(row['deal_id']),
                        'fail_detail': f"Field value mismatch between final ECL result and preprocessed exposure table：{row[output_field]} (final ecl table)/{row[exposure_field]} (preprocessed exposure table)"
                    })
                self.results.extend(fail_results)
            else:
                self.results.append({
                    'check_category': 'data_consistency_check',
                    'check_type': check_name,
                    'check_flg': 'Pass',
                    'deal_ids': '',
                    'fail_detail': 'All values match'
                })
    
    def _range_check(self, test_design: pd.DataFrame):
        """Range check based on result_range_check test design"""
        for _, row in test_design.iterrows():
            tab = row['tab_name']
            field = row['field_name']
            criteria = row.get('criteria', '')
            
            df = self._get_table_by_name(tab)
            if df is None or field not in df.columns:
                error_detail = 'Tab not found' if df is None else 'Field not found'
                self._record_check_result('result_range_check', tab, field, 'Fail', error_detail,
                                        handling=row.get('handling', ''))
                continue
            
            values = pd.to_numeric(df[field], errors='coerce')
            valid_mask = values.notna()
            
            if not valid_mask.any():
                continue
            
            status, detail, out_of_range_mask = self._evaluate_range_vectorized(values[valid_mask], criteria)
            
            if status == 'Fail' and 'deal_id' in df.columns:
                fail_indices = df.index[valid_mask][out_of_range_mask]
                failed_df = df.loc[fail_indices]
                failed_values = values.loc[fail_indices]
                
                fail_results = pd.DataFrame({
                    'check_category': 'result_range_check',
                    'check_level': '',
                    'tab_name': tab,
                    'field_name': field,
                    'check_flg': 'Fail',
                    'deal_ids': failed_df['deal_id'].astype(str),
                    'fail_detail': failed_values.apply(lambda x: f"Out of expected range ({criteria}), fail value: {x}"),
                    'handling': row.get('handling', '')
                })
                
                self.results.extend(fail_results.to_dict('records'))
            elif status == 'Fail':
                fail_value = values[valid_mask][out_of_range_mask].iloc[0] if out_of_range_mask.any() else 'N/A'
                self._record_check_result('result_range_check', tab, field, 'Fail', 
                                        f"Out of expected range ({criteria}), fail value: {fail_value}",
                                        handling=row.get('handling', ''))
            else:
                self._record_check_result('result_range_check', tab, field, 'Pass', 'All values in range',
                                        handling=row.get('handling', ''))
    
    def _missing_check(self):
        """Check if final_stage column and ECL fields have null values"""
        # Check if ECL final result table exists
        if self.ecl_final_result is None:
            self._record_check_result('missing_check', 'interim_output_ecl_by_deal', 'final_stage', 
                                    'Fail', 'ECL final result not found')
            return
        
        table_name = 'interim_output_ecl_by_deal'
        
        # Check final_stage field for null values
        if 'final_stage' in self.ecl_final_result.columns:
            null_mask = self.ecl_final_result['final_stage'].isna() | (self.ecl_final_result['final_stage'].astype(str).str.strip() == '')
            
            if null_mask.any() and 'deal_id' in self.ecl_final_result.columns:
                # Record each deal_id with missing final_stage
                null_df = self.ecl_final_result[null_mask]
                null_results = pd.DataFrame({
                    'check_category': 'missing_check',
                    'check_level': '',
                    'tab_name': table_name,
                    'field_name': 'final_stage',
                    'check_flg': 'Fail',
                    'deal_ids': null_df['deal_id'].astype(str),
                    'fail_detail': 'Stage missing',
                    'handling': ''
                })
                self.results.extend(null_results.to_dict('records'))
            elif null_mask.any():
                # No deal_id column, record general failure
                self._record_check_result('missing_check', table_name, 'final_stage', 
                                        'Fail', 'Stage missing')
            else:
                # All final_stage values are present
                self._record_check_result('missing_check', table_name, 'final_stage', 
                                        'Pass', 'No null values in final_stage column')
        else:
            # final_stage field not found in table
            self._record_check_result('missing_check', table_name, 'final_stage', 
                                    'Fail', 'Field not found')
        
        # Hardcode ECL fields check
        ecl_fields = ['ecl_final_hke_m', 'ecl_benign_hke_m', 'ecl_base_hke_m', 
                    'ecl_mild_hke_m', 'ecl_medium_hke_m', 'ecl_severe_hke_m']
        
        for field in ecl_fields:
            if field in self.ecl_final_result.columns:
                # Check for NaN or empty string values
                null_mask = self.ecl_final_result[field].isna() | (self.ecl_final_result[field].astype(str).str.strip() == '')
                
                if null_mask.any() and 'deal_id' in self.ecl_final_result.columns:
                    # Record each deal_id with missing ECL field value
                    null_df = self.ecl_final_result[null_mask]
                    null_results = pd.DataFrame({
                        'check_category': 'missing_check',
                        'check_level': '',
                        'tab_name': table_name,
                        'field_name': field,
                        'check_flg': 'Fail',
                        'deal_ids': null_df['deal_id'].astype(str),
                        'fail_detail': f"{field} missing",
                        'handling': ''
                    })
                    self.results.extend(null_results.to_dict('records'))
                elif null_mask.any():
                    # No deal_id column, record general failure
                    self._record_check_result('missing_check', table_name, field, 
                                            'Fail', f"{field} missing")
                else:
                    # All values are present for this ECL field
                    self._record_check_result('missing_check', table_name, field, 
                                            'Pass', f'No null values in {field} column')

    # ==================== Helper Functions ====================
    def _get_table_by_name(self, tab_name: str) -> Optional[pd.DataFrame]:
        """Get table data by name - dynamically load from available paths"""
        tab_base = tab_name.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')
        
        # Check if it's already loaded in memory
        if tab_base == 'interim_output_ecl_by_deal' and self.ecl_final_result is not None:
            return self.ecl_final_result
        elif tab_base == 'interim_output_ecl_detailed' and self.ecl_detail_result is not None:
            return self.ecl_detail_result
        elif tab_base == 'on_off_df' and self.exposure_table is not None:
            return self.exposure_table
        
        if tab_base in self._table_cache:
            return self._table_cache[tab_base]
        
        search_paths = [
            self.context.outInterimPath,
            self.context.inDataPath,
            self.context.outDataPath,
            self.context.paramPath
        ]
        
        for path in search_paths:
            if not os.path.exists(path):
                continue
                
            csv_path = os.path.join(path, f"{tab_base}.csv")
            if os.path.exists(csv_path):
                try:
                    df = pd.read_csv(csv_path)
                    df.columns = df.columns.str.lower()
                    self._table_cache[tab_base] = df
                    return df
                except Exception as e:
                    print(f"Error reading {csv_path}: {e}")
            
            for ext in ['.xlsx', '.xls']:
                excel_path = os.path.join(path, f"{tab_base}{ext}")
                if os.path.exists(excel_path):
                    try:
                        df = pd.read_excel(excel_path)
                        df.columns = df.columns.str.lower()
                        self._table_cache[tab_base] = df
                        return df
                    except Exception as e:
                        print(f"Error reading {excel_path}: {e}")
        
        return None    

    def _evaluate_range_vectorized(self, data: pd.Series, criteria: str) -> Tuple[str, str, pd.Series]:
        try:
            if criteria.startswith('[') and criteria.endswith(']'):
                bounds = criteria[1:-1].split(',')
                lower, upper = float(bounds[0]), float(bounds[1])
                out_of_range_mask = (data < lower) | (data > upper)
            elif '>=' in criteria:
                value = float(criteria.replace('>=', '').strip())
                out_of_range_mask = data < value
            elif '<=' in criteria:
                value = float(criteria.replace('<=', '').strip())
                out_of_range_mask = data > value
            elif '>' in criteria:
                value = float(criteria.replace('>', '').strip())
                out_of_range_mask = data <= value
            elif '<' in criteria:
                value = float(criteria.replace('<', '').strip())
                out_of_range_mask = data >= value
            else:
                return 'Fail', f'Invalid criteria format: {criteria}', pd.Series([True] * len(data), index=data.index)
        except ValueError:
            return 'Fail', f'Invalid numeric value in criteria: {criteria}', pd.Series([True] * len(data), index=data.index)
        
        if out_of_range_mask.any():
            return 'Fail', f'Values out of range {criteria}', out_of_range_mask
        else:
            return 'Pass', 'All values in range', out_of_range_mask
    
    def _record_check_result(self, category: str, tab: str, field: str, status: str, 
                        detail: str, level: str = '', handling: str = '', deal_ids: List[str] = None):
        """Record check result"""
        self.results.append({
            'check_category': category,
            'check_level': level,
            'tab_name': tab,
            'field_name': field,
            'check_flg': status,
            'deal_ids': ', '.join(deal_ids) if deal_ids else '', 
            'fail_detail': detail,
            'handling': handling,
            'check_type': ''
        })

    # ==================== Report Generation ====================
    def _generate_report(self) -> str:
        """Generate Excel report with check results"""
        df_results = pd.DataFrame(self.results)
        
        sheet_columns = {
            'ecl_check': ['tab_name', 'field_name', 'check_flg', 'deal_ids', 'fail_detail', 'handling'],
            'data_consistency_check': ['check_type', 'check_flg', 'deal_ids', 'fail_detail'],
            'result_range_check': ['tab_name', 'field_name', 'check_flg', 'deal_ids', 'fail_detail', 'handling'],
            'missing_check': ['tab_name', 'field_name', 'check_flg', 'deal_ids', 'fail_detail'],
            'existence_check': ['check_level', 'tab_name', 'field_name', 'check_flg', 'handling']
        }
        
        output_path = os.path.join(
            self.context.outReportPath,
            f'post_data_health_check_report_{self.context.data_yymm}.xlsx'
        )
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Generate postruntestdesc summary if exists
            if 'postruntestdesc' in self.test_design:
                test_desc = self.test_design['postruntestdesc'].copy()
                
                result_flags = []
                for test_name in test_desc['post_run_validation_test']:
                    if test_name in ['deal_id_consistency_check', 'current_balance_consistency_check', 
                                    'accural_interest_consistency_check']:
                        if 'check_type' in df_results.columns:
                            mask = (df_results['check_category'] == 'data_consistency_check') & \
                                (df_results['check_type'].fillna('') == test_name)
                        else:
                            mask = pd.Series([False] * len(df_results))
                    else:
                        mask = df_results['check_category'] == test_name
                    
                    test_results = df_results[mask]
                    
                    if len(test_results) == 0:
                        result_flag = 'Pass'
                    elif (test_results['check_flg'] == 'Fail').any():
                        result_flag = 'Fail'
                    else:
                        result_flag = 'Pass'
                    
                    result_flags.append(result_flag)
                
                test_desc['result_flag'] = result_flags
                
                # Calculate summary statistics - include stage_3
                stage_3_df = None
                stage_3_path = os.path.join(self.context.outInterimPath, 'stage_3_df.csv')
                if os.path.exists(stage_3_path):
                    stage_3_df = pd.read_csv(stage_3_path)
                    stage_3_df.columns = stage_3_df.columns.str.lower()
                
                # Deal count
                input_deal_count = len(self.exposure_table['deal_id'].dropna()) if self.exposure_table is not None else 0
                if stage_3_df is not None and 'deal_id' in stage_3_df.columns:
                    input_deal_count += len(stage_3_df['deal_id'].dropna())
                
                output_deal_count = len(self.ecl_final_result['deal_id'].dropna()) if self.ecl_final_result is not None else 0
                
                # Current balance sum
                input_cur_bal_sum = 0
                if self.exposure_table is not None and 'cur_bal_hke' in self.exposure_table.columns:
                    input_cur_bal_sum = self.exposure_table['cur_bal_hke'].sum() / 1_000_000
                if stage_3_df is not None and 'cur_bal_hke' in stage_3_df.columns:
                    input_cur_bal_sum += stage_3_df['cur_bal_hke'].sum() / 1_000_000
                
                output_cur_bal_sum = self.ecl_final_result['cur_bal_hke_m'].sum() if self.ecl_final_result is not None and 'cur_bal_hke_m' in self.ecl_final_result.columns else 0

                # Accrued interest sum
                input_accr_int_sum = 0
                if self.exposure_table is not None and 'int_accr_hke' in self.exposure_table.columns:
                    input_accr_int_sum = self.exposure_table['int_accr_hke'].sum() / 1_000_000
                if stage_3_df is not None and 'int_accr_hke' in stage_3_df.columns:
                    input_accr_int_sum += stage_3_df['int_accr_hke'].sum() / 1_000_000
                
                output_accr_int_sum = self.ecl_final_result['int_accr_hke_m'].sum() if self.ecl_final_result is not None and 'int_accr_hke_m' in self.ecl_final_result.columns else 0
                
                # Create new summary rows
                summary_rows = pd.DataFrame([
                    {
                        'post_run_validation_test': 'deal_id_count',
                        'remark': f'input(preprocessed exposure table): {input_deal_count:,}, output(final ecl table): {output_deal_count:,}'
                    },
                    {
                        'post_run_validation_test': 'value_sum',
                        'remark': f'input(preprocessed exposure table) cur_bal_hke(m): {input_cur_bal_sum:,.2f}, output(final ecl table) cur_bal_hke(m): {output_cur_bal_sum:,.2f}/ input(preprocessed exposure table) accr_int_hke(m): {input_accr_int_sum:,.2f}, output(final ecl table) accr_int_hke(m): {output_accr_int_sum:,.2f}'
                    }
                ])
                
                # Add other columns from test_desc to summary_rows if they exist
                for col in test_desc.columns:
                    if col not in ['post_run_validation_test', 'remark']:
                        summary_rows[col] = ''
                
                # Append summary rows to test_desc
                test_desc = pd.concat([test_desc, summary_rows], ignore_index=True)
                
                priority_cols = ['post_run_validation_test', 'result_flag', 'remark']
                other_cols = [col for col in test_desc.columns if col not in priority_cols]
                ordered_cols = [col for col in priority_cols if col in test_desc.columns] + other_cols
                
                test_desc[ordered_cols].to_excel(writer, sheet_name='postruntestdesc', index=False)
            
            # Write failed checks for each category
            for category, columns in sheet_columns.items():
                category_results = df_results[df_results['check_category'] == category]
                
                if len(category_results) > 0:
                    failed = category_results[category_results['check_flg'] == 'Fail']
                    
                    if len(failed) > 0:
                        cols = [col for col in columns if col in failed.columns]
                        failed[cols].to_excel(writer, sheet_name=category, index=False)
        
        print(f"Report generated: {output_path}")
        return output_path