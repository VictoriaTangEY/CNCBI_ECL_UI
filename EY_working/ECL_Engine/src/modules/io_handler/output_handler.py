import pandas as pd
import os
import json
from pathlib import Path


class Config:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            config = json.load(f)
        self.input_param_path = config['input_param_path']
        self.input_merge_path = config['input_merge_path']
        self.output_data_path = config['output_data_path']
        self.log_path = config['log_path']
        self.reporting_date = config['reporting_date']


class OutputHandler:
    def __init__(self, config=None):
        self.config = config or Config()
        self.ecl_columns = [
            'ecl_hke_m_base', 'ecl_hke_m_benign', 'ecl_hke_m_final',
            'ecl_hke_m_medium', 'ecl_hke_m_mild', 'ecl_hke_m_severe'
        ]
        self.param_tables = {}
    
    def _load_param_file(self):
        """Load CNCBI ECL engine param table"""
        for filename in os.listdir(self.config.input_param_path):
            if 'CNCBI ECL engine param table' in filename and filename.endswith('.xlsx'):
                filepath = os.path.join(self.config.input_param_path, filename)
                try:
                    xls = pd.ExcelFile(filepath)
                    for sheet_name in ['chart_of_accounts_param', 'c800_product_param', 'interco_cd_param']:
                        if sheet_name in xls.sheet_names:
                            df_raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
                            
                            if df_raw.shape[0] >= 4 and df_raw.shape[1] >= 2:
                                col_names = df_raw.iloc[0, 1:].dropna().values
                                data_df = df_raw.iloc[4:, 1:len(col_names)+1].copy()
                                data_df.columns = col_names
                                data_df = data_df.reset_index(drop=True)
                                
                                data_df.columns = data_df.columns.str.lower()
                                self.param_tables[sheet_name] = data_df
                            else:
                                self.param_tables[sheet_name] = pd.DataFrame()
                                
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
    
    def _load_final_ecl(self):
        """Load final_ecl.csv"""
        filepath = os.path.join(self.config.output_data_path, 'final_ecl.csv')
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            return df
        return None
    
    def _standardize_headers(self, df):
        """Convert all column names to lowercase"""
        df.columns = df.columns.str.lower()
        return df
    
    def _add_million_columns(self, df):
        """Add million unit columns for specified ECL columns"""
        for col in self.ecl_columns:
            col_lower = col.lower()
            if col_lower in df.columns:
                df[f'{col_lower}_million'] = df[col_lower] / 1_000_000
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
        condition_fields = ['entity', 'cust_id', 'remarks', 'resd_country_cd', 'country_of_risk']
        
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
    
    def _save_csv(self, df, filename):
        """Save dataframe to csv"""
        filepath = os.path.join(self.config.output_data_path, filename)
        df.to_csv(filepath, index=False)
        print(f"Saved: {filename}")
    
    def process_final_ecl(self):
        """Process final_ecl.csv with all transformations"""
        # Load data
        df = self._load_final_ecl()
        if df is None:
            print("final_ecl.csv not found")
            return
        
        # Load parameter tables
        self._load_param_file()
        
        # 1. Standardize headers
        df = self._standardize_headers(df)
        
        # 2. Add million columns
        df = self._add_million_columns(df)
        
        # 3. Add c800 column
        if 'deal_type' in df.columns and 'chart_of_accounts_param' in self.param_tables:
            chart_df = self.param_tables['chart_of_accounts_param']
            df['c800'] = df['deal_type'].apply(lambda x: self._get_c800(x, chart_df) if pd.notna(x) else None)
        else:
            df['c800'] = None
        
        # 4. Add product column
        if 'c800_product_param' in self.param_tables:
            product_df = self.param_tables['c800_product_param']
            df['product'] = df['c800'].apply(lambda x: self._get_product(x, product_df))
        else:
            df['product'] = None
        
        # 5. Add interco_cd column
        if 'interco_cd_param' in self.param_tables:
            interco_df = self.param_tables['interco_cd_param']
            df['interco_cd'] = df.apply(lambda row: self._get_interco_cd(row, interco_df), axis=1)
        else:
            df['interco_cd'] = None
        
        # Save processed file
        self._save_csv(df, 'final_ecl.csv')
        return df

    
    def run(self):
        """Execute main processing flow"""
        try:
            print("Starting data processing")
            
            # Process final_ecl.csv
            self.process_final_ecl()
            
            print("Data processing completed")
            
        except Exception as e:
            print(f"Error during processing: {str(e)}")
            raise