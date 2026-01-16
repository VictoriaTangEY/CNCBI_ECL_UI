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

        # Convert current_dt to datetime format once in __init__
        if isinstance(context.data_yymm, (int, str)) and len(str(context.data_yymm)) == 8:
            self.current_dt = pd.to_datetime(
                str(context.data_yymm), format='%Y%m%d')
        else:
            self.current_dt = pd.to_datetime(context.data_yymm)

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
        # Check if eir column already exists in cf_table
        if self.data_cols['EIR_rate'] in self.cf_table.columns:
            return self.cf_table

        # If not, merge from loan_table
        merged = pd.merge(
            self.cf_table,
            self.loan_table,
            left_on=[self.data_cols['deal_id']],
            right_on=[self.data_cols['deal_id']],
            how="left"
        )

        # Check if the column exists in merged result
        if self.data_cols['EIR_rate'] in merged.columns:
            self.cf_table[self.data_cols['EIR_rate']
                          ] = merged[self.data_cols['EIR_rate']]
        else:
            # Try to find eir column with suffix
            eir_columns = [
                col for col in merged.columns if 'eir' in col.lower()]
            if eir_columns:
                self.cf_table[self.data_cols['EIR_rate']
                              ] = merged[eir_columns[0]]

        return self.cf_table

    def _convert_quarterly_rate(self):
        self.cf_table['EIR_quarter'] = (
            1+self.cf_table[self.data_cols['EIR_rate']])**0.25 - 1
        return self.cf_table

    def _calculate_cum_life(self):
        """Calculate remaining life in quarters using days difference divided by 91 days per quarter"""
        # current_dt is already converted to datetime in __init__
        snap_dt_series = pd.to_datetime(
            self.cf_table[self.data_cols['snap_dt']])

        # Calculate days difference
        days_diff = (snap_dt_series - self.current_dt).dt.days

        # Calculate quarters: days_diff / 91 (estimated days per quarter)
        # Set negative values (past dates) to 0
        self.cf_table['cum_life_in_quarter'] = np.maximum(
            days_diff / 91, 0.0)

        return self.cf_table

    def _calculate_discount_factor(self):
        self.cf_table['discount_factor'] = 1 / \
            (1+self.cf_table['EIR_quarter']
             )**(self.cf_table['cum_life_in_quarter'])

        return self.cf_table
