import pandas as pd
import numpy as np
from typing import Optional, Dict
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Tuple

########## Expected Life ##########

# Tailored class


class OutdatedAdjustment:
    """CNCBI-specific life calculation implementation"""

    def __init__(self,
                 loan_table: pd.DataFrame,
                 data_cols: Optional[Dict[str, str]] = None
                 ):

        self.loan_table = loan_table.copy()
        self.data_cols = data_cols or {
            'current_dt': 'as_of_dt',
            'mat_dt': 'maturity_date',
            'deal_dt': 'deal_dt'
        }

    def process_all(self) -> pd.DataFrame:
        """Full processing pipeline for CNCBI"""
        self._handle_outdated_deal_dt()
        self._handle_outdated_mat_dt()
        return self.loan_table

    def _handle_outdated_deal_dt(self):
        """Update deal date to current date for outdated loans (where maturity < current date)"""
        current_dt_col = self.data_cols['current_dt']
        mat_dt_col = self.data_cols['mat_dt']
        deal_dt_col = self.data_cols['deal_dt']

        # Identify outdated loans (maturity date earlier than current date)
        outdated_mask = (
            self.loan_table[mat_dt_col] < self.loan_table[current_dt_col]
        )

        # Update deal date to current date for outdated loans
        self.loan_table.loc[outdated_mask, deal_dt_col] = \
            self.loan_table.loc[outdated_mask, current_dt_col]

    def _handle_outdated_mat_dt(self):
        current_dt_col = self.data_cols['current_dt']
        mat_dt_col = self.data_cols['mat_dt']

        outdated_mask = (
            self.loan_table[mat_dt_col] < self.loan_table[current_dt_col]
        )

        self.loan_table['maturity_date_final_outdated'] = self.loan_table[mat_dt_col]

        # TODO: update to use param
        self.loan_table.loc[outdated_mask, 'maturity_date_final_outdated'] = (
            self.loan_table.loc[outdated_mask, current_dt_col]
            + pd.offsets.DateOffset(months=12)
        )


class MissingAdjustment:
    """CNCBI-specific life calculation implementation"""

    def __init__(self,
                 loan_table: pd.DataFrame,
                 missing_life_param: pd.DataFrame,
                 data_cols: Optional[Dict[str, str]] = None):

        self.loan_table = loan_table.copy()
        self.missing_life_param = missing_life_param.copy()
        self.data_cols = data_cols or {
            'current_dt': 'as_of_dt',
            'mat_dt': 'maturity_date',
            'life_adjustment': 'lifetime_val_std'
        }

    def process_all(self) -> pd.DataFrame:
        """Full processing pipeline for CNCBI"""
        self._apply_missing_adjustment()
        self._calculate_final_maturity()
        return self.loan_table

    def _apply_missing_adjustment(self):
        """Apply business lifetime adjustments"""

        self.loan_table = pd.merge(
            self.loan_table,
            self.missing_life_param[['source_system',
                                     'stage', self.data_cols['life_adjustment']]],
            left_on=['source_system', 'final_stage'],
            right_on=['source_system', 'stage'],
            how='left'
        )

        adjustment_col = self.data_cols['life_adjustment']
        maturity_col = self.data_cols['mat_dt']

        condition = pd.isna(self.loan_table[maturity_col])

        self.loan_table['remaining_life_missing'] = np.where(
            condition,
            self.loan_table[adjustment_col],
            np.nan
        )

        self.loan_table = self.loan_table.drop(
            columns=['stage', adjustment_col]
        )

    def _calculate_final_maturity(self):
        current_dates = self.loan_table[self.data_cols['current_dt']].values
        remaining_life = self.loan_table['remaining_life_missing'].values

        final_dates = np.empty(len(current_dates), dtype=object)

        for i in range(len(current_dates)):
            if pd.isna(remaining_life[i]) or pd.isna(current_dates[i]):
                final_dates[i] = pd.NaT
                continue

            try:
                whole_quarters = int(remaining_life[i])
                fractional_part = remaining_life[i] % 1
                remaining_days = round(fractional_part * 90)

                final_dates[i] = (
                    current_dates[i] +
                    pd.DateOffset(months=whole_quarters*3) +
                    pd.Timedelta(days=remaining_days)
                )
            except (ValueError, TypeError) as e:
                final_dates[i] = pd.NaT
                print(f"Error in {i}: {str(e)}")

        self.loan_table['maturity_date_final_missing'] = pd.to_datetime(
            final_dates, errors='coerce')


