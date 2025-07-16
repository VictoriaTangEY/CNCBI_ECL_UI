import pandas as pd
from modules.ecl_calculator.ead_layer_3 import BaseRepayment


class OffBalEAD:
    def __init__(self, context, param):
        self.context = context
        self.param = param
        self.rpt_date = context.data_yymm

    def run(self, off_df_deal, off_df_fac):
        # get ccf
        off_df_deal = self.ccf_calculation(self.param, off_df_deal, 'deal_id')
        off_df_fac = self.ccf_calculation(
            self.param, off_df_fac, 'facility_nr')

        # calc ead
        off_df_deal = self.ead_calculation(off_df_deal, 'prin_amt_hke')
        off_df_fac = self.ead_calculation(off_df_fac, 'undrawn_amount_hke')

        # gen ead df
        off_ead_df_deal = self.generate_off_ead_df(
            off_df_deal, self.rpt_date, 'deal_id')
        off_ead_df_fac = self.generate_off_ead_df(
            off_df_fac, self.rpt_date, 'facility_nr')

        # concat ead_df and reset index
        off_ead_df = pd.concat([off_ead_df_deal, off_ead_df_fac])
        off_ead_df.reset_index(drop=True, inplace=True)

        return off_ead_df

    def ccf_calculation(self, param: dict, df: pd.DataFrame, key: str):
        """
        Calculate the CCF for the given dataframe.
        """
        df = df.copy()
        ead_param = param['ead_param']
        ccf_param = param['ccf_param']

        # Initialize category column if it doesn't exist
        if 'category' not in df.columns:
            df['category'] = None

        # Check if ead_param has the required columns
        if not ead_param.empty and 'deal_subtype' in ead_param.columns and 'category' in ead_param.columns:
            # Iterate through each deal_subtype in ead_param
            for _, row in ead_param.iterrows():
                deal_subtype = row['deal_subtype']
                category = row['category']

                # Skip if deal_subtype is empty or NaN
                if pd.isna(deal_subtype) or deal_subtype == '':
                    continue

                # Check if key contains the deal_subtype (case-insensitive)
                mask = df[key].str.contains(
                    str(deal_subtype), case=False, na=False)

                # Assign category where key contains the deal_subtype
                df.loc[mask, 'category'] = category

        # Initialize ccf column if it doesn't exist
        if 'ccf' not in df.columns:
            df['ccf'] = None

        # Assign CCF based on category and additional conditions
        if not ccf_param.empty and 'category' in ccf_param.columns and 'ccf' in ccf_param.columns:
            # Iterate through each row in ccf_param
            for _, param_row in ccf_param.iterrows():
                param_category = param_row['category']
                param_ccf = param_row['ccf']

                # Skip if category is empty or NaN
                if pd.isna(param_category) or param_category == '':
                    continue

                # Create mask for category match
                mask = df['category'] == param_category

                # Add additional conditions if they exist in ccf_param
                if 'segment' in ccf_param.columns and not pd.isna(param_row['segment']):
                    mask = mask & (df['segment'] == param_row['segment'])

                if 'sub_segment' in ccf_param.columns and not pd.isna(param_row['sub_segment']):
                    mask = mask & (df['sub_segment'] ==
                                   param_row['sub_segment'])

                if 'life_condition' in ccf_param.columns and not pd.isna(param_row['life_condition']):
                    mask = mask & (df['life_condition'] ==
                                   param_row['life_condition'])

                # Assign CCF where all conditions are satisfied
                df.loc[mask, 'ccf'] = param_ccf

        return df

    def ead_calculation(self, df: pd.DataFrame, expo_col_name: str):
        """
        Calculate the EAD for the given dataframe.
        """
        df = df.copy()
        df['ead'] = df[expo_col_name] * df['ccf']
        return df

    def generate_off_ead_df(self, df: pd.DataFrame, reporting_date: int, key):
        """
        Generate EAD DataFrame for off-balance sheet items.
        Uses BaseRepayment's _generate_ead_dates method to create quarterly EAD dates
        and assigns the calculated EAD value to each date.
        """
        if df.empty:
            return pd.DataFrame()

        # Create a simple BaseRepayment instance to use its _generate_ead_dates method
        base_repayment = BaseRepayment(data_cols={})

        ead_results = []

        for _, row in df.iterrows():
            try:
                # Get required dates from the row
                maturity_date = pd.to_datetime(row['maturity_date_final'])
                reporting_dte = pd.to_datetime(str(reporting_date))
                id_key = row[key]
                calculated_ead = row['ead']  # This is the constant EAD value

                # Generate EAD dates using BaseRepayment's method
                ead_dates = base_repayment._generate_ead_dates(
                    reporting_dte, maturity_date)

                # Create EAD records for each date
                for ead_date in ead_dates:
                    ead_results.append({
                        key: id_key,
                        'snapshot_dt': ead_date.date(),
                        'ead': calculated_ead,
                    })

            except Exception as e:
                print(
                    f"Error processing deal {row.get(key, 'unknown')}: {e}")
                continue

        # Convert to DataFrame
        ead_df = pd.DataFrame(ead_results)

        return ead_df
