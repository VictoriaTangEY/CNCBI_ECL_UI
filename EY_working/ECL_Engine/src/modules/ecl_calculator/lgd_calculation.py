import pandas as pd
import numpy as np


class SecuredLGDCalculator:
    def __init__(self, deal_allocation_df, rule_df):
        self.input_df = deal_allocation_df
        self.rule_df = rule_df
        self.rule_dedup = None

    def _deduplicate_rules(self):
        self.rule_dedup = self.rule_df.drop_duplicates(
            subset=['COLLATERAL_AGREEMENT_TYPE'])

    def _merge_data(self):
        self.input_df = pd.merge(
            self.input_df,
            self.rule_dedup[['COLLATERAL_AGREEMENT_TYPE',
                             'RECOVERY_TIME', 'RECOVER_RANK']],
            on='COLLATERAL_AGREEMENT_TYPE',
            how='left'
        )

    def _calculate_secured_lgd(self):
        # TODO: 20250410: Confirm if effective_yield = cur_rt
        self.input_df['SECURED_LGD'] = 1 - \
            (1 + self.input_df['CUR_RT'] /
             100) ** (-self.input_df['RECOVERY_TIME'])

    def _get_result(self):
        return self.input_df

    def process(self):
        self._deduplicate_rules()
        self._merge_data()
        self._calculate_secured_lgd()
        return self._get_result()


