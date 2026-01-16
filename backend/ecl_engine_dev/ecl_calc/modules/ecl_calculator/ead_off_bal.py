import pandas as pd
from ecl_calc.modules.ecl_calculator.ead_layer_3 import BaseRepayment


class OffBalEAD:
    def __init__(self, context, param):
        self.context = context
        self.param = param
        self.rpt_date = context.data_yymm

    def run(self, off_df):

        # calc ead using 'prin_amt_hke'
        off_df = self.ead_calculation(off_df, 'prin_amt_hke')

        # gen ead df using 'deal_id'
        off_ead_df = self.generate_off_ead_df(
            off_df, self.rpt_date, 'deal_id')
        off_ead_df.reset_index(drop=True, inplace=True)

        return off_ead_df

    def ead_calculation(self, df: pd.DataFrame, expo_col_name: str):
        """
        Calculate the EAD for the given dataframe.
        """
        df = df.copy()
        # CCF is now applied in the ECL calculation step (step 5.5 in ecl_engine_service.py)
        # to ensure LGD assignment uses pre-CCF EAD values
        # df['ead'] = df[expo_col_name] * df['ccf']
        df['ead'] = df[expo_col_name]
        return df

    def generate_off_ead_df(self, df: pd.DataFrame, reporting_date: int, key):
        """
        Generate EAD DataFrame for off-balance sheet items.
        Uses BaseRepayment's _generate_ead_dates method to create quarterly EAD dates
        and assigns the calculated EAD value to each date.
        EAD is set to 0 at the maturity date since the loan is fully repaid.
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
                    # EAD should be 0 at maturity date (fully repaid)
                    if ead_date.date() == maturity_date.date():
                        ead_value = 0
                    else:
                        ead_value = calculated_ead

                    ead_results.append({
                        key: id_key,
                        'snapshot_dt': ead_date.date(),
                        'ead': ead_value,
                    })

            except Exception as e:
                print(
                    f"Error processing deal {row.get(key, 'unknown')}: {e}")
                continue

        # Convert to DataFrame
        ead_df = pd.DataFrame(ead_results)

        return ead_df
