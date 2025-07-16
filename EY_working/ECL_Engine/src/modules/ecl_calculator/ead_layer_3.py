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
                self._daily_to_period_rate(annual_rate, days_diff)
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
            rate = annual_rate / 12 * freq_mult
            return rate, n_periods
        elif freq == 'Q':
            rate = annual_rate / 4 * freq_mult
            return rate, n_periods
        elif freq == 'D':
            avg_days = np.mean(
                [(dates[i] - dates[i-1]).days for i in range(1, len(dates))])
            rate = annual_rate / 365 * avg_days
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

        cfl = []
        remaining_principal = principal

        for i in range(1, len(dates)):
            # Calculate period-specific rate
            period_days = (dates[i] - dates[i-1]).days
            if freq in ['M', 'Q']:
                period_rate = self._daily_to_period_rate(
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
            period_rate = self._daily_to_period_rate(
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
            period_rate = self._daily_to_period_rate(
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
            self._daily_to_period_rate(annual_rate, days_to_maturity)

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
                self._daily_to_period_rate(annual_rate, days_diff)
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
        parallel_by_deals: bool = False,
        chunk_size: int = 1000
    ):
        """
        Args:
            repayment_mapping: Mapping table containing AMRT_TYPE_CD and REPAYMENT_TYPE
            data_cols: Date Column Name Mapping. If None, uses default mapping
            rounding: decimal accuracy
            grace_period: interest-free period
            parallel_by_deals: If True, process by number of deals instead of AMRT_TYPE_CD
            chunk_size: Number of deals to process in parallel when parallel_by_deals is True
        """
        self.repayment_map = self._create_type_map(repayment_mapping)

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
        self.parallel_by_deals = parallel_by_deals
        self.chunk_size = chunk_size

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

    def _is_at_maturity(self, start_dte: pd.Timestamp, mat_dte: pd.Timestamp, freq: str, freq_mult: int) -> bool:
        """Check if the loan should use At Maturity bullet repayment"""
        if freq == 'M':
            # Calculate number of months between dates
            months_diff = (mat_dte.year - start_dte.year) * \
                12 + (mat_dte.month - start_dte.month)
            return months_diff == freq_mult
        elif freq == 'Q':
            # Calculate number of quarters between dates
            months_diff = (mat_dte.year - start_dte.year) * \
                12 + (mat_dte.month - start_dte.month)
            quarters_diff = months_diff / 3
            return quarters_diff == freq_mult
        elif freq == 'D':
            # Calculate number of days between dates
            days_diff = (mat_dte - start_dte).days
            return days_diff == freq_mult
        return False

    def get_repayment_class(self, amrt_code: str, deal_row: Optional[pd.Series] = None) -> Type[BaseRepayment]:
        """Get the corresponding repayment calculation class"""

        # If deal_row is provided, check if it should use BAM repayment
        if deal_row is not None:
            # Patch: if repayment type is 9999 and first payment date is NA, use BAMRepayment
            if (deal_row[self.data_cols['repayment_type_cd']] == "9999") & (pd.isna(deal_row[self.data_cols['first_payment_date']])):
                return BAMRepayment
            else:
                # Check if required columns for at maturity check exist
                required_cols = [
                    self.data_cols['start_date'],
                    self.data_cols['maturity_date'],
                    self.data_cols['instal_freq'],
                    self.data_cols['instal_freq_n']
                ]

                if not all(col in deal_row for col in required_cols):
                    return NotImplementedRepayment

                else:
                    start_dte = pd.to_datetime(
                        deal_row[self.data_cols['start_date']])
                    mat_dte = pd.to_datetime(
                        deal_row[self.data_cols['maturity_date']])
                    freq = str(deal_row[self.data_cols['instal_freq']]).upper()
                    freq_mult = int(deal_row[self.data_cols['instal_freq_n']])

                    is_at_maturity = self._is_at_maturity(
                        start_dte, mat_dte, freq, freq_mult)

                    choice = BAMRepayment if is_at_maturity else self.repayment_map.get(
                        amrt_code)
                    return choice

        # If not at maturity, proceed with normal class selection
        cls = self.repayment_map.get(amrt_code)
        if not cls:
            raise ValueError(f"Unsupported AMRT_TYPE_CD: {amrt_code}")

        return cls

    def _get_repayment_type_name(self, repayment_cls: Type[BaseRepayment]) -> str:
        """Get the repayment type name from the class"""
        # Create a reverse mapping from class to type name
        type_mapper = {
            EIPRepayment: 'EIP',
            BulletRepayment: 'Bullet_Normal',
            BAMRepayment: 'Bullet_At_Maturity',
            EPPRepayment: 'EPP',
            NotImplementedRepayment: 'NotImplemented'
        }
        return type_mapper.get(repayment_cls, 'Unknown')

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
                            amrt_code = deal_row[self.data_cols['repayment_type_cd']]
                            repayment_cls = self.get_repayment_class(
                                amrt_code, deal_row)
                            calculator = repayment_cls(
                                data_cols=self.data_cols,
                                rounding=self.rounding,
                                grace_period=self.grace_period
                            )

                            # Store repayment type name
                            repayment_type_name = self._get_repayment_type_name(
                                repayment_cls)
                            deal_id = deal_row[self.data_cols['deal_id']]
                            result_loan_table.loc[result_loan_table[self.data_cols['deal_id']]
                                                  == deal_id, 'repayment_type'] = repayment_type_name

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
                    ead_dfs, ignore_index=True) if ead_dfs else pd.DataFrame(),
                result_loan_table
            )
        else:
            # Original approach: group by AMRT_TYPE_CD
            grouped = valid_df.groupby(
                self.data_cols['repayment_type_cd'], group_keys=False)
            cfl_dfs = []
            ead_dfs = []

            for amrt_code, group_df in grouped:
                # Process each deal in the group
                for _, deal_row in group_df.iterrows():
                    repayment_cls = self.get_repayment_class(
                        amrt_code, deal_row)
                    calculator = repayment_cls(
                        data_cols=self.data_cols,
                        rounding=self.rounding,
                        grace_period=self.grace_period
                    )

                    # Store repayment type name
                    repayment_type_name = self._get_repayment_type_name(
                        repayment_cls)
                    deal_id = deal_row[self.data_cols['deal_id']]
                    result_loan_table.loc[result_loan_table[self.data_cols['deal_id']]
                                          == deal_id, 'repayment_type'] = repayment_type_name

                    # Process the current deal
                    cfl, ead = calculator.run(
                        pd.DataFrame([deal_row]), reporting_date)

                    # Override first EAD row for this deal
                    if not ead.empty:
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
                    ead_dfs, ignore_index=True) if ead_dfs else pd.DataFrame(),
                result_loan_table
            )


# ---------- Placeholder for unimplemented types ----------
class NotImplementedRepayment(BaseRepayment):
    """Placeholder class for unimplemented repayment types"""

    def calculate_cashflow(self, deal_row: pd.Series) -> List[Dict]:
        pass
        # raise NotImplementedError("This repayment type is not yet supported")