class FinalLGDCalculator:
    def __init__(self, secured_result, ead_df, rule_df, fwd_index_df):
        self.input = secured_result
        self.ead = ead_df
        self.rule_df = rule_df
        self.fwd_index = fwd_index_df
        self.input_sample_merged = None

    def _preprocess(self):
        # Merge with rules
        input_sample = self.input[self.input['DEAL_ID'].isin(
            self.ead['DEAL_ID'])]
        input_sample_clean = input_sample[['COLLATERAL_AGREEMENT_ID', 'COLLATERAL_AGREEMENT_TYPE',
                                           'COLLATERAL_CURRENCY', 'FACILITY_NR', 'DEAL_ID',
                                           'CUR_RT', 'SECURED_LGD', 'RECOVER_RANK',
                                           'COLLATERAL_VALUE_POST_HAIRCUT', 'EAD_POST_CCF',
                                           'AS_OF_DT', 'ON_OFF_IND',
                                           'DEAL_ALLOCATED_COLLATERAL_ON',
                                           'DEAL_ALLOCATED_COLLATERAL_OFF']]

        # Convert dates to datetime objects
        input_sample_clean['AS_OF_DT'] = pd.to_datetime(
            input_sample_clean['AS_OF_DT'], format='%d%b%Y:%H:%M:%S')

        # Ensure SNAPSHOT_DTE is datetime in both DataFrames
        # TODO: move to data_preprocessor after testing
        self.ead['SNAPSHOT_DTE'] = pd.to_datetime(self.ead['SNAPSHOT_DTE'])
        self.fwd_index['DTE'] = pd.to_datetime(
            self.fwd_index['DTE'])

        # Merge with EAD data
        self.input_sample_merged = pd.merge(
            input_sample_clean,
            self.ead[['DEAL_ID', 'SNAPSHOT_DTE',
                      'PRIN_REM', 'ACCR_INT', 'ead']],
            on='DEAL_ID',
            how='left'
        )

        # Clean and standardize COLLATERAL_AGREEMENT_TYPE
        self.input_sample_merged['COLLATERAL_AGREEMENT_TYPE'] = self.input_sample_merged['COLLATERAL_AGREEMENT_TYPE'].str.strip()

        # Melt forward index
        fwd_index_long = self.fwd_index.melt(id_vars=['DTE'],
                                             var_name='COLLATERAL_AGREEMENT_TYPE',
                                             value_name='FWD_INX')

        # Clean COLLATERAL_AGREEMENT_TYPE in melted DataFrame
        fwd_index_long['COLLATERAL_AGREEMENT_TYPE'] = fwd_index_long['COLLATERAL_AGREEMENT_TYPE'].str.strip()

        # Merge forward index into input
        self.input_sample_merged = pd.merge(self.input_sample_merged, fwd_index_long,
                                            left_on=['SNAPSHOT_DTE',
                                                     'COLLATERAL_AGREEMENT_TYPE'],
                                            right_on=['DTE',
                                                      'COLLATERAL_AGREEMENT_TYPE'],
                                            how='left')
        # print('input_sample_merged', self.input_sample_merged.head())

    def _calculate_forward_looking_adjustments(self):
        # Calculate FORWARD_LOOKING_ADJ_ALLOCATED_COLLATERAL_VALUE
        self.input_sample_merged['FORWARD_LOOKING_ADJ_ALLOCATED_COLLATERAL_VALUE'] = np.where(
            self.input_sample_merged['ON_OFF_IND'] == 'N',
            self.input_sample_merged['DEAL_ALLOCATED_COLLATERAL_ON'] *
            (1 + self.input_sample_merged['FWD_INX']),
            self.input_sample_merged['DEAL_ALLOCATED_COLLATERAL_OFF'] *
            (1 + self.input_sample_merged['FWD_INX'])
        )

    def _calculate_corresponding_total_exposure_1(self):
        def calculate_corresponding_total_exposure_1(group):
            ead = group['ead'].values[0]
            # for now, 61 types of collateral
            sums = {rank: 0 for rank in range(1, 62)}

            for rank in range(1, 62):
                if rank == 1:
                    matched_values = group['FORWARD_LOOKING_ADJ_ALLOCATED_COLLATERAL_VALUE'].loc[group['RECOVER_RANK'] == rank]
                    total_exposure = min(
                        matched_values.values[0], ead) if not matched_values.empty else 0
                elif rank in range(2, 61):  # for recover_rank = 2~60
                    previous_sums = sums[1]
                    matched_values = group['FORWARD_LOOKING_ADJ_ALLOCATED_COLLATERAL_VALUE'].loc[group['RECOVER_RANK'] == rank]
                    total_exposure = min(matched_values.values[0], max(
                        0, ead - previous_sums)) if not matched_values.empty else 0
                else:  # for highest rank
                    previous_exposures = group.loc[group['RECOVER_RANK'].isin(
                        range(1, rank)), 'CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_1'].sum()
                    total_exposure = max(0, ead - previous_exposures)

                sums[rank] = total_exposure
                group.loc[group['RECOVER_RANK'] == rank,
                          'CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_1'] = total_exposure

            return group

        # Calculate each group
        self.input_sample_merged = self.input_sample_merged.groupby(
            ['ead', 'ON_OFF_IND', 'SNAPSHOT_DTE', 'DEAL_ID']).apply(calculate_corresponding_total_exposure_1)

    def _calculate_corresponding_total_exposure_2(self):
        def calculate_corresponding_total_exposure_2(row):
            if row['ON_OFF_IND'] == 'F':
                return row['CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_1']
            elif row['ON_OFF_IND'] == 'N':
                matching_rows = self.input_sample_merged[
                    (self.input_sample_merged['DEAL_ID'] == row['DEAL_ID']) &
                    (self.input_sample_merged['ON_OFF_IND'] == 'N') &
                    (self.input_sample_merged['SNAPSHOT_DTE']
                     == row['AS_OF_DT'])
                ]
                if not matching_rows.empty:
                    return matching_rows['CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_1'].values[0]
            return None

        self.input_sample_merged['CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_2'] = self.input_sample_merged.apply(
            calculate_corresponding_total_exposure_2, axis=1)

    def _calculate_secured_portion(self):
        # Calculate SECURED_PORTION_1
        def calculate_secured_portion_1(row):
            if row['CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_1'] == 0:
                return 1
            else:
                return min(row['FORWARD_LOOKING_ADJ_ALLOCATED_COLLATERAL_VALUE'] / row['CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_1'], 1)

        self.input_sample_merged['SECURED_PORTION_1'] = self.input_sample_merged.apply(
            calculate_secured_portion_1, axis=1)

        # Calculate SECURED_PORTION_2
        # def calculate_secured_portion_2(row):
        #     if row['CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_2'] == 0:
        #         return 1
        #     else:
        #         return min(row['FORWARD_LOOKING_ADJ_ALLOCATED_COLLATERAL_VALUE'] / row['CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_2'], 1)

        def calculate_secured_portion_2(row):
            try:
                numerator = row['FORWARD_LOOKING_ADJ_ALLOCATED_COLLATERAL_VALUE']
                denominator = row['CORRESPONDING_TOTAL_EXPOSURE_PRE_CCF_2']

                # Checking denominator validity
                if pd.isna(denominator) or denominator <= 0:
                    return 1  # or return some other default value

                return min(numerator / denominator, 1)
            except Exception as e:
                print(
                    f"Error in Deal {row.get('DEAL_ID', 'Unknown')}: {str(e)}")
                return 0.0  # or return some other default value

        self.input_sample_merged['SECURED_PORTION_2'] = self.input_sample_merged.apply(
            calculate_secured_portion_2, axis=1)

    def _finalize_lgd(self):
        # TODO: 20250411: unsecured lgd assumed as 52% for now
        self.input_sample_merged['UNSECURED_LGD'] = 0.52

        self.input_sample_merged['FINAL_LGD_1'] = (
            self.input_sample_merged['SECURED_LGD'] * self.input_sample_merged['SECURED_PORTION_1'] +
            (1 - self.input_sample_merged['SECURED_PORTION_1']
             ) * self.input_sample_merged['UNSECURED_LGD']
        )

        self.input_sample_merged['FINAL_LGD_2'] = (
            self.input_sample_merged['SECURED_LGD'] * self.input_sample_merged['SECURED_PORTION_2'] +
            (1 - self.input_sample_merged['SECURED_PORTION_2']
             ) * self.input_sample_merged['UNSECURED_LGD']
        )

        # print("First 5 rows of the merged:\n", self.input_sample_merged.head())
        return self.input_sample_merged

    def run_analysis(self):
        self._preprocess()
        self._calculate_forward_looking_adjustments()
        self._calculate_corresponding_total_exposure_1()
        self._calculate_corresponding_total_exposure_2()
        self._calculate_secured_portion()
        return self._finalize_lgd()

    # def save_to_csv(self, LGD_output):
    #     result_df = self.run_analysis()
    #     if result_df is None:
    #         raise ValueError("The merged DataFrame is None, cannot save to CSV.")
    #     result_df.to_csv(LGD_output, index=False)
    #     return result_df
