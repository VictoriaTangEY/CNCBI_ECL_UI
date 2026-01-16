# Lock packages
import pandas as pd
from typing import List, Dict, Optional, Union, Tuple, Type
import warnings


# ---------- For CNCBI Specific ----------
# ---------- Cashflow & EAD Layer 1: use internal repayment schedule ----------


class CashflowLayerOne:
    """Calculate cashflow and EAD using internal repayment schedule."""

    # Default column mappings
    DEFAULT_DATA_COLS = {
        'start_date': 'deal_dt',
        'maturity_date': 'maturity_date_final',
        'annual_rate': 'eir',
        'principal': 'prin_amt_hke',
        'current_balance': 'cur_bal_hke',
        'interest_accrued': 'int_accr_hke',
        'deal_id': 'deal_id',
        'acct_id': 'acct_id'
    }

    DEFAULT_SCHED_DATA_COLS = {
        'acct_id': 'acct_id',
        'sched_start_date': 'sched_start_dt',
        'sched_end_date': 'sched_end_dt',
        'first_due_date': 'first_due_dt',
        'n_payments': 'nof_pmt',
        'instal_amt': 'instl_flat_amt_hke',
        'pmt_freq': 'pmt_freq',
        'pmt_freq_n': 'pmt_incr',
        'pmt_type': 'pmt_typ_cd',
        'pmt_skip_mth': 'skp_pmt_mth'
    }

    def __init__(
        self,
        reporting_date: int,
        data: pd.DataFrame,
        sched_data: pd.DataFrame,
        data_cols: Optional[Dict[str, str]] = None,
        sched_data_cols: Optional[Dict[str, str]] = None,
        rounding: int = 6,
        grace_period: int = 0
    ):
        """Initialize calculator with data and configuration."""
        self.reporting_date = reporting_date
        self.data = data
        self.sched_data = sched_data
        self.data_cols = data_cols or self.DEFAULT_DATA_COLS
        self.sched_data_cols = sched_data_cols or self.DEFAULT_SCHED_DATA_COLS
        self.rounding = rounding
        self.grace_period = grace_period

    def _preprocess_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Preprocess input data by converting dates and filtering valid rows."""
        data_df = self.data.copy()
        sched_df = self.sched_data.copy()

        # Convert dates to datetime
        date_cols = {
            self.sched_data_cols['first_due_date']: '%d/%m/%Y',
            self.sched_data_cols['sched_end_date']: '%d/%m/%Y',
            self.data_cols['start_date']: '%d%b%Y:%H:%M:%S',
            self.data_cols['maturity_date']: '%d%b%Y:%H:%M:%S'
        }

        for col, fmt in date_cols.items():
            if col in sched_df.columns:
                sched_df[col] = pd.to_datetime(
                    sched_df[col], format=fmt, errors='coerce')
            if col in data_df.columns:
                data_df[col] = pd.to_datetime(
                    data_df[col], format=fmt, errors='coerce')

        return data_df, sched_df

    def _get_principal_sched_df(self, sched_df: pd.DataFrame) -> pd.DataFrame:
        """Get principal schedule data."""
        return sched_df[sched_df[self.sched_data_cols['pmt_type']] == 'P']

    def _get_interest_sched_df(self, sched_df: pd.DataFrame) -> pd.DataFrame:
        """Get interest schedule data."""
        return sched_df[sched_df[self.sched_data_cols['pmt_type']] == 'I']

    def _generate_prin_dates(self, sched_df: pd.DataFrame) -> pd.DatetimeIndex:
        """Generate principal payment dates from schedule data."""
        all_dates = []

        for _, row in sched_df.iterrows():
            try:
                first_due_date = pd.to_datetime(
                    row[self.sched_data_cols['first_due_date']], format='%d:%m:%Y')
                n_payments = int(row[self.sched_data_cols['n_payments']])
                pmt_freq = str(row[self.sched_data_cols['pmt_freq']]).upper()
                pmt_freq_n = int(row[self.sched_data_cols['pmt_freq_n']])

                if n_payments <= 0 or pmt_freq_n <= 0:
                    continue

                # Generate dates based on frequency
                if pmt_freq == 'M':
                    dates = pd.date_range(
                        start=first_due_date, periods=n_payments, freq=f'{pmt_freq_n}ME')
                    dates = dates.to_series().apply(lambda dt: dt.replace(
                        day=min(first_due_date.day, dt.daysinmonth)))
                elif pmt_freq == 'Q':
                    dates = pd.date_range(
                        start=first_due_date, periods=n_payments, freq=f'{pmt_freq_n}QE')
                    dates = dates.to_series().apply(lambda dt: dt.replace(
                        day=min(first_due_date.day, dt.daysinmonth)))
                elif pmt_freq == 'D':
                    dates = pd.date_range(
                        start=first_due_date, periods=n_payments, freq=f'{pmt_freq_n}D')
                else:
                    continue

                all_dates.extend(dates)
            except Exception as e:
                warnings.warn(f"Error processing row: {str(e)}")
                continue

        # Get start and end dates
        earliest_row = sched_df.loc[sched_df[self.sched_data_cols['first_due_date']].idxmin(
        )]
        start_date = earliest_row[self.sched_data_cols['first_due_date']]
        end_date = sched_df[self.sched_data_cols['sched_end_date']].max()

        # Combine all dates
        result = (
            pd.DatetimeIndex([start_date])
            .union(all_dates)
            .union(pd.DatetimeIndex([end_date]))
            .sort_values()
            .drop_duplicates()
        )

        return result

    def _generate_int_dates(self, sched_df: pd.DataFrame) -> pd.DatetimeIndex:
        """Generate interest payment dates from schedule data."""
        if sched_df.empty:
            return pd.DatetimeIndex([])

        # Get parameters from earliest row
        earliest_row = sched_df.loc[sched_df[self.sched_data_cols['first_due_date']].idxmin(
        )]
        pmt_freq = str(earliest_row[self.sched_data_cols['pmt_freq']]).upper()
        pmt_freq_n = int(earliest_row[self.sched_data_cols['pmt_freq_n']])
        start_date = earliest_row[self.sched_data_cols['first_due_date']]
        end_date = sched_df[self.sched_data_cols['sched_end_date']].max()

        # Generate dates based on frequency
        if pmt_freq == 'M':
            dates = pd.date_range(
                start=start_date, end=end_date, freq=f'{pmt_freq_n}ME', inclusive='both')
            dates = dates.to_series().apply(lambda dt: dt.replace(
                day=min(start_date.day, dt.daysinmonth)))
        elif pmt_freq == 'Q':
            dates = pd.date_range(
                start=start_date, end=end_date, freq=f'{pmt_freq_n}QE', inclusive='both')
            dates = dates.to_series().apply(lambda dt: dt.replace(
                day=min(start_date.day, dt.daysinmonth)))
        elif pmt_freq == 'D':
            dates = pd.date_range(
                start=start_date, end=end_date, freq=f'{pmt_freq_n}D', inclusive='both')
        else:
            return pd.DatetimeIndex([])

        # Combine all dates
        result = (
            pd.DatetimeIndex([start_date])
            .union(dates)
            .union(pd.DatetimeIndex([end_date]))
            .sort_values()
            .drop_duplicates()
        )

        return result

    def _calculate_compound_interest(self, principal: float, rate: float, days: int) -> float:
        """Calculate compound interest for a given period."""
        interest = principal * ((1 + rate) ** (days/365) - 1)
        return round(interest, self.rounding)

    def calculate_cashflow(self, deal_row: pd.Series, prin_df: pd.DataFrame, prin_dates: pd.DatetimeIndex, int_dates: pd.DatetimeIndex) -> pd.DataFrame:
        """Calculate cashflow for a single deal row."""
        # Create initial DataFrame with principal dates
        cfl_df = pd.DataFrame({'cashflow_dt': prin_dates})

        # Merge instal_amt into the cashflow DataFrame
        cfl_df = cfl_df.merge(
            prin_df[[self.sched_data_cols['first_due_date'],
                     self.sched_data_cols['instal_amt']]],
            left_on='cashflow_dt',
            right_on=self.sched_data_cols['first_due_date'],
            how='left'
        )

        # Rename and clean up columns
        cfl_df = cfl_df.rename(
            columns={self.sched_data_cols['instal_amt']: 'prin_pmt'})
        cfl_df = cfl_df.drop(columns=[self.sched_data_cols['first_due_date']])

        # Forward fill missing PRIN_PMT values
        cfl_df['prin_pmt'] = cfl_df['prin_pmt'].ffill()

        # Add interest dates
        unique_int_dates = set(int_dates) - set(prin_dates)
        int_df = pd.DataFrame({'cashflow_dt': list(unique_int_dates)})
        cfl_df = pd.concat([cfl_df, int_df], ignore_index=True)

        # Sort and fill missing values
        cfl_df = cfl_df.sort_values('cashflow_dt')
        cfl_df['prin_pmt'] = cfl_df['prin_pmt'].fillna(0)

        # Add start date row
        start_date = pd.to_datetime(
            deal_row[self.data_cols['start_date']], format='%d%b%Y:%H:%M:%S')
        start_row = pd.DataFrame(
            {'cashflow_dt': [start_date], 'prin_pmt': [0]})
        cfl_df = pd.concat([start_row, cfl_df], ignore_index=True)

        # Calculate remaining principal
        # TODO: for irregular, update to start from CUR_BAL
        initial_principal = deal_row[self.data_cols['principal']]
        cfl_df['prin_rem'] = initial_principal - cfl_df['prin_pmt'].cumsum()

        return cfl_df

    def _generate_ead_dates(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp
    ) -> pd.DatetimeIndex:
        """Generate quarterly EAD dates between start and end dates"""
        # TODO: confirm what if the date is in mid of the month? will need more flexible frequency?
        dates = [start_date]
        q_dates = pd.date_range(
            start=start_date + pd.offsets.QuarterEnd(0),
            end=end_date,
            freq='QE'
        )
        dates.extend(q_dates)
        if end_date not in dates:
            dates.append(end_date)
        return pd.DatetimeIndex(dates).unique().sort_values().to_series().loc[lambda x: x <= end_date].index

    def calculate_ead(self, cfl_df: pd.DataFrame, ead_dates: pd.DatetimeIndex, prin_dates: pd.DatetimeIndex, int_dates: pd.DatetimeIndex, deal_row: pd.Series) -> pd.DataFrame:
        """Calculate EAD for a single deal row."""
        # Create initial EAD DataFrame
        ead_df = pd.DataFrame({'snapshot_dt': ead_dates})

        # Calculate latest principal payment date
        # get start_date from deal_row
        start_date = pd.to_datetime(
            deal_row[self.data_cols['start_date']], format='%d%b%Y:%H:%M:%S')
        ead_df['lst_pay_dte'] = ead_df['snapshot_dt'].apply(
            lambda x: prin_dates[prin_dates <= x].max() if any(
                prin_dates <= x) else start_date
        )

        # Merge PRIN_REM from cashflow DataFrame
        ead_df = ead_df.merge(
            cfl_df[['cashflow_dt', 'prin_rem']],
            left_on='lst_pay_dte',
            right_on='cashflow_dt',
            how='left'
        )

        # chk
        # print('\ncfl_df:')
        # print(cfl_df)

        # print('\nead_df merged:')
        # print(ead_df)
        ead_df = ead_df.drop(columns=['cashflow_dt'])

        # Calculate latest interest payment date
        ead_df['lst_int_dte'] = ead_df['snapshot_dt'].apply(
            lambda x: int_dates[int_dates <= x].max() if any(
                int_dates <= x) else None
        )

        # Calculate accrual life
        ead_df['accr_life'] = ead_df.apply(
            lambda row: (
                (row['snapshot_dt'] - row['lst_int_dte']).days
                if pd.notnull(row['lst_int_dte'])
                else (row['snapshot_dt'] - row['lst_pay_dte']).days
            ),
            axis=1
        )

        # chk
        # print('\nead_df:')
        # print(ead_df)

        # Calculate accrued interest
        annual_rate = deal_row[self.data_cols['annual_rate']]
        ead_df['accrued_int'] = ead_df.apply(
            lambda row: self._calculate_compound_interest(
                row['prin_rem'],
                annual_rate,
                row['accr_life']
            ) if pd.notnull(row['prin_rem']) else 0,
            axis=1
        )

        # chk
        # print('\nead_df:', ead_df)

        # Override first row values
        ead_df.loc[0, 'lst_pay_dte'] = pd.to_datetime(
            deal_row[self.data_cols['start_date']], format='%d%b%Y:%H:%M:%S')
        ead_df.loc[0, 'prin_rem'] = deal_row[self.data_cols['current_balance']]
        ead_df.loc[0, 'accrued_int'] = deal_row[self.data_cols['interest_accrued']]

        # Calculate EAD
        ead_df['ead'] = ead_df['prin_rem'] + ead_df['accrued_int']

        # chk
        # print('\nead_df:')
        # print(ead_df)

        return ead_df[['snapshot_dt', 'prin_rem', 'accrued_int', 'ead']]

    def batch_process(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Process multiple accounts in batches."""
        # Preprocess data
        data_df, sched_df = self._preprocess_data()

        # Check if schedule data is empty
        if sched_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        # Required columns for data_df
        required_data_cols = [
            self.data_cols['start_date'],
            self.data_cols['maturity_date'],
            self.data_cols['annual_rate'],
            self.data_cols['principal'],
            self.data_cols['current_balance'],
            self.data_cols['interest_accrued'],
            self.data_cols['deal_id'],
            self.data_cols['acct_id']
        ]

        # Required columns for sched_df
        required_sched_cols = [
            self.sched_data_cols['acct_id'],
            self.sched_data_cols['first_due_date'],
            self.sched_data_cols['n_payments'],
            self.sched_data_cols['instal_amt'],
            self.sched_data_cols['pmt_freq'],
            self.sched_data_cols['pmt_freq_n'],
            self.sched_data_cols['pmt_type']
        ]

        # Check for missing columns in data_df
        missing_data_cols = [
            col for col in required_data_cols if col not in data_df.columns]
        if missing_data_cols:
            warnings.warn(
                f"Missing required columns in data_df: {missing_data_cols}")
            return pd.DataFrame(), pd.DataFrame()

        # Check for missing columns in sched_df
        missing_sched_cols = [
            col for col in required_sched_cols if col not in sched_df.columns]
        if missing_sched_cols:
            warnings.warn(
                f"Missing required columns in sched_df: {missing_sched_cols}")
            return pd.DataFrame(), pd.DataFrame()

        # Filter out rows with any blank values in required columns
        valid_data_df = data_df.dropna(subset=required_data_cols)
        valid_sched_df = sched_df.dropna(subset=required_sched_cols)

        if len(valid_data_df) < len(data_df):
            warnings.warn(
                f"Skipped {len(data_df) - len(valid_data_df)} data rows with blank values")
        if len(valid_sched_df) < len(sched_df):
            warnings.warn(
                f"Skipped {len(sched_df) - len(valid_sched_df)} schedule rows with blank values")

        # Get unique ACCT_IDs from valid schedule data
        unique_acct_ids = valid_sched_df[self.sched_data_cols['acct_id']].unique(
        )

        # Initialize results
        all_cfl = []
        all_ead = []

        # Process sequentially
        import time

        # Start timing sequential processing
        sequential_start = time.time()
        acct_count = 0
        for acct_id in unique_acct_ids:
            try:
                # Filter data for current account
                acct_data = valid_data_df[valid_data_df[self.data_cols['acct_id']] == acct_id].copy(
                )
                acct_sched = valid_sched_df[valid_sched_df[self.sched_data_cols['acct_id']] == acct_id].copy(
                )

                if acct_data.empty or acct_sched.empty:
                    warnings.warn(f"No data found for account {acct_id}")
                    continue

                acct_count += 1
                # Process single account
                cfl, ead = self._process_single_account(
                    acct_data, acct_sched)

                if not cfl.empty:
                    all_cfl.append(cfl)
                if not ead.empty:
                    all_ead.append(ead)

            except Exception as e:
                warnings.warn(
                    f"Error processing account {acct_id}: {str(e)}")
                continue
        sequential_time = time.time() - sequential_start

        # Combine results
        concat_start = time.time()
        if all_cfl and all_ead:
            final_cfl = pd.concat(all_cfl, ignore_index=True)
            final_ead = pd.concat(all_ead, ignore_index=True)
        else:
            final_cfl = pd.DataFrame()
            final_ead = pd.DataFrame()
        concat_time = time.time() - concat_start

        # Print timing information
        print(f"\n[Layer 1 Sequential Processing Timing]")
        print(
            f"  Actual sequential processing (core): {sequential_time:.3f}s")
        print(f"  Result concatenation: {concat_time:.3f}s")
        print(f"  Total time: {sequential_time + concat_time:.3f}s")
        print(f"  Accounts processed: {acct_count}")

        return final_cfl, final_ead

    def _process_single_account(self, acct_data: pd.DataFrame, acct_sched: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Process a single account."""
        # Get principal and interest schedules
        principal_df = self._get_principal_sched_df(acct_sched)
        interest_df = self._get_interest_sched_df(acct_sched)

        # Generate dates
        prin_dates = self._generate_prin_dates(principal_df)
        int_dates = self._generate_int_dates(interest_df)

        # chk
        # print('\nprin_dates:', prin_dates)
        # print('\nint_dates:', int_dates)

        # Generate EAD dates
        reporting_dte = pd.Timestamp(str(self.reporting_date))
        ead_dates = self._generate_ead_dates(
            reporting_dte,
            acct_data[self.data_cols['maturity_date']].values[0]
        )

        # Calculate cashflow and EAD
        cfl = self.calculate_cashflow(
            acct_data.iloc[0], principal_df, prin_dates, int_dates)
        ead = self.calculate_ead(
            cfl, ead_dates, prin_dates, int_dates, acct_data.iloc[0])

        # Add account ID to results
        cfl.insert(0, 'acct_id', acct_data[self.data_cols['acct_id']].iloc[0])
        ead.insert(0, 'acct_id', acct_data[self.data_cols['acct_id']].iloc[0])

        return cfl, ead
