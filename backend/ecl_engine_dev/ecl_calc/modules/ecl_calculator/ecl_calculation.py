import pandas as pd
import numpy as np
from typing import Dict, Optional
from dateutil.relativedelta import relativedelta


class ECLCalculation:
    def __init__(self,
                 param,
                 ead_df: pd.DataFrame):

        self.ead_df = ead_df.copy()
        self.param = param
        self.scenarios = self.param['scenario_weight_param']['scenario']

    def calculate_scenario_ecl_detailed(self):
        # ecl by scenario
        for scenario in self.scenarios:
            # Calculate ECL for current period
            self.ead_df[f'ecl_{scenario}_hke'] = (
                self.ead_df['ead'] *
                self.ead_df[f'applied_mpd_{scenario}'] *
                self.ead_df[f'applied_lgd_{scenario}'] *
                self.ead_df['discount_factor']
            )

        return self.ead_df

    def calculate_scenario_ecl_by_deal(self, scenario_ecl_detailed):
        # Sum scenario ECL columns by deal_id
        scenario_cols = [
            f"ecl_{scenario}_hke" for scenario in self.scenarios if f"ecl_{scenario}_hke" in scenario_ecl_detailed.columns]

        # Group by deal_id and sum scenario ECL columns
        ecl_by_deal = scenario_ecl_detailed.groupby(
            'deal_id')[scenario_cols].sum().reset_index()

        return ecl_by_deal

    def run_scenario_ecl(self):
        scenario_ecl_detailed = self.calculate_scenario_ecl_detailed()
        scenario_ecl_by_deal = self.calculate_scenario_ecl_by_deal(
            scenario_ecl_detailed)

        return scenario_ecl_detailed, scenario_ecl_by_deal


########################################################################################
# separate the pwa ECL calculation for flexible adjustment purpose
########################################################################################

def run_pwa_ecl(param, on_off_df, scenario_ecl_detailed, scenario_ecl_by_deal):
    scenario_param = param['scenario_weight_param']
    scenarios = scenario_param['scenario']

    def calculate_pwa_ecl(ecl_df, scenario_param):
        """
        Calculate weighted average ECL values using scenario weights and apply stage-based final ECL
        """
        scenarios = scenario_param['scenario']
        weighted_sum = 0

        for scenario in scenarios:
            # Get scenario weight for each period
            weight = scenario_param.loc[
                scenario_param['scenario'] == scenario, 'scenario_weight'
            ].values[0]

            # Calculate weighted sum
            weighted_sum += ecl_df[f'ecl_{scenario}_hke'] * weight

            # Store weighted average
        ecl_df[f'ecl_hke'] = weighted_sum

        return ecl_df

    def format_pwa_ecl_detailed(scenarios, on_off_df, pwa_ecl_detailed):
        left_df = on_off_df.copy()
        right_df = pwa_ecl_detailed.copy()

        # keep cols
        left_keep_cols = ['deal_id', 'nxt_pmt_dt', 'prin_amt_hke',
                          'int_accr_hke', 'maturity_date_final', 'remaining_life']

        right_keep_cols = ['deal_id', 'snapshot_dt',
                           'discount_factor', 'ead', 'ecl_hke']

        # add scenario cols
        for scenario in scenarios:
            right_keep_cols.append(f'applied_mpd_{scenario}')
            right_keep_cols.append(f'applied_lgd_{scenario}')
            right_keep_cols.append(f'ecl_{scenario}_hke')

        left_df = left_df[left_keep_cols]
        right_df = right_df[right_keep_cols]
        right_df.rename(columns={'ead': 'ead_hke'}, inplace=True)

        # merge on_off_df and pwa_ecl_detailed
        df = pd.merge(left_df, right_df, on='deal_id', how='left')
        df.reset_index(drop=True, inplace=True)

        return df

    def format_pwa_ecl_by_deal(scenarios, on_off_df, pwa_ecl_by_deal, first_record_df):
        left_df = on_off_df.copy()
        right_df = pwa_ecl_by_deal.copy()

        # add cols
        left_df['ead_hke'] = left_df['cur_bal_hke'] + left_df['int_accr_hke']

        # keep cols
        # TODO： to be confirmed if the cols are needed
        # left_keep_cols = ['deal_id', 'nxt_pmt_dt', 'prin_amt_hke',
        #                   'int_accr_hke', 'maturity_date_final', 'remaining_life']

        # TODO: to add the unsecured_lgd_scenario cols
        right_keep_cols = ['deal_id', 'ecl_hke']

        # add scenario cols
        for scenario in scenarios:
            right_keep_cols.append(f'ecl_{scenario}_hke')

        # left_df = left_df[left_keep_cols]
        right_df = right_df[right_keep_cols]

        # merge on_off_df and pwa_ecl_by_deal
        df = pd.merge(left_df, right_df, on='deal_id', how='left')

        # merge first record data (ead, pd, lgd from first snapshot_dt)
        df = pd.merge(df, first_record_df, on='deal_id', how='left')

        df.reset_index(drop=True, inplace=True)
        return df

    # Extract first record (by snapshot_dt) for each deal from scenario_ecl_detailed
    # This gets the EAD, PD, and LGD values at reporting date (first snapshot_dt)
    # Optimized: select columns first to reduce data size for sorting
    first_record_cols = ['deal_id', 'snapshot_dt', 'ead']
    for scenario in scenarios:
        first_record_cols.extend([
            f'applied_mpd_{scenario}',
            f'applied_lgd_{scenario}'
        ])

    # Select only needed columns first (reduces data size for sorting)
    first_record_df = scenario_ecl_detailed[first_record_cols].copy()

    # Sort by deal_id and snapshot_dt, then take first record per deal
    # Using drop_duplicates is more efficient than sort + groupby + first
    first_record_df = first_record_df.sort_values(
        ['deal_id', 'snapshot_dt']).drop_duplicates(subset='deal_id', keep='first')

    # Drop snapshot_dt column (not needed in output)
    first_record_df = first_record_df.drop(columns=['snapshot_dt', 'ead'])

    # Rename columns with _0 suffix to indicate first record
    rename_dict = {}
    for scenario in scenarios:
        rename_dict[f'applied_mpd_{scenario}'] = f'applied_mpd_{scenario}_0'
        rename_dict[f'applied_lgd_{scenario}'] = f'applied_lgd_{scenario}_0'

    first_record_df.rename(columns=rename_dict, inplace=True)

    # calculate pwa ecl
    pwa_ecl_detailed = calculate_pwa_ecl(scenario_ecl_detailed, scenario_param)
    pwa_ecl_by_deal = calculate_pwa_ecl(scenario_ecl_by_deal, scenario_param)

    # format ecl results
    pwa_ecl_detailed = format_pwa_ecl_detailed(
        scenarios, on_off_df, pwa_ecl_detailed)
    pwa_ecl_by_deal = format_pwa_ecl_by_deal(
        scenarios, on_off_df, pwa_ecl_by_deal, first_record_df)

    return pwa_ecl_detailed, pwa_ecl_by_deal
