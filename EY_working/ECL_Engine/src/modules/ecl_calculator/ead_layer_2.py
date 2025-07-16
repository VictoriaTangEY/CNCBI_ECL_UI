# Lock packages
import pandas as pd
import numpy as np
import numpy_financial as npf
from typing import List, Dict, Optional, Union, Tuple, Type
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import warnings


# ---------- Base Repayment Class ----------
class BaseRepayment:
    """Base class for repayment schedule calculations"""

    def __init__(
        self,
        data_cols: Dict[str, str],
        rounding: int = 6,
        grace_period: int = 0
    ):
        """
        Initialize common parameters for all repayment types

        Args:
            data_cols: Mapping of financial date column names
            rounding: Decimal precision for rounding
            grace_period: Grace period in days before interest accrual
        """
        self.data_cols = data_cols
        self.rounding = rounding
        self.grace_period = grace_period

    def _validate_dates(
        self,
        start_dte: pd.Timestamp,
        mat_dte: pd.Timestamp,
        pay_dte_1: pd.Timestamp
    ) -> bool:
        """Validate date consistency and return True if valid"""
        if pd.isnull([start_dte, mat_dte, pay_dte_1]).any():
            return False
        if start_dte >= mat_dte:
            return False
        return True

    def _generate_cashflow_dates(
        self,
        start_dte: pd.Timestamp,
        mat_dte: pd.Timestamp,
        pay_dte_1: pd.Timestamp,
        instal_freq: str,
        instal_freq_n: int
    ) -> pd.DatetimeIndex:
        """Generate cashflow dates between start and maturity dates"""
        if not self._validate_dates(start_dte, mat_dte, pay_dte_1):
            return pd.DatetimeIndex([])

        # For monthly and quarterly frequency, use the day of the 1st payment date as repayment day
        def _get_first_pay_date(sd: pd.Timestamp, pay_day: int) -> pd.Timestamp:
            try:
                candidate = sd.replace(day=min(pay_day, sd.daysinmonth))
                if candidate > sd:
                    return candidate
            except ValueError:
                pass
            next_month = sd + pd.offsets.MonthBegin(instal_freq_n)
            return next_month.replace(day=min(pay_day, next_month.daysinmonth))

        # Generate schedule based on instal_freq and instal_freq_n
        if instal_freq == 'M':
            # For monthly and quarterly frequency, use the day of the 1st payment date as repayment day
            pay_day = min(pay_dte_1.day, pay_dte_1.daysinmonth)
            first_pay_date = _get_first_pay_date(start_dte, pay_day)
            # For monthly frequency, use MonthEnd offset
            schedule = pd.date_range(
                start=first_pay_date,
                end=mat_dte,
                freq=f'{instal_freq_n}M',
                inclusive='left'
            )
            # Ensure all dates have the payment day
            schedule = schedule.to_series().apply(
                lambda dt: dt.replace(day=min(pay_day, dt.daysinmonth))
            )
        elif instal_freq == 'Q':
            # For monthly and quarterly frequency, use the day of the 1st payment date as repayment day
            pay_day = min(pay_dte_1.day, pay_dte_1.daysinmonth)
            first_pay_date = _get_first_pay_date(start_dte, pay_day)
            # For quarterly frequency, use QuarterEnd offset
            schedule = pd.date_range(
                start=first_pay_date,
                end=mat_dte,
                freq=f'{instal_freq_n}Q',
                inclusive='left'
            )
            # Ensure all dates have the payment day
            schedule = schedule.to_series().apply(
                lambda dt: dt.replace(day=min(pay_day, dt.daysinmonth))
            )
        elif instal_freq == 'D':
            # For daily frequency, use Day offset
            schedule = pd.date_range(
                start=start_dte,
                end=mat_dte,
                freq=f'{instal_freq_n}D',
                inclusive='left'
            )
        else:
            raise ValueError(
                f"Invalid frequency {instal_freq}. Use 'D', 'M', or 'Q'")

        schedule = pd.DatetimeIndex(schedule)

        # Combine start date, schedule, and maturity date
        result = (
            pd.DatetimeIndex([start_dte])
            .union(schedule)
            .union([mat_dte])
            .sort_values()
            .drop_duplicates()
        )

        return result

    def _daily_to_period_rate(
        self,
        annual_rate: float,
        days: int
    ) -> float:
        """Convert annual rate to period-specific rate using compound interest"""
        effective_days = max(days - self.grace_period, 0)
        return ((1 + annual_rate) ** (effective_days/365) - 1)

    def _generate_ead_dates(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp
    ) -> pd.DatetimeIndex:
        """Generate quarterly EAD dates between start and end dates"""
        # TODO: confirm what if the date is in mid of the month? will need more flexible frequency?
        snapshot_day = min(start_date.day, start_date.daysinmonth)
        schedule = pd.date_range(
            start=start_date,
            end=end_date,
            freq='Q',
            inclusive='left'
        )
        # Ensure all dates have the payment day
        schedule = schedule.to_series().apply(
            lambda dt: dt.replace(day=min(snapshot_day, dt.daysinmonth))
        )

        schedule = pd.DatetimeIndex(schedule)

        # Combine start date, schedule, and maturity date
        result = (
            pd.DatetimeIndex([start_date])
            .union(schedule)
            .union([end_date])
            .sort_values()
            .drop_duplicates()
        )

        # dates = [start_date]
        # q_dates = pd.date_range(
        #     start=start_date + pd.offsets.QuarterEnd(0),
        #     end=end_date,
        #     freq='Q'
        # )
        # dates.extend(q_dates)
        # if end_date not in dates:
        #     dates.append(end_date)
        # return pd.DatetimeIndex(dates).unique().sort_values().to_series().loc[lambda x: x <= end_date].index

        return result

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        """To be implemented by subclasses"""
        raise NotImplementedError

    def calculate_ead(
        self,
        cfl: List[Dict],
        deal_row: pd.Series,
        reporting_date: int
    ) -> List[Dict]:
        """Calculate EAD for a single deal row and its cashflow"""
        try:
            reporting_dte = pd.Timestamp(str(reporting_date))
            mat_dte = deal_row[self.data_cols['maturity_date']]
            annual_rate = deal_row[self.data_cols['annual_rate']] / 100
            principal = abs(float(deal_row[self.data_cols['principal']]))
            deal_id = str(deal_row[self.data_cols['deal_id']])
        except KeyError as e:
            raise ValueError(f"Missing column: {e}") from None

        if not cfl:
            return []

        cfl_df = pd.DataFrame(cfl)
        cfl_df['cashflow_dt'] = pd.to_datetime(cfl_df['cashflow_dt'])
        cfl_df = cfl_df.set_index('cashflow_dt').sort_index()

        ead_dates = self._generate_ead_dates(reporting_dte, mat_dte)
        ead_results = []

        for ead_date in ead_dates:

            valid_dates = cfl_df.index[cfl_df.index <= ead_date]
            if valid_dates.empty:
                current_prin = principal
                last_cfl_date = reporting_dte
            else:
                last_cfl_date = valid_dates.max()
                current_prin = cfl_df.loc[last_cfl_date, 'prin_rem']

            days_diff = (ead_date - last_cfl_date).days
            if days_diff < 0:
                days_diff = 0

            accrued_interest = current_prin * \
                self._daily_to_period_rate(annual_rate, days_diff)
            ead_value = current_prin + accrued_interest

            ead_results.append({
                'deal_id': deal_id,
                'snapshot_dt': ead_date.date(),
                'prin_rem': round(current_prin, self.rounding),
                'ead': round(ead_value, self.rounding)
            })
        return ead_results

    def run(
        self,
        df: pd.DataFrame,
        reporting_date: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Process DataFrame and return concatenated cashflow and EAD results"""
        cfl_list = []
        ead_list = []

        for _, row in df.iterrows():
            try:
                deal_cfl = self.calculate_cashflow(row)
                if deal_cfl:
                    cfl_list.extend(deal_cfl)
                    deal_ead = self.calculate_ead(
                        deal_cfl, row, reporting_date)
                    if deal_ead:
                        ead_list.extend(deal_ead)
            except Exception as e:
                print(
                    f"Error processing deal {row[self.data_cols['deal_id']]}: {str(e)}")

        return (
            pd.DataFrame(cfl_list) if cfl_list else pd.DataFrame(),
            pd.DataFrame(ead_list) if ead_list else pd.DataFrame()
        )


# ---------- EIP Repayment Class ----------
class EIPRepayment(BaseRepayment):
    """Equal Installment Payment (principal + interest) repayment scheme"""

    def _calculate_periodic_payment(
        self,
        rate: float,
        n_periods: int,
        principal: float
    ) -> float:
        """Calculate fixed installment payment using time value of money"""
        try:
            return abs(npf.pmt(
                rate=rate,
                nper=n_periods,
                pv=-principal,
                fv=0
            ))
        except (npf.InvalidRateError, ZeroDivisionError):
            return principal / n_periods if n_periods else 0

    def _get_periodic_params(
        self,
        start: pd.Timestamp,
        dates: pd.DatetimeIndex,
        freq: str,
        annual_rate: float,
        freq_mult: int
    ) -> tuple:
        """Calculate periodic rate and validate parameters"""
        if freq == 'M':
            rate = annual_rate / 12 * freq_mult
            n_periods = len(dates) - 1
            return rate, n_periods
        elif freq == 'Q':
            rate = annual_rate / 4 * freq_mult
            n_periods = len(dates) - 1
            return rate, n_periods
        elif freq == 'D':
            avg_days = np.mean(
                [(dates[i] - dates[i-1]).days for i in range(1, len(dates))])
            rate = annual_rate / 365 * avg_days
            n_periods = len(dates) - 1
            return rate, n_periods
        else:
            raise ValueError(f"Unsupported frequency: {freq}")

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        """Calculate equal installment cashflow schedule"""
        # Extract parameters directly from standardized data
        start_dte = deal_row[self.data_cols['start_date']]
        mat_dte = deal_row[self.data_cols['maturity_date']]
        pay_dte_1 = deal_row[self.data_cols['first_payment_date']]
        freq = str(deal_row[self.data_cols['instal_freq']]).upper()
        freq_mult = int(deal_row[self.data_cols['instal_freq_n']])
        rate = float(deal_row[self.data_cols['annual_rate']])
        principal = abs(float(deal_row[self.data_cols['principal']]))
        deal_id = str(deal_row[self.data_cols['deal_id']])

        dates = self._generate_cashflow_dates(
            start_dte, mat_dte, pay_dte_1, freq, freq_mult
        )

        if len(dates) < 2:
            return []

        # Get periodic parameters
        rate, n_periods = self._get_periodic_params(
            start_dte, dates, freq, rate, freq_mult
        )

        # Calculate fixed installment payment
        inst_pmt = self._calculate_periodic_payment(
            rate, n_periods, principal
        )

        cfl = []
        remaining_principal = principal

        for i in range(1, len(dates)):
            # Calculate period-specific rate
            period_days = (dates[i] - dates[i-1]).days
            if freq in ['M', 'Q']:
                period_rate = self._daily_to_period_rate(
                    rate, period_days)
            else:
                period_rate = rate

            # Calculate interest and principal components
            accrued_int = remaining_principal * period_rate
            if i == len(dates)-1:  # Handle final payment
                principal_pmt = remaining_principal
                accrued_int = max(inst_pmt - principal_pmt, 0)
            else:
                principal_pmt = inst_pmt - accrued_int

            remaining_principal -= principal_pmt

            cfl.append({
                'deal_id': deal_id,
                'cashflow_dt': dates[i].date(),
                'instal_pmt': round(inst_pmt, self.rounding),
                'accrued_int': round(accrued_int, self.rounding),
                'principal_pmt': round(principal_pmt, self.rounding),
                'prin_rem': round(remaining_principal, self.rounding)
            })
        return cfl


# ---------- CNCBI-specific EIP repayment ----------
class EIPRepaymentCncbi(EIPRepayment):
    """
    CNCBI-specific EIP repayment scheme that allows assigned installment payment.
    For CNCBI cashflow layer 2 - EIP_EMBEDDED
    """

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        """Calculate equal installment cashflow schedule with assigned payment if available"""
        # Extract parameters directly from standardized data
        start_dte = deal_row[self.data_cols['start_date']]
        mat_dte = deal_row[self.data_cols['maturity_date']]
        pay_dte_1 = deal_row[self.data_cols['first_payment_date']]
        freq = str(deal_row[self.data_cols['instal_freq']]).upper()
        freq_mult = int(deal_row[self.data_cols['instal_freq_n']])
        rate = float(deal_row[self.data_cols['annual_rate']])
        principal = abs(float(deal_row[self.data_cols['principal']]))
        deal_id = str(deal_row[self.data_cols['deal_id']])

        dates = self._generate_cashflow_dates(
            start_dte, mat_dte, pay_dte_1, freq, freq_mult
        )

        if len(dates) < 2:
            print(
                f"Layer 2 - Insufficient dates for deal {deal_id}: {len(dates)} dates generated")
            return []

        # Get periodic parameters
        rate, n_periods = self._get_periodic_params(
            start_dte, dates, freq, rate, freq_mult
        )

        # Get installment payment - use assigned value if available
        if pd.notnull(deal_row[self.data_cols['instal_pmt']]):
            inst_pmt = float(deal_row[self.data_cols['instal_pmt']])
        else:
            inst_pmt = self._calculate_periodic_payment(
                rate, n_periods, principal
            )

        cfl = []
        remaining_principal = principal

        for i in range(1, len(dates)):
            # Calculate period-specific rate
            period_days = (dates[i] - dates[i-1]).days
            if freq in ['M', 'Q']:
                period_rate = self._daily_to_period_rate(
                    rate, period_days)
            else:
                period_rate = rate

            # Calculate interest and principal components
            accrued_int = remaining_principal * period_rate
            if i == len(dates)-1:  # Handle final payment
                principal_pmt = remaining_principal
                accrued_int = max(inst_pmt - principal_pmt, 0)
            else:
                principal_pmt = inst_pmt - accrued_int

            remaining_principal -= principal_pmt

            cfl.append({
                'deal_id': deal_id,
                'cashflow_dt': dates[i].date(),
                'instal_pmt': round(inst_pmt, self.rounding),
                'accrued_int': round(accrued_int, self.rounding),
                'principal_pmt': round(principal_pmt, self.rounding),
                'prin_rem': round(remaining_principal, self.rounding)
            })
        return cfl


# ---------- CNCBI-specific repayment factory ----------
class RepaymentFactoryCncbi:
    """
    CNCBI-specific repayment factory for layer 2 that only handles EIP repayment type.
    """

    def __init__(
        self,
        data_cols: Optional[Dict[str, str]] = None,
        rounding: int = 6,
        grace_period: int = 0,
        parallel_by_deals: bool = False,
        chunk_size: int = 1000
    ):
        """
        Args:
            data_cols: Date Column Name Mapping. If None, uses default mapping
            rounding: decimal accuracy
            grace_period: interest-free period
            parallel_by_deals: If True, process by number of deals instead of AMRT_TYPE_CD
            chunk_size: Number of deals to process in parallel when parallel_by_deals is True
        """
        # Add CNCBI-specific columns to data_cols
        if data_cols is None:
            data_cols = {
                'start_date': 'deal_dt',
                'maturity_date': 'maturity_date_final',
                'first_payment_date': 'nxt_pmt_dt',
                'instal_freq': 'pmt_freq_multiplier',
                'instal_freq_n': 'pmt_freq',
                'annual_rate': 'eir',
                'principal': 'prin_amt_hke',
                'deal_id': 'deal_id',
                'current_balance': 'cur_bal_hke',
                'interest_accrued': 'int_accr_hke',
                'instal_pmt': 'pmt_amt_hke'
            }

        self.data_cols = data_cols
        self.rounding = rounding
        self.grace_period = grace_period
        self.parallel_by_deals = parallel_by_deals
        self.chunk_size = chunk_size

    def batch_process(
        self,
        loan_table: pd.DataFrame,
        reporting_date: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Batch Processing Entry Functions with first EAD row override

        Args:
            loan_table: input deal data
            reporting_date: reporting date (YYYYMMDD)

        Returns:
            (cashflow DataFrame, EAD DataFrame)
        """
        # Required columns for calculation
        required_cols = [
            self.data_cols['start_date'],
            self.data_cols['maturity_date'],
            self.data_cols['first_payment_date'],
            self.data_cols['instal_freq'],
            self.data_cols['instal_freq_n'],
            self.data_cols['annual_rate'],
            self.data_cols['principal'],
            self.data_cols['deal_id'],
            self.data_cols['current_balance'],
            self.data_cols['interest_accrued']
        ]

        # Check for missing columns
        missing_cols = [
            col for col in required_cols if col not in loan_table.columns]
        if missing_cols:
            warnings.warn(
                f"Missing required columns in loan_table: {missing_cols}")
            return pd.DataFrame(), pd.DataFrame()

        # Filter out rows with any blank values in required columns
        print(f"Layer 2 - Total deals before validation: {len(loan_table)}")

        # Check for missing values in each required column
        for col in required_cols:
            missing_count = loan_table[col].isna().sum()
            if missing_count > 0:
                print(f"Layer 2 - Missing values in {col}: {missing_count}")

        # Debug: Check the actual values in frequency and multiplier columns
        print(
            f"Layer 2 - Sample pmt_freq values: {loan_table['pmt_freq'].head(5).tolist()}")
        print(
            f"Layer 2 - Sample pmt_freq_multiplier values: {loan_table['pmt_freq_multiplier'].head(5).tolist()}")

        valid_df = loan_table.dropna(subset=required_cols)

        if len(valid_df) < len(loan_table):
            warnings.warn(
                f"Skipped {len(loan_table) - len(valid_df)} rows with blank values")
            print(f"Layer 2 - Deals after validation: {len(valid_df)}")
        else:
            print(f"Layer 2 - All deals passed validation: {len(valid_df)}")

        if self.parallel_by_deals:
            # Process by number of deals
            cfl_dfs = []
            ead_dfs = []

            # Split into chunks
            chunks = [valid_df[i:i + self.chunk_size]
                      for i in range(0, len(valid_df), self.chunk_size)]

            # Process chunks sequentially
            for chunk in chunks:
                try:
                    # Process deals in chunk in parallel
                    with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
                        futures = []

                        # Submit all deals in chunk for parallel processing
                        for _, deal_row in chunk.iterrows():
                            calculator = EIPRepaymentCncbi(
                                data_cols=self.data_cols,
                                rounding=self.rounding,
                                grace_period=self.grace_period
                            )

                            future = executor.submit(
                                calculator.run,
                                pd.DataFrame([deal_row]),
                                reporting_date
                            )
                            futures.append(future)

                        # Collect results as they complete
                        chunk_cfl = []
                        chunk_ead = []
                        for future in as_completed(futures):
                            try:
                                cfl, ead = future.result()
                                if not cfl.empty:
                                    chunk_cfl.append(cfl)
                                if not ead.empty:
                                    chunk_ead.append(ead)
                            except Exception as e:
                                warnings.warn(
                                    f"Error processing deal: {str(e)}")
                                continue

                        # Combine chunk results
                        if chunk_cfl and chunk_ead:
                            cfl_dfs.append(
                                pd.concat(chunk_cfl, ignore_index=True))
                            ead_dfs.append(
                                pd.concat(chunk_ead, ignore_index=True))

                except Exception as e:
                    warnings.warn(f"Error processing chunk: {str(e)}")
                    continue

            return (
                pd.concat(
                    cfl_dfs, ignore_index=True) if cfl_dfs else pd.DataFrame(),
                pd.concat(
                    ead_dfs, ignore_index=True) if ead_dfs else pd.DataFrame()
            )
        else:
            # Process deals sequentially
            cfl_dfs = []
            ead_dfs = []

            for _, deal_row in valid_df.iterrows():
                calculator = EIPRepaymentCncbi(
                    data_cols=self.data_cols,
                    rounding=self.rounding,
                    grace_period=self.grace_period
                )

                # Process the current deal
                cfl, ead = calculator.run(
                    pd.DataFrame([deal_row]), reporting_date)

                # Override first EAD row for this deal
                if not ead.empty:
                    deal_id = deal_row[self.data_cols['deal_id']]
                    deal_mask = ead['deal_id'] == deal_id

                    # Get current balance and accrued interest from input data
                    current_balance = float(
                        deal_row[self.data_cols['current_balance']])
                    interest_accrued = float(
                        deal_row[self.data_cols['interest_accrued']])

                    # Update first row for this deal
                    first_row_idx = ead[deal_mask].index[0]
                    ead.loc[first_row_idx, 'prin_rem'] = round(
                        current_balance, self.rounding)
                    ead.loc[first_row_idx, 'accrued_int'] = round(
                        interest_accrued, self.rounding)
                    ead.loc[first_row_idx, 'ead'] = round(
                        current_balance + interest_accrued, self.rounding)

                cfl_dfs.append(cfl)
                ead_dfs.append(ead)

            return (
                pd.concat(
                    cfl_dfs, ignore_index=True) if cfl_dfs else pd.DataFrame(),
                pd.concat(
                    ead_dfs, ignore_index=True) if ead_dfs else pd.DataFrame()
            )
