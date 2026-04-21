# Lock packages
import pandas as pd
import numpy as np
import numpy_financial as npf
from typing import List, Dict, Optional, Union, Tuple, Type
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import warnings


# ---------- Repayment Types ----------
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

    def _annual_to_period_rate(
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
            annual_rate = deal_row[self.data_cols['annual_rate']]
            principal = deal_row[self.data_cols['principal']]
            deal_id = deal_row[self.data_cols['deal_id']]
            start_dte = deal_row[self.data_cols['start_date']]
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
                self._annual_to_period_rate(annual_rate, days_diff)
            ead_value = current_prin + accrued_interest

            if ead_date == ead_dates[-1]:
                ead_results.append({
                    'deal_id': deal_id,
                    'snapshot_dt': ead_date.date(),
                    'prin_rem': 0,
                    'ead': 0
                })
            else:
                ead_results.append({
                    'deal_id': deal_id,
                    'snapshot_dt': ead_date.date(),
                    'prin_rem': round(principal, self.rounding),
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
        # Validate dates array
        if len(dates) < 2:
            raise ValueError(
                f"Insufficient dates for calculation: {len(dates)} dates provided, need at least 2")

        n_periods = len(dates) - 1

        if freq == 'M':
            rate = (1+annual_rate)**(freq_mult/12) - 1
            return rate, n_periods
        elif freq == 'Q':
            rate = (1+annual_rate)**(freq_mult/4) - 1
            return rate, n_periods
        elif freq == 'D':
            rate = (1+annual_rate)**(freq_mult/365) - 1
            return rate, n_periods
        else:
            raise ValueError(f"Unsupported frequency: {freq}")

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        """Calculate equal installment cashflow schedule"""
        # Get deal parameters directly from deal_row
        start_dte = deal_row[self.data_cols['start_date']]
        mat_dte = deal_row[self.data_cols['maturity_date']]
        pay_dte_1 = deal_row[self.data_cols['first_payment_date']]
        freq = deal_row[self.data_cols['instal_freq']]
        freq_mult = deal_row[self.data_cols['instal_freq_n']]
        annual_rate = deal_row[self.data_cols['annual_rate']]
        principal = deal_row[self.data_cols['principal']]
        deal_id = deal_row[self.data_cols['deal_id']]

        dates = self._generate_cashflow_dates(
            start_dte, mat_dte, pay_dte_1, freq, freq_mult
        )

        if len(dates) < 2:
            return []

        # Get periodic parameters
        rate, n_periods = self._get_periodic_params(
            start_dte, dates, freq, annual_rate, freq_mult
        )

        # Calculate fixed installment payment
        inst_pmt = self._calculate_periodic_payment(
            rate, n_periods, principal
        )

        # print('inst_pmt', inst_pmt)
        # print('principal', principal)
        # print('rate', rate)
        # print('n_periods', n_periods)

        cfl = []
        remaining_principal = principal

        for i in range(1, len(dates)):
            # if i <= 10:
            #     print('dates[i]', dates[i])

            # Calculate period-specific rate
            period_days = (dates[i] - dates[i-1]).days
            if freq in ['M', 'Q']:
                period_rate = self._annual_to_period_rate(
                    annual_rate, period_days)
            else:
                period_rate = rate

            # Calculate interest and principal components
            # TODO: change to 复利
            accrued_int = remaining_principal * period_rate
            if i == len(dates)-1:  # Handle final payment
                principal_pmt = remaining_principal
                accrued_int = max(inst_pmt - principal_pmt, 0)
            else:
                principal_pmt = inst_pmt - accrued_int

            remaining_principal -= principal_pmt
            # if i <= 10:
            #     print('remaining_principal', remaining_principal)
            #     print('principal_pmt', principal_pmt)
            #     print('accrued_int', accrued_int)

            cfl.append({
                'deal_id': deal_id,
                'cashflow_dt': dates[i].date(),
                'inst_pmt': round(inst_pmt, self.rounding),
                'accrued_int': round(accrued_int, self.rounding),
                'prin_pmt': round(principal_pmt, self.rounding),
                'prin_rem': round(remaining_principal, self.rounding)
            })
        return cfl


class EPPRepayment(BaseRepayment):
    """Equal Principal Payment repayment scheme"""

    def _calculate_principal_payments(
        self,
        principal: float,
        n_periods: int
    ) -> Tuple[float, List[float]]:
        """Calculate equal principal payments and final adjustment"""
        if n_periods <= 0:
            return 0, []

        base_principal = principal / n_periods
        adjusted_principal = principal - (base_principal * (n_periods - 1))
        payments = [base_principal] * (n_periods - 1)
        payments.append(adjusted_principal)
        return base_principal, payments

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        """Calculate equal principal cashflow schedule"""
        # Get deal parameters directly from deal_row
        start_dte = deal_row[self.data_cols['start_date']]
        mat_dte = deal_row[self.data_cols['maturity_date']]
        pay_dte_1 = deal_row[self.data_cols['first_payment_date']]
        freq = deal_row[self.data_cols['instal_freq']]
        freq_mult = deal_row[self.data_cols['instal_freq_n']]
        annual_rate = deal_row[self.data_cols['annual_rate']]
        principal = deal_row[self.data_cols['principal']]
        deal_id = deal_row[self.data_cols['deal_id']]

        dates = self._generate_cashflow_dates(
            start_dte, mat_dte, pay_dte_1, freq, freq_mult
        )

        if len(dates) < 2:
            return []

        # Calculate number of payment periods
        n_periods = len(dates) - 1

        # Generate principal payments
        base_principal, principal_pmts = self._calculate_principal_payments(
            principal, n_periods
        )

        cfl = []
        remaining_principal = principal
        for i in range(1, len(dates)):
            # Calculate period-specific rate
            period_days = (dates[i] - dates[i-1]).days
            period_rate = self._annual_to_period_rate(
                annual_rate, period_days)

            # Calculate interest component
            accrued_int = remaining_principal * period_rate

            # Get principal payment
            principal_pmt = principal_pmts[i -
                                           1] if i <= len(principal_pmts) else 0

            # Update remaining principal
            remaining_principal -= principal_pmt

            cfl.append({
                'deal_id': deal_id,
                'cashflow_dt': dates[i].date(),
                'inst_pmt': round(principal_pmt + accrued_int, self.rounding),
                'accrued_int': round(accrued_int, self.rounding),
                'prin_pmt': round(principal_pmt, self.rounding),
                'prin_rem': round(remaining_principal, self.rounding)
            })
        return cfl


class BulletRepayment(BaseRepayment):
    """Normal Bullet repayment scheme (periodic interest payments, principal at maturity)"""

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        """Calculate normal bullet repayment cashflow schedule"""
        # Get deal parameters directly from deal_row
        start_dte = deal_row[self.data_cols['start_date']]
        mat_dte = deal_row[self.data_cols['maturity_date']]
        pay_dte_1 = deal_row[self.data_cols['first_payment_date']]
        freq = deal_row[self.data_cols['instal_freq']]
        freq_mult = deal_row[self.data_cols['instal_freq_n']]
        annual_rate = deal_row[self.data_cols['annual_rate']]
        principal = deal_row[self.data_cols['principal']]
        deal_id = deal_row[self.data_cols['deal_id']]

        dates = self._generate_cashflow_dates(
            start_dte, mat_dte, pay_dte_1, freq, freq_mult
        )

        if len(dates) < 2:
            return []

        cfl = []
        remaining_principal = principal

        for i in range(1, len(dates)):
            # Calculate period interest
            period_days = (dates[i] - dates[i-1]).days
            period_rate = self._annual_to_period_rate(
                annual_rate, period_days)
            accrued_int = remaining_principal * period_rate

            if i == len(dates)-1:
                # Final payment: principal + current period interest
                inst_pmt = remaining_principal + accrued_int
                principal_pmt = remaining_principal
                remaining_principal -= principal_pmt
            else:
                # Intermediate periods: pay only interest
                inst_pmt = accrued_int
                principal_pmt = 0.0

            cfl.append({
                'deal_id': deal_id,
                'cashflow_dt': dates[i].date(),
                'inst_pmt': round(inst_pmt, self.rounding),
                'accrued_int': round(accrued_int, self.rounding),
                'prin_pmt': round(principal_pmt, self.rounding),
                'prin_rem': round(remaining_principal, self.rounding)
            })

        return cfl


class BAMRepayment(BaseRepayment):
    """Bullet At Maturity repayment scheme (single payment at maturity)"""

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        """Calculate bullet at maturity cashflow schedule - 2 records: start date and maturity date"""
        # Get deal parameters directly from deal_row
        start_dte = deal_row[self.data_cols['start_date']]
        mat_dte = deal_row[self.data_cols['maturity_date']]
        annual_rate = deal_row[self.data_cols['annual_rate']]
        principal = deal_row[self.data_cols['principal']]
        deal_id = deal_row[self.data_cols['deal_id']]

        # Calculate total accrued interest from start to maturity
        days_to_maturity = (mat_dte - start_dte).days
        if days_to_maturity < 0:
            return []

        total_accrued_interest = principal * \
            self._annual_to_period_rate(annual_rate, days_to_maturity)

        # Two cashflow records: start date and maturity date
        cfl = [
            # Start date record - no payment, full principal remaining
            {
                'deal_id': deal_id,
                'cashflow_dt': start_dte.date(),
                'inst_pmt': 0,
                'accrued_int': 0,
                'prin_pmt': 0,
                'prin_rem': round(principal, self.rounding)
            },
            # Maturity date record - full payment of principal + accrued interest
            {
                'deal_id': deal_id,
                'cashflow_dt': mat_dte.date(),
                'inst_pmt': round(principal + total_accrued_interest, self.rounding),
                'accrued_int': round(total_accrued_interest, self.rounding),
                'prin_pmt': round(principal, self.rounding),
                'prin_rem': 0
            }
        ]

        return cfl

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
            annual_rate = deal_row[self.data_cols['annual_rate']]
            principal = deal_row[self.data_cols['principal']]
            deal_id = deal_row[self.data_cols['deal_id']]
            start_dte = deal_row[self.data_cols['start_date']]
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
            days_diff = (ead_date - start_dte).days
            if days_diff < 0:
                days_diff = 0

            accrued_interest = principal * \
                self._annual_to_period_rate(annual_rate, days_diff)
            ead_value = principal + accrued_interest

            if ead_date == ead_dates[-1]:
                ead_results.append({
                    'deal_id': deal_id,
                    'snapshot_dt': ead_date.date(),
                    'prin_rem': 0,
                    'ead': 0
                })
            else:
                ead_results.append({
                    'deal_id': deal_id,
                    'snapshot_dt': ead_date.date(),
                    'prin_rem': round(principal, self.rounding),
                    'ead': round(ead_value, self.rounding)
                })

        return ead_results

# ---------- CNCBI-specific repayment factory ----------


class RepaymentFactoryCncbi:
    """
    CNCBI-specific repayment factory that:
    1. uses BAM repayment for deals that are at maturity
    2. overrides first EAD row with current balance and accrued interest
    """

    def __init__(
        self,
        repayment_mapping: pd.DataFrame,
        data_cols: Optional[Dict[str, str]] = None,
        rounding: int = 6,
        grace_period: int = 0,
        use_batch_parallel: bool = False,
        batch_size: Optional[int] = None
    ):
        """
        Args:
            repayment_mapping: Mapping table containing AMRT_TYPE_CD and REPAYMENT_TYPE
            data_cols: Date Column Name Mapping. If None, uses default mapping
            rounding: decimal accuracy
            grace_period: interest-free period
            use_batch_parallel: If True, use batch parallel processing (faster for large datasets on Linux)
            batch_size: Number of deals per batch when use_batch_parallel is True. 
                       If None, batch size will be dynamically determined based on number of deals
        """
        self.repayment_map = self._create_type_map(repayment_mapping)
        # Store repayment_mapping DataFrame for querying repayment_type names
        self.repayment_mapping_df = repayment_mapping.copy()

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
                'repayment_type_cd': 'amrt_type_cd',
                'current_balance': 'cur_bal_hke',
                'interest_accrued': 'int_accr_hke',
                'instal_pmt': 'pmt_amt_hke'
            }

        self.data_cols = data_cols
        self.rounding = rounding
        self.grace_period = grace_period
        self.use_batch_parallel = use_batch_parallel
        self.batch_size = batch_size

    def _create_type_map(self, mapping_df: pd.DataFrame) -> Dict[str, Type[BaseRepayment]]:
        """Create type mapping dictionary based on mapping_df"""
        # Define the mapping of type names to class objects
        type_mapper = {
            'EIP': EIPRepayment,
            'Bullet': BulletRepayment,
            'BAM': BAMRepayment,
            'EPP': EPPRepayment,
            'NotImplemented': NotImplementedRepayment,
            # ...extend other types...
        }

        # Constructing a Mapping Dictionary from a DataFrame
        return {
            str(row['amrt_type_cd']): type_mapper.get(
                row['repayment_type'],
                NotImplementedRepayment
            )
            for _, row in mapping_df.iterrows()
            if pd.notnull(row['amrt_type_cd'])
        }

    def _get_repayment_type_name(self, amrt_code: str, deal_id: str = None) -> Optional[str]:
        """Get repayment type name from mapping table"""
        mapping_row = self.repayment_mapping_df[
            self.repayment_mapping_df['amrt_type_cd'] == amrt_code
        ]

        if not mapping_row.empty:
            return mapping_row.iloc[0]['repayment_type']

        # Try string comparison as fallback
        mapping_row_str = self.repayment_mapping_df[
            self.repayment_mapping_df['amrt_type_cd'].astype(
                str) == str(amrt_code)
        ]
        if not mapping_row_str.empty:
            return mapping_row_str.iloc[0]['repayment_type']

        return None

    def _process_data_anomalies(
        self,
        deal_row: pd.Series,
        repayment_type_name: str,
        reporting_date: int
    ) -> pd.Series:
        """
        Process data anomalies according to the correct flow:
        2. Repayment type specific anomaly processing
        """
        reporting_dte = pd.Timestamp(str(reporting_date))

        # Create a copy to avoid modifying original
        processed_row = deal_row.copy()

        # Get start_date_col and principal_col for later use
        start_date_col = self.data_cols['start_date']
        principal_col = self.data_cols['principal']

        # 2. Repayment type specific anomaly processing
        try:
            principal = float(processed_row[principal_col])
            current_balance = float(
                processed_row[self.data_cols['current_balance']])

            if repayment_type_name == 'Bullet':
                # For Bullet: if principal != current_balance, set start_date = reporting_date and principal = current_balance
                if principal != current_balance:
                    processed_row[start_date_col] = reporting_dte
                    processed_row[principal_col] = current_balance
            else:
                # For other types: if principal <= current_balance, set start_date = reporting_date and principal = current_balance
                if principal <= current_balance:
                    processed_row[start_date_col] = reporting_dte
                    processed_row[principal_col] = current_balance
        except (KeyError, ValueError, TypeError):
            # If required columns are missing or values are invalid, skip patch
            pass

        return processed_row

    def _is_at_maturity(self, start_dte: pd.Timestamp, mat_dte: pd.Timestamp, freq: str, freq_mult: int, deal_id: str = None) -> bool:
        """Check if the loan should use At Maturity bullet repayment

        Returns True if mat_dte <= start_dte + freq*freq_mult
        """
        if freq == 'M':
            # Calculate target date: start_dte + freq_mult months
            target_date = start_dte + pd.DateOffset(months=freq_mult)
            return mat_dte <= target_date
        elif freq == 'Q':
            # Calculate target date: start_dte + freq_mult quarters (3*freq_mult months)
            target_date = start_dte + pd.DateOffset(months=3 * freq_mult)
            return mat_dte <= target_date
        elif freq == 'D':
            # Calculate target date: start_dte + freq_mult days
            target_date = start_dte + pd.Timedelta(days=freq_mult)
            return mat_dte <= target_date
        return False

    def get_repayment_class(
        self,
        amrt_code: str,
        deal_row: Optional[pd.Series] = None,
        repayment_type_name: Optional[str] = None
    ) -> Type[BaseRepayment]:
        """
        Get the corresponding repayment calculation class

        Step 3: Assign repayment class based on mapped repayment type
        - Normal types: use mappedtypeRepayment format
        - For Bullet type: check is_at_maturity to decide between BAMRepayment or BulletRepayment
        """
        deal_id = deal_row[self.data_cols['deal_id']
                           ] if deal_row is not None else None

        # Get repayment type name if not provided
        if repayment_type_name is None:
            repayment_type_name = self._get_repayment_type_name(
                amrt_code, deal_id)

        # Special case: if repayment type is 9999 and first payment date is NA, use BAMRepayment
        if deal_row is not None:
            repayment_type_cd = deal_row[self.data_cols['repayment_type_cd']]
            first_payment_date = deal_row[self.data_cols['first_payment_date']]
            if (repayment_type_cd == "9999") & (pd.isna(first_payment_date)):
                return BAMRepayment

        # For Bullet_and_BAM type, check is_at_maturity to decide between BAMRepayment or BulletRepayment
        # Also handle case where 9999 is not in mapping but should be treated as Bullet
        is_bullet_and_bam_type = (repayment_type_name == 'Bullet_and_BAM') or (
            amrt_code == "9999" and repayment_type_name is None)

        if is_bullet_and_bam_type and deal_row is not None:
            # Check if required columns for at maturity check exist
            required_cols = [
                self.data_cols['start_date'],
                self.data_cols['maturity_date'],
                self.data_cols['instal_freq'],
                self.data_cols['instal_freq_n']
            ]

            if not all(col in deal_row for col in required_cols):
                return NotImplementedRepayment

            start_dte = pd.to_datetime(deal_row[self.data_cols['start_date']])
            mat_dte = pd.to_datetime(deal_row[self.data_cols['maturity_date']])
            freq = str(deal_row[self.data_cols['instal_freq']]).upper()
            freq_mult = int(deal_row[self.data_cols['instal_freq_n']])

            is_at_maturity = self._is_at_maturity(
                start_dte, mat_dte, freq, freq_mult, deal_id)

            if is_at_maturity:
                return BAMRepayment
            else:
                return BulletRepayment

        # For other types (including Bullet and BAM), use the mapped class from repayment_map
        cls = self.repayment_map.get(amrt_code)
        if not cls:
            # If 9999 is not in mapping, treat it as Bullet
            if amrt_code == "9999":
                cls = BulletRepayment
            else:
                raise ValueError(f"Unsupported AMRT_TYPE_CD: {amrt_code}")

        return cls

    def _get_repayment_type_name_from_class(self, repayment_cls: Type[BaseRepayment]) -> str:
        """Get the repayment type name from the class (simplified: use class name)"""
        # Simple mapping: use class name directly
        class_name = repayment_cls.__name__
        # Remove 'Repayment' suffix if present
        if class_name.endswith('Repayment'):
            return class_name[:-9]  # Remove 'Repayment'
        return class_name

    def _process_deals_batch_parallel(self, valid_df: pd.DataFrame, reporting_date: int, result_loan_table: pd.DataFrame):
        """
        Process deals in parallel using batch processing for better performance

        Args:
            valid_df: DataFrame with valid deal data
            reporting_date: reporting date (YYYYMMDD)
            result_loan_table: DataFrame to update with repayment_type

        Returns:
            (cashflow DataFrame, EAD DataFrame, updated loan_table DataFrame)
        """
        import os
        import time

        # Prepare data for batch processing
        prep_start = time.time()
        deal_data_list = []
        for _, deal_row in valid_df.iterrows():
            deal_data_list.append({
                'deal_row': deal_row.to_dict(),
                'reporting_date': reporting_date,
                'repayment_mapping_df': self.repayment_mapping_df.to_dict('records'),
                'data_cols': self.data_cols,
                'rounding': self.rounding,
                'grace_period': self.grace_period
            })

        # Determine optimal batch size based on number of deals (dynamic batch sizing)
        # Similar to lgd_calculation, but adjusted for ead_layer_3's processing characteristics
        if len(deal_data_list) >= 50000:
            # Very large datasets (50k+): larger batches to minimize overhead
            dynamic_batch_size = 2000
        elif len(deal_data_list) >= 20000:
            dynamic_batch_size = 1000  # Large datasets: larger batches to reduce overhead
        elif len(deal_data_list) >= 5000:
            dynamic_batch_size = 500   # Medium datasets: medium batches
        elif len(deal_data_list) >= 1000:
            dynamic_batch_size = 200   # Small-medium datasets: smaller batches
        else:
            dynamic_batch_size = 50    # Small datasets: smallest batches for better load balancing

        # Use configured batch_size if explicitly set, otherwise use dynamic batch_size
        # If batch_size is None or not set, use dynamic batch_size
        if self.batch_size is not None and self.batch_size > 0:
            batch_size = self.batch_size  # Use configured batch_size
        else:
            batch_size = dynamic_batch_size  # Use dynamic batch_size

        # Split deals into batches
        batches = []
        for i in range(0, len(deal_data_list), batch_size):
            batches.append(deal_data_list[i:i + batch_size])

        # Calculate max_workers dynamically
        cpu_count = os.cpu_count() or 4
        cpu_based_workers = max(1, cpu_count - 1)

        if cpu_count >= 16:
            max_workers_limit = 10
        elif cpu_count >= 8:
            max_workers_limit = 8
        elif cpu_count >= 4:
            max_workers_limit = 5
        else:
            max_workers_limit = max(1, cpu_count - 1)

        max_workers = min(cpu_based_workers, max_workers_limit, len(batches))
        prep_time = time.time() - prep_start

        # Process batches in parallel
        cfl_results = {}  # {deal_id: cfl_df}
        ead_results = {}  # {deal_id: ead_df}

        # Start timing actual parallel processing
        parallel_start = time.time()
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batch tasks
            submit_start = time.time()
            future_to_batch = {
                executor.submit(_process_batch_deals_worker, batch_data): batch_data
                for batch_data in batches
            }
            submit_time = time.time() - submit_start

            # Collect results as they complete
            collect_start = time.time()
            completed_batches = 0
            total_deals_processed = 0
            for future in as_completed(future_to_batch):
                batch_data = future_to_batch[future]
                try:
                    # List of (cfl_df, ead_df, repayment_type_name_display, deal_id)
                    batch_results = future.result()

                    # Process each deal result in the batch
                    for cfl, ead, repayment_type_name_display, deal_id in batch_results:
                        # Update result_loan_table with repayment_type
                        result_loan_table.loc[
                            result_loan_table[self.data_cols['deal_id']
                                              ] == deal_id,
                            'repayment_type'
                        ] = repayment_type_name_display

                        # Store results by deal_id
                        if not cfl.empty:
                            cfl_results[deal_id] = cfl
                        if not ead.empty:
                            ead_results[deal_id] = ead

                    completed_batches += 1
                    # batch_data is a list of deal_data dictionaries
                    total_deals_processed += len(batch_data)

                    # Print progress for every batch completion
                    print(
                        f"Completed {completed_batches}/{len(batches)} batches ({total_deals_processed}/{len(deal_data_list)} deals)")

                except Exception as exc:
                    warnings.warn(f'Batch generated an exception: {exc}')
            collect_time = time.time() - collect_start
        parallel_time = time.time() - parallel_start

        # Concat results
        concat_start = time.time()
        cfl_dfs = list(cfl_results.values())
        ead_dfs = list(ead_results.values())
        concat_time = time.time() - concat_start

        # Print timing information
        print(f"\n[Layer 3 Batch Parallel Processing Timing]")
        print(f"  Data preparation: {prep_time:.3f}s")
        print(f"  Task submission (serialization): {submit_time:.3f}s")
        print(f"  Actual parallel processing (core): {collect_time:.3f}s")
        print(f"  Result concatenation: {concat_time:.3f}s")
        print(f"  Total parallel time: {parallel_time:.3f}s")
        print(
            f"  Total time (including prep): {prep_time + parallel_time + concat_time:.3f}s")
        print(
            f"  Batches processed: {len(batches)}, Batch size: {batch_size}, Workers: {max_workers}")
        print(f"  Total deals: {len(deal_data_list)}")

        return (
            pd.concat(cfl_dfs, ignore_index=True) if cfl_dfs else pd.DataFrame(),
            pd.concat(ead_dfs, ignore_index=True) if ead_dfs else pd.DataFrame(),
            result_loan_table
        )

    def batch_process(
        self,
        loan_table: pd.DataFrame,
        reporting_date: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Batch Processing Entry Functions with first EAD row override

        Args:
            loan_table: input deal data
            reporting_date: reporting date (YYYYMMDD)

        Returns:
            (cashflow DataFrame, EAD DataFrame, updated loan_table DataFrame)
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
            self.data_cols['repayment_type_cd'],
            self.data_cols['current_balance'],
            self.data_cols['interest_accrued'],
            self.data_cols['instal_pmt']
        ]

        # Filter out rows with any blank values in required columns
        # TODO: add back the chk for testing
        valid_df = loan_table.copy()
        # valid_df = loan_table.dropna(subset=required_cols)
        # if len(valid_df) < len(loan_table):
        #     warnings.warn(
        #         f"Skipped {len(loan_table) - len(valid_df)} rows with blank values")

        # Create a copy of the loan_table to add repayment_type column
        result_loan_table = loan_table.copy()
        result_loan_table['repayment_type'] = None

        if self.use_batch_parallel:
            # Process deals in parallel using batch processing
            return self._process_deals_batch_parallel(valid_df, reporting_date, result_loan_table)
        else:
            # Process deals sequentially
            import time

            grouped = valid_df.groupby(
                self.data_cols['repayment_type_cd'], group_keys=False)
            cfl_dfs = []
            ead_dfs = []

            # Start timing sequential processing
            sequential_start = time.time()
            deal_count = 0
            for amrt_code, group_df in grouped:
                # Process each deal in the group
                for _, deal_row in group_df.iterrows():
                    deal_count += 1
                    # Step 1: Get repayment type from mapping
                    deal_id = deal_row[self.data_cols['deal_id']]
                    repayment_type_name = self._get_repayment_type_name(
                        amrt_code, deal_id)

                    # Step 2: Process data anomalies
                    processed_row = self._process_data_anomalies(
                        deal_row, repayment_type_name, reporting_date)

                    # Step 3: Get repayment class
                    repayment_cls = self.get_repayment_class(
                        amrt_code, processed_row, repayment_type_name)

                    calculator = repayment_cls(
                        data_cols=self.data_cols,
                        rounding=self.rounding,
                        grace_period=self.grace_period
                    )

                    # Store repayment type name
                    repayment_type_name_display = self._get_repayment_type_name_from_class(
                        repayment_cls)
                    deal_id = processed_row[self.data_cols['deal_id']]
                    result_loan_table.loc[result_loan_table[self.data_cols['deal_id']]
                                          == deal_id, 'repayment_type'] = repayment_type_name_display

                    # Process the current deal
                    cfl, ead = calculator.run(
                        pd.DataFrame([processed_row]), reporting_date)

                    # Override first EAD row for this deal
                    if not ead.empty:
                        deal_mask = ead['deal_id'] == deal_id

                        # Get current balance and accrued interest from input data
                        current_balance = float(
                            processed_row[self.data_cols['current_balance']])
                        interest_accrued = float(
                            processed_row[self.data_cols['interest_accrued']])

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
            sequential_time = time.time() - sequential_start

            # Concat results
            concat_start = time.time()
            result_cfl = pd.concat(
                cfl_dfs, ignore_index=True) if cfl_dfs else pd.DataFrame()
            result_ead = pd.concat(
                ead_dfs, ignore_index=True) if ead_dfs else pd.DataFrame()
            concat_time = time.time() - concat_start

            # Print timing information
            print(f"\n[Layer 3 Sequential Processing Timing]")
            print(
                f"  Actual sequential processing (core): {sequential_time:.3f}s")
            print(f"  Result concatenation: {concat_time:.3f}s")
            print(f"  Total time: {sequential_time + concat_time:.3f}s")
            print(f"  Deals processed: {deal_count}")

            return (
                result_cfl,
                result_ead,
                result_loan_table
            )


# ---------- Placeholder for unimplemented types ----------
class NotImplementedRepayment(BaseRepayment):
    """Placeholder class for unimplemented repayment types"""

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        pass
        # raise NotImplementedError("This repayment type is not yet supported")


# ---------- Batch worker function for parallel processing ----------
def _process_batch_deals_worker(batch_data):
    """
    Worker function for parallel processing of batches of deals
    This function runs in a separate process and processes multiple deals in a batch

    Args:
        batch_data: List of dictionaries, each containing all necessary data for processing a single deal
            Each dictionary contains:
            - deal_row: dict of deal row data
            - reporting_date: reporting date (YYYYMMDD)
            - repayment_mapping_df: list of dicts for repayment mapping DataFrame
            - data_cols: dictionary of data column mappings
            - rounding: rounding precision
            - grace_period: grace period in days

    Returns:
        List of tuples: [(cfl_df, ead_df, repayment_type_name_display, deal_id), ...]
    """
    batch_results = []

    # Extract common parameters from first deal (all deals share the same parameters)
    if not batch_data:
        return batch_results

    first_deal_data = batch_data[0]
    repayment_mapping_records = first_deal_data['repayment_mapping_df']
    data_cols = first_deal_data['data_cols']
    rounding = first_deal_data['rounding']
    grace_period = first_deal_data['grace_period']

    # Recreate repayment_mapping_df from records (shared across all deals in batch)
    if repayment_mapping_records:
        repayment_mapping_df = pd.DataFrame(repayment_mapping_records)
    else:
        repayment_mapping_df = pd.DataFrame(
            columns=['amrt_type_cd', 'repayment_type'])

    # Create a single RepaymentFactoryCncbi instance for the entire batch
    # This avoids recreating the instance for each deal, saving initialization time
    factory = RepaymentFactoryCncbi(
        repayment_mapping=repayment_mapping_df,
        data_cols=data_cols,
        rounding=rounding,
        grace_period=grace_period,
        use_batch_parallel=False  # No need for parallel processing inside worker
    )

    # Process each deal in the batch using the shared factory instance
    for deal_data in batch_data:
        # Extract deal-specific data
        deal_row_dict = deal_data['deal_row']
        reporting_date = deal_data['reporting_date']

        # Convert deal_row_dict back to Series
        deal_row = pd.Series(deal_row_dict)

        # Step 1: Get repayment type from mapping
        amrt_code = deal_row[data_cols['repayment_type_cd']]
        deal_id = deal_row[data_cols['deal_id']]
        repayment_type_name = factory._get_repayment_type_name(
            amrt_code, deal_id)

        # Step 2: Process data anomalies
        processed_row = factory._process_data_anomalies(
            deal_row, repayment_type_name, reporting_date)

        # Step 3: Get repayment class
        repayment_cls = factory.get_repayment_class(
            amrt_code, processed_row, repayment_type_name)

        # Step 4: Create calculator and run calculation
        calculator = repayment_cls(
            data_cols=data_cols,
            rounding=rounding,
            grace_period=grace_period
        )

        # Get repayment type name for display
        repayment_type_name_display = factory._get_repayment_type_name_from_class(
            repayment_cls)

        # Process the deal
        cfl, ead = calculator.run(
            pd.DataFrame([processed_row]), reporting_date)

        # Step 5: Override first EAD row for this deal (same logic as non-parallel branch)
        if not ead.empty:
            deal_mask = ead['deal_id'] == deal_id

            # Get current balance and accrued interest from input data
            current_balance = float(
                processed_row[data_cols['current_balance']])
            interest_accrued = float(
                processed_row[data_cols['interest_accrued']])

            # Update first row for this deal
            first_row_idx = ead[deal_mask].index[0]
            ead.loc[first_row_idx, 'prin_rem'] = round(
                current_balance, rounding)
            ead.loc[first_row_idx, 'accrued_int'] = round(
                interest_accrued, rounding)
            ead.loc[first_row_idx, 'ead'] = round(
                current_balance + interest_accrued, rounding)

        # Add result to batch results
        batch_results.append((cfl, ead, repayment_type_name_display, deal_id))

    return batch_results