class ExpectedLifeCalculation:
    """CNCBI-specific life calculation implementation"""

    def __init__(self,
                 loan_table: pd.DataFrame,
                 lifetime_param: pd.DataFrame,
                 floor_param: str,
                 data_cols: Optional[Dict[str, str]] = None):

        self.loan_table = loan_table.copy()
        self.lifetime_param = lifetime_param.copy()
        self.floor_param = str(floor_param)
        self.data_cols = data_cols or {
            'current_dt': 'as_of_dt',
            'mat_dt': 'maturity_date_final',
            'life_adjustment': 'lifetime_val_std'
        }

    def process_all(self) -> pd.DataFrame:
        """Full processing pipeline for CNCBI"""
        self._combine_maturity_dates()
        self._apply_stage_floor()
        self._apply_life_adjustment()
        self._calculate_life()
        return self.loan_table

    def _combine_maturity_dates(self):
        mat_dt_col = self.data_cols['mat_dt']

        self.loan_table[mat_dt_col] = np.where(
            self.loan_table['maturity_date_final_outdated'].notna(),
            self.loan_table['maturity_date_final_outdated'],
            self.loan_table['maturity_date_final_missing']
        )

        # Drop the intermediate columns
        self.loan_table = self.loan_table.drop(
            columns=['maturity_date_final_outdated',
                     'maturity_date_final_missing', 'remaining_life_missing']
        )

    def _apply_stage_floor(self):
        """Enforce minimum value for stage 2 loans"""
        if self.floor_param == "Y":
            # Get column names
            current_dt_col = self.data_cols['current_dt']
            mat_dt_col = self.data_cols['mat_dt']

            # Identify stage 2 loans
            stage_2_mask = (self.loan_table['final_stage'] == 2)

            # Calculate minimum required date (4 quarters after as_of_dt)
            min_required_date = (
                self.loan_table.loc[stage_2_mask, current_dt_col]
                + pd.offsets.DateOffset(months=12)  # 4 quarters = 12 months
            )

            # Current maturity dates
            current_maturity = self.loan_table.loc[stage_2_mask, mat_dt_col]

            # Apply floor: keep whichever is later (current maturity or min required date)
            self.loan_table.loc[stage_2_mask, mat_dt_col] = np.where(
                current_maturity > min_required_date,
                current_maturity,
                min_required_date
            )

    def _apply_life_adjustment(self):
        """Apply business lifetime adjustments"""
        self.loan_table = pd.merge(
            self.loan_table,
            self.lifetime_param[['source_system', 'stage',
                                 self.data_cols['life_adjustment']]],
            left_on=['source_system', 'final_stage'],
            right_on=['source_system', 'stage'],
            how='left'
        )

        current_dates = self.loan_table[self.data_cols['current_dt']].values
        remaining_life = self.loan_table[self.data_cols['life_adjustment']].values

        final_dates = np.empty(len(current_dates), dtype=object)

        for i in range(len(current_dates)):
            if pd.isna(remaining_life[i]) or pd.isna(current_dates[i]):
                final_dates[i] = pd.NaT
                continue

            try:
                whole_quarters = int(remaining_life[i])
                fractional_part = remaining_life[i] % 1
                remaining_days = round(fractional_part * 90)

                final_dates[i] = (
                    current_dates[i] +
                    pd.DateOffset(months=whole_quarters*3) +
                    pd.Timedelta(days=remaining_days)
                )
            except (ValueError, TypeError) as e:
                final_dates[i] = pd.NaT
                print(f"Error in {i}: {str(e)}")

        valid_mask = ~pd.isna(final_dates)
        self.loan_table.loc[valid_mask,
                            self.data_cols['mat_dt']] = final_dates[valid_mask]

        # Clean up temporary columns
        self.loan_table = self.loan_table.drop(
            columns=['stage', self.data_cols['life_adjustment']])

    def _calculate_life(self):
        """Calculate remaining life in quarters using precise quarter offsets"""
        def _calculate_quarters(row):
            start_date = row[self.data_cols['current_dt']]
            end_date = row[self.data_cols['mat_dt']]

            if start_date >= end_date:
                return 0.0

            for quarter in range(0, 201):
                next_quarter_date = start_date + \
                    pd.offsets.DateOffset(months=3*quarter)

                if next_quarter_date >= end_date:
                    last_quarter_date = start_date + \
                        pd.offsets.DateOffset(months=3*(quarter))

                    remaining_days = (end_date - last_quarter_date).days
                    remaining_quarters = remaining_days / 90

                    return (quarter) + remaining_quarters if quarter > 0 else remaining_quarters

            return 200.0

        self.loan_table['remaining_life'] = self.loan_table.apply(
            _calculate_quarters,
            axis=1
        )
