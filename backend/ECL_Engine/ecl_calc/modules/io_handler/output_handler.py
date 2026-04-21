import pandas as pd
import numpy as np
from ._add_cols import AddColsHandler


class OutputHandler:
    def __init__(self, context):
        """
        Initialize OutputHandler with context

        Args:
            context: Context object containing timestamp_datetime
        """
        self.context = context
        self.add_cols_handler = AddColsHandler()

    def process_general(self, df, output_type=None):
        """
        Process general columns - optimized to minimize memory usage

        Args:
            df (pandas.DataFrame): Input DataFrame
            output_type (str, optional): Type of output - 'coll_df', 'ead_df', 'pwa_ecl_detailed', or 'pwa_ecl_by_deal'
                                        If provided, will filter columns using keep_cols

        Returns:
            pandas.DataFrame: DataFrame with all processing applied
        """
        # Apply all processing functions in sequence without unnecessary copies
        df = self.add_timestamp(df)
        df = self.col_name_lower_case(df)
        df = self.hke_to_million(df)
        # Apply keep_cols if output_type is provided
        if output_type is not None:
            df = self.keep_cols(df, output_type)
        return df

    def process_all(self, df, param, output_type=None):
        """
        Run all processing functions on the DataFrame and return the modified DataFrame
        Optimized to minimize memory usage by avoiding unnecessary copies

        Args:
            df (pandas.DataFrame): Input DataFrame
            param (dict): Parameter dictionary containing lookup tables
            output_type (str, optional): Type of output - 'coll_df', 'ead_df', 'pwa_ecl_detailed', or 'pwa_ecl_by_deal'
                                        If provided, will filter columns using keep_cols

        Returns:
            pandas.DataFrame: DataFrame with all processing applied
        """
        # Create only one copy at the beginning to avoid modifying the original
        df_processed = df.copy()

        # Apply all processing functions in sequence
        df_processed = self.add_timestamp(df_processed)
        df_processed = self.col_name_lower_case(df_processed)
        df_processed = self.hke_to_million(df_processed)
        # Apply add_cols (skip only in test mode)
        if self.context.RUN_MODE in ["test"]:
            print("Skipping add_cols in process_all in test mode")
        else:
            df_processed = self.add_cols_handler.add_cols(df_processed, param)
        # Apply keep_cols if output_type is provided
        if output_type is not None:
            df_processed = self.keep_cols(df_processed, output_type)
        return df_processed

    def add_timestamp(self, df):
        """
        Add timestamp column to DataFrame and return the modified DataFrame

        Args:
            df (pandas.DataFrame): Input DataFrame

        Returns:
            pandas.DataFrame: DataFrame with timestamp column added as the first column
        """
        # Add timestamp column as the first column using timestamp from context
        df.insert(0, 'timestamp', self.context.timestamp_datetime)
        return df

    def col_name_lower_case(self, df):
        """
        Convert all column names to lowercase and return the modified DataFrame

        Args:
            df (pandas.DataFrame): Input DataFrame

        Returns:
            pandas.DataFrame: DataFrame with lowercase column names
        """
        # Convert all column names to lowercase in-place
        df.columns = df.columns.str.lower()
        return df

    def hke_to_million(self, df):
        """
        Convert HKD amount columns to million HKD using vectorized operations
        Only processes columns that contain both 'ecl' and 'hke' in their names
        """
        # Find all columns that contain both 'ecl' and 'hke' in their names
        hke_columns = [
            col for col in df.columns if 'ecl' in col.lower() and 'hke' in col.lower()]

        if hke_columns:
            # Vectorized division for all HKE columns at once
            df[hke_columns] = df[hke_columns] / 1000000

            # Vectorized column renaming
            new_names = {col: col.replace('_hke', '_hke_m')
                         for col in hke_columns}
            df.rename(columns=new_names, inplace=True)

        return df

    def keep_cols(self, df, output_type):
        """
        Keep only specified columns for different interim output types

        Args:
            df (pandas.DataFrame): Input DataFrame
            output_type (str): Type of output - 'coll_df', 'ead_df', 'pwa_ecl_detailed', or 'pwa_ecl_by_deal'

        Returns:
            pandas.DataFrame: DataFrame with only specified columns kept
        """
        # Define columns to keep for each output type
        columns_map = {
            'coll_df': [
                'timestamp',
                'facility_nr',
                'collateral_agreement_type',
                'collateral_agreement_id',
                'collateral_amount_hke',
                'haircut',
                'post_haircut_coll_amt',
                'post_ccf_base_amt_fac_level',
                'allocated_collateral_amount'
            ],
            'ead_df': [
                'timestamp',
                'deal_id',
                'snapshot_dt',
                'prin_rem',
                'accrued_int',
                'ead'
            ],
            'pwa_ecl_detailed': [
                'timestamp',
                'deal_id',
                'nxt_pmt_dt',
                'prin_amt_hke',
                'int_accr_hke',
                'maturity_date_final',
                'remaining_life',
                'snapshot_dt',
                'ead_hke',
                'discount_factor',
                'applied_mpd_benign',
                'applied_mpd_base',
                'applied_mpd_medium',
                'applied_mpd_mild',
                'applied_mpd_severe',
                'applied_lgd_benign',
                'applied_lgd_base',
                'applied_lgd_medium',
                'applied_lgd_mild',
                'applied_lgd_severe',
                'ecl_hke_m',
                'ecl_benign_hke_m',
                'ecl_base_hke_m',
                'ecl_medium_hke_m',
                'ecl_mild_hke_m',
                'ecl_severe_hke_m'
            ],
            'pwa_ecl_by_deal': [
                'timestamp',
                'region_brch',
                'product_type_brch',
                'account_officer',
                'acct_id',
                'amrt_type_cd',
                'as_of_dt',
                'blk_cd',
                'bu',
                'country_of_risk',
                'cur_bal',
                'cur_rt',
                'currency',
                'cust_bk_group',
                'customer_nr',
                'customer_shortname',
                'customer_type',
                'days_pastdue',
                'deal_dt',
                'deal_id',
                'deal_subtype',
                'deal_type',
                'ead_seg',
                'effective_yield',
                'entity',
                'facility_nr',
                'fitch_rating',
                'industry_code',
                'int_accr',
                'int_susp_amt',
                'intrnl_rating',
                'intrnl_rating_model',
                'lgd_risk_region',
                'lgd_risk_seg',
                'loan_class_cd',
                'location',
                'master_scale_rating',
                'maturity_date',
                'moody_rating',
                'multiply_divide_ind',
                'nxt_pmt_dt',
                'on_off_ind',
                'orig_master_scale_rating',
                'pastdue_int',
                'pastdue_prin',
                'pd_seg',
                'pit_pd_seg',
                'pmt_amt',
                'pmt_freq',
                'pmt_freq_multiplier',
                'prin_amt',
                'profit_centre',
                'rate',
                'snp_rating',
                'source_system',
                'stg_asmt_seg',
                'tfi_id',
                'ttc_pd',
                'tu_rating',
                'tu_score',
                'coa_mapping',
                'from_currency',
                'lcy_to_hkd',
                'intercompany',
                'to_currency',
                'source_merged_table',
                'adj_ind',
                'cur_bal_hke',
                'int_accr_hke',
                'int_susp_amt_hke',
                'pmt_amt_hke',
                'prin_amt_hke',
                'on_off_ind_final',
                'segment',
                'sub_segment',
                'final_stage',
                'maturity_date_final',
                'remaining_life',
                'eir',
                'category',
                'ccf',
                'ead_layer',
                'repayment_type',
                'post_ccf_base_amount',
                'post_ccf_base_amt_fac_level',
                'post_ccf_base_amt_deal_pct',
                'facility_allocated_collateral_amt',
                'allocated_collateral_amt',
                'ead_hke',
                'ecl_hke_m',
                'ecl_benign_hke_m',
                'ecl_base_hke_m',
                'ecl_mild_hke_m',
                'ecl_medium_hke_m',
                'ecl_severe_hke_m',
                'applied_mpd_benign_0',
                'applied_mpd_base_0',
                'applied_mpd_mild_0',
                'applied_mpd_medium_0',
                'applied_mpd_severe_0',
                'applied_lgd_benign_0',
                'applied_lgd_base_0',
                'applied_lgd_mild_0',
                'applied_lgd_medium_0',
                'applied_lgd_severe_0',
                'elim',
                'c800',
                'product',
                'interco_cd',
                'class',
                'stage',
                'entity1',
                'entity2',
                'coa_entity',
                'bu1',
                'bu2',
                'bu4',
                'bu3',
                'ceo2',
                'profit_centre_1',
                'coa_prod_gp1',
                'product1',
                'ceo1'
            ]
        }

        # If output_type is not in map or is set to None, return original DataFrame
        if output_type not in columns_map or columns_map[output_type] is None:
            return df

        # Get columns to keep
        cols_to_keep = columns_map[output_type]

        # Find columns that exist in the DataFrame (case-insensitive)
        df_cols_lower = {col.lower(): col for col in df.columns}
        existing_cols = []
        missing_cols = []

        for col in cols_to_keep:
            col_lower = col.lower()
            if col_lower in df_cols_lower:
                existing_cols.append(df_cols_lower[col_lower])
            else:
                missing_cols.append(col)

        # Warn if some columns are missing
        if missing_cols:
            print(
                f"Warning: The following columns are missing in the DataFrame for {output_type}: {missing_cols}")

        # Return DataFrame with only existing columns to keep
        if existing_cols:
            return df[existing_cols].copy()
        else:
            print(
                f"Warning: No matching columns found for {output_type}, returning empty DataFrame")
            return pd.DataFrame()
