import pandas as pd
import numpy as np
from typing import Dict, Optional
from dateutil.relativedelta import relativedelta


class ECLCalculation:
    def __init__(self,
                 context,
                 param,
                 cf_table: pd.DataFrame,
                 loan_table: pd.DataFrame,
                 data_cols: Optional[Dict[str, str]] = None):

        self.cf_table = cf_table.copy()
        self.loan_table = loan_table.copy()
        self.scenario_param = param['scenario_weight_param']
        self.scenarios = self.scenario_param['scenario']
        self.current_dt = context.data_yymm
        self.outInterimPath = context.outInterimPath
        self.data_cols = data_cols or {
            'id': 'deal_id',
            'snap_dt': 'snapshot_dt',
            'stage': 'final_stage',
        }

    def process_all(self):
        self.calculate_ECL_by_date()
        # self.cf_table.to_csv(self.outInterimPath /
        #                      "step_12_1_ecl_by_date.csv", index=False)

        self.calculate_12m_ECL()
        # self.loan_table.to_csv(
        #     self.outInterimPath / "step_12_2_ecl_12m.csv", index=False)

        self.calculate_lt_ECL()
        # self.loan_table.to_csv(
        #     self.outInterimPath / "step_12_3_ecl_lt.csv", index=False)

        self.calculate_pwa_ecl()
        return self.loan_table

    def calculate_ECL_by_date(self):
        for scenario in self.scenarios:
            # Calculate ECL for current period
            self.cf_table[f'ecl_{scenario}'] = (
                self.cf_table['ead'] *
                self.cf_table[f'applied_mpd_{scenario}'] *
                self.cf_table[f'lgd_{scenario}'] *
                self.cf_table['discount_factor']
            )
        return self.cf_table

    def calculate_12m_ECL(self):
        # Sort data
        self.cf_table = self.cf_table.sort_values(
            [self.data_cols['id'], self.data_cols['snap_dt']])

        # Get cutoff date (first date + 12mo)
        as_of_dt = pd.to_datetime(self.current_dt)
        cutoff_dt = as_of_dt + relativedelta(months=12)

        # Filter window
        mask = (self.cf_table[self.data_cols['snap_dt']] > as_of_dt) & \
            (self.cf_table[self.data_cols['snap_dt']] <= cutoff_dt)
        window_df = self.cf_table[mask].copy()

        # Sum ECLs
        ecl_cols = [f'ecl_{scenario}' for scenario in self.scenarios]
        result = window_df.groupby(self.data_cols['id'])[ecl_cols].sum()
        result.columns = [f'ecl_12m_{scenario}' for scenario in self.scenarios]

        self.loan_table = pd.merge(
            self.loan_table,
            result.reset_index(),
            left_on=[self.data_cols['id']],
            right_on=[self.data_cols['id']],
            how='left'
        )
        return self.loan_table

    def calculate_lt_ECL(self):
        """Calculate lifetime ECL by summing ECL_{scenario} values"""
        # Sum ECLs across all periods (lifetime view)
        ecl_cols = [f'ecl_{scenario}' for scenario in self.scenarios]
        result = self.cf_table.groupby(self.data_cols['id'])[ecl_cols].sum()

        # Rename columns to indicate lifetime ECL
        result.columns = [f'ecl_lt_{scenario}' for scenario in self.scenarios]

        # Merge with loan_table
        self.loan_table = pd.merge(
            self.loan_table,
            result.reset_index(),
            left_on=[self.data_cols['id']],
            right_on=[self.data_cols['id']],
            how='left'
        )
        return self.loan_table

    def calculate_pwa_ecl(self):
        """
        Calculate weighted average ECL values using scenario weights and apply stage-based final ECL
        """
        # 1. Calculate weighted averages
        for period in ['12m', 'lt']:
            weighted_sum = 0
            for scenario in self.scenarios:
                # Get scenario weight for each period
                weight = self.scenario_param.loc[
                    self.scenario_param['scenario'] == scenario, 'scenario_weight'
                ].values[0]

                # Calculate weighted sum
                weighted_sum += self.loan_table[f'ecl_{period}_{scenario}'] * weight

            # Store weighted average
            self.loan_table[f'ecl_{period}_pwa'] = weighted_sum

        # 2. Apply stage-based final ECL
        self.loan_table['pwa_ecl'] = np.where(
            self.loan_table[self.data_cols['stage']] == 1,
            self.loan_table['ecl_12m_pwa'],
            self.loan_table['ecl_lt_pwa']
        )

        return self.loan_table
