import pandas as pd
import numpy as np
from typing import Dict, Optional
from dateutil.relativedelta import relativedelta

########## Discount Factor ##########


class DiscountFactorCalculation:

    def __init__(self,
                 context,
                 cf_table: pd.DataFrame,
                 loan_table: pd.DataFrame,
                 data_cols: Optional[Dict[str, str]] = None):

        self.cf_table = cf_table.copy()
        self.loan_table = loan_table.copy()
        self.current_dt = context.data_yymm
        self.data_cols = data_cols or {
            'EIR_rate': 'eir',
            'deal_id': 'deal_id',
            'snap_dt': 'snapshot_dt'
        }

    def process_all(self) -> pd.DataFrame:
        self._map_back_EIR()
        self._convert_quarterly_rate()
        self._calculate_cum_life()
        self._calculate_discount_factor()
        return self.cf_table

    def _map_back_EIR(self):
        merged = pd.merge(
            self.cf_table,
            self.loan_table,
            left_on=[self.data_cols['deal_id']],
            right_on=[self.data_cols['deal_id']],
            how="left"
        )

        self.cf_table[self.data_cols['EIR_rate']
                      ] = merged[self.data_cols['EIR_rate']]

        return self.cf_table

    def _convert_quarterly_rate(self):
        self.cf_table['EIR_quarter'] = (
            1+self.cf_table[self.data_cols['EIR_rate']])**0.25 - 1
        return self.cf_table

    def _calculate_cum_life(self):
        """Calculate remaining life in quarters using days difference divided by 91 days per quarter"""
        # Convert dates to datetime if they aren't already
        current_dt = pd.to_datetime(self.current_dt)
        snap_dt_series = pd.to_datetime(
            self.cf_table[self.data_cols['snap_dt']])

        # Calculate days difference
        days_diff = (snap_dt_series - current_dt).dt.days

        # Calculate quarters: days_diff / 91 (estimated days per quarter)
        # Set negative values (past dates) to 0
        self.cf_table['cum_life_in_the_quarter'] = np.maximum(
            days_diff / 91, 0.0)

        return self.cf_table

    def _calculate_discount_factor(self):
        self.cf_table['discount_factor'] = 1 / \
            (1+self.cf_table['EIR_quarter']
             )**(self.cf_table['cum_life_in_the_quarter'])

        return self.cf_table
