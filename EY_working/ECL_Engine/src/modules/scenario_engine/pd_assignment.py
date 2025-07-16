import pandas as pd
import numpy as np
from typing import Dict, Optional


class PDAssignmentFramework:
    def __init__(self,
                 param: dict,
                 cf_table: pd.DataFrame,
                 loan_table: pd.DataFrame,
                 data_cols: Optional[Dict[str, str]] = None):
        self.cf_table = cf_table.copy()
        self.loan_table = loan_table.copy()
        self.data_cols = data_cols or {
            'deal_id': 'deal_id',
            'mat_dt': 'maturity_date_final',
            'payment_dt': 'snapshot_dt'
        }
        self.scenario_param = param['scenario_weight_param']
        self.mpd_param = param['pd_param']

    def process_all(self) -> pd.DataFrame:
        self._calculate_quarter_life()
        self._calculate_payment_term()
        self._map_pd()
        self._pd_adjustment()

        return self.cf_table

    def _calculate_quarter_life(self) -> pd.DataFrame:
        """Calculate remaining life in the quarter for PD assignment"""
        self._map_maturity_date()
        self._convert_date_columns()
        self._calculate_RL_in_the_quarter()
        return self.cf_table

    def _map_maturity_date(self):
        """
        Map maturity dates from loan table to cash flow table while preserving datetime type

        Steps:
        1. Ensure source column in loan table is datetime
        2. Perform left join on deal_id
        3. Copy datetime column directly to maintain type
        """
        # Convert source column to datetime
        self.loan_table[self.data_cols['mat_dt']] = pd.to_datetime(
            self.loan_table[self.data_cols['mat_dt']],
            format='%m/%d/%Y',
            errors='coerce'  # Convert invalid dates to NaT
        )

        # Merge tables
        merged = pd.merge(
            self.cf_table,
            self.loan_table,
            left_on=[self.data_cols['deal_id']],
            right_on=[self.data_cols['deal_id']],
            how='left'
        )

        # Preserve datetime type during assignment
        self.cf_table[self.data_cols['mat_dt']
                      ] = merged[self.data_cols['mat_dt']]

        return self.cf_table

    def _convert_date_columns(self):
        """
        Convert date columns to datetime64[ns] type

        Currently only processes payment date column (snapshot_dt)
        Uses coercive conversion (invalid → NaT)
        """
        for col in [self.data_cols['payment_dt']]:
            self.cf_table[col] = pd.to_datetime(
                self.cf_table[col],
                format='%m/%d/%Y',  # Explicit format matching
                errors='coerce'       # Force invalid to NaT
            ).astype('datetime64[ns]')  # Ensure precise datetime type

        return self.cf_table

    def _calculate_RL_in_the_quarter(self) -> pd.DataFrame:
        """
        Calculate remaining life in the quarter

        Logic:
        1. If payment date == maturity date → 0
        2. If next quarter date > maturity date → remaining_days/90
        3. Else → 1 (full quarter remaining)
        """
        # Ensure datetime type
        payment_dates = self.cf_table[self.data_cols['payment_dt']]
        maturity_dates = self.cf_table[self.data_cols['mat_dt']]

        # Calculate next quarter date
        next_quarter_dates = payment_dates + pd.offsets.DateOffset(months=3)

        # Calculate days between dates
        remaining_days = (maturity_dates - payment_dates).dt.days

        # Conditional calculation
        self.cf_table['remaining_life_of_the_quarter'] = np.where(
            payment_dates == maturity_dates,  # Case 1
            0,
            np.where(
                next_quarter_dates > maturity_dates,  # Case 2
                remaining_days / 90,  # Fractional quarter
                1  # Case 3 (full quarter)
            )
        )

        return self.cf_table

    def _calculate_payment_term(self) -> pd.DataFrame:
        """Calculate payment term sequence for each deal"""
        self.cf_table = self.cf_table.sort_values(
            [self.data_cols['deal_id'], self.data_cols['payment_dt']])
        self.cf_table['term'] = self.cf_table.groupby(
            self.data_cols['deal_id']).cumcount() + 1

        return self.cf_table

    def _map_pd(self) -> pd.DataFrame:
        """Map MPD values for scenarios"""
        # First merge with loan table
        merged_1 = pd.merge(
            self.cf_table,
            self.loan_table[['deal_id', 'segment',
                             'sub_segment', 'master_scale_rating']],
            left_on=[self.data_cols['deal_id']],
            right_on=[self.data_cols['deal_id']],
            how='left'
        )

        # Verify required columns exist
        required_cols = ['segment', 'sub_segment',
                         'term', 'master_scale_rating']
        missing_cols = [
            col for col in required_cols if col not in merged_1.columns]
        if missing_cols:
            print(f"ERROR: Missing required columns: {missing_cols}")
            print(f"Available columns: {list(merged_1.columns)}")
            raise KeyError(f"Missing required columns: {missing_cols}")

        # Process each scenario
        for scenario in self.scenario_param['scenario']:

            # Get MPD params for current scenario
            mpd_param_scenario = self.mpd_param[self.mpd_param['scenario'] == scenario]

            # Merge with MPD parameters for current scenario
            merged_2 = pd.merge(
                merged_1,
                mpd_param_scenario,
                left_on=['segment', 'sub_segment',
                         'term', 'master_scale_rating'],
                right_on=['segment', 'sub_segment',
                          'quarter', 'master_scale_rating'],
                how='left'
            )

            # Create a mapping DataFrame with the key columns and mpd values
            # Use deal_id and snapshot_dt as the key to ensure proper alignment
            mpd_mapping = merged_2[['deal_id',
                                    self.data_cols['payment_dt'], 'mpd']].copy()

            # Merge back to cf_table using the key columns to ensure proper alignment
            self.cf_table = pd.merge(
                self.cf_table,
                mpd_mapping,
                left_on=['deal_id', self.data_cols['payment_dt']],
                right_on=['deal_id', self.data_cols['payment_dt']],
                how='left'
            )

            # Rename the mpd column to the scenario-specific name
            self.cf_table[f'applied_mpd_{scenario}'] = self.cf_table['mpd']

            # Drop the temporary mpd column
            self.cf_table = self.cf_table.drop(columns=['mpd'])

        return self.cf_table

    def _pd_adjustment(self) -> pd.DataFrame:

        for scenario in self.scenario_param['scenario']:

            self.cf_table[f'final_mpd_{scenario}'] = 1 - (
                (1-self.cf_table[f'applied_mpd_{scenario}'])**(self.cf_table['remaining_life_of_the_quarter']))

        return self.cf_table
