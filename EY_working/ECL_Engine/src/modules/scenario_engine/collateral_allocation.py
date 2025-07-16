import pandas as pd
import numpy as np


class CollateralAllocator:
    def __init__(self,
                 context,
                 coll_df: pd.DataFrame,
                 coll_param: pd.DataFrame):
        self.input = coll_df.copy()
        self.rule = coll_param.copy()
        self.outInterimPath = context.outInterimPath

    def process_all(self):
        self._generate_priority_key()
        # self.input.to_csv(self.outInterimPath /
        #                   "step1_priority_key.csv", index=False)

        self._merge_priority_num()
        # self.input.to_csv(self.outInterimPath /
        #                   "step2_priority_num.csv", index=False)

        self._generate_priority_flags()
        # self.input.to_csv(self.outInterimPath /
        #                   "step3_priority_flags.csv", index=False)

        self._calculate_on_off()
        # self.input.to_csv(self.outInterimPath / "step4_on_off.csv", index=False)

        self._merge_haircut()
        # self.input.to_csv(self.outInterimPath /
        #                   "step5_haircut.csv", index=False)

        self._calculate_collateral_value_post_haircut()
        # self.input.to_csv(self.outInterimPath /
        #                   "step6_post_haircut.csv", index=False)

        self._calculate_ead_post_ccf()
        # self.input.to_csv(self.outInterimPath /
        #                   "step7_post_ccf.csv", index=False)

        self._calculate_allocated_collateral()
        # self.input.to_csv(self.outInterimPath /
        #                   "step8_allocated.csv", index=False)

        return self.input

    def _generate_priority_key(self):
        self.rule['key'] = (self.rule['collateral_agreement_type'] + "_" +
                            self.rule['collateral_deal_relationship'])

        self.input['priority_key'] = (
            self.input['collateral_agreement_type'] +
            "_One_to_" +
            self.input.groupby('collateral_agreement_id')['collateral_agreement_id'].transform('count').apply(
                lambda x: "Many" if x > 1 else "One"
            )
        )
        return self.input

    def _merge_priority_num(self):
        self.input = self.input.merge(
            self.rule[['key', 'collateral_allocation_priority']],
            left_on='priority_key',
            right_on='key',
            how='left'
        )

        return self.input

    def _generate_priority_flags(self):
        for n in range(1, 123):
            flag_column_name = f'priority_{n}_flag'
            self.input[flag_column_name] = self.input['collateral_allocation_priority'].apply(
                lambda x: "Y" if x == n else "N")

        return self.input

    def _calculate_on_off(self):
        # Create a list to store processed rows (for cases where we need to split rows)
        processed_rows = []

        for _, row in self.input.iterrows():
            drawn = row['drawn_amount_hke']
            undrawn = row['undrawn_amount_hke']

            # Case 1: Only drawn_amount > 0
            if drawn > 0 and undrawn == 0:
                new_row = row.copy()
                new_row['guaranteed_amount'] = drawn
                new_row['on_off_ind'] = "ON"
                processed_rows.append(new_row)

            # Case 2: Only undrawn_amount > 0
            elif drawn == 0 and undrawn > 0:
                new_row = row.copy()
                new_row['guaranteed_amount'] = undrawn
                new_row['on_off_ind'] = "OFF"
                processed_rows.append(new_row)

            # Case 3: Both drawn_amount and undrawn_amount > 0
            elif drawn > 0 and undrawn > 0:
                # Create ON row
                on_row = row.copy()
                on_row['guaranteed_amount'] = drawn
                on_row['on_off_ind'] = "ON"
                processed_rows.append(on_row)

                # Create OFF row
                off_row = row.copy()
                off_row['guaranteed_amount'] = undrawn
                off_row['on_off_ind'] = "OFF"
                processed_rows.append(off_row)

            # Case 4: Both drawn_amount and undrawn_amount == 0
            elif drawn == 0 and undrawn == 0:
                new_row = row.copy()
                new_row['guaranteed_amount'] = 0
                new_row['on_off_ind'] = "ON" if row['commit_indicator'] == "Y" else "OFF"
                processed_rows.append(new_row)

        # Convert the list of processed rows back to a DataFrame
        self.input = pd.DataFrame(processed_rows).reset_index(drop=True)

        return self.input

    def _merge_haircut(self):
        self.input = self.input.merge(
            self.rule[['collateral_agreement_type', 'haircut']],
            on='collateral_agreement_type',
            how='left'
        )

        self.input = self.input.drop_duplicates()

        return self.input

    def _calculate_collateral_value_post_haircut(self):
        self.input['collateral_value_post_haircut'] = (
            1 - self.input['haircut']) * self.input['collateral_amount_hke']

        return self.input

    def _calculate_ead_post_ccf(self):
        # Apply the CCF based on the ON/OFF indicator
        self.input['ead_post_ccf'] = self.input.apply(
            lambda row: 0.2 * row['guaranteed_amount'] if row['on_off_ind'] == 'OFF'
            else row['guaranteed_amount'],
            axis=1
        )

        return self.input

    def _calculate_allocated_collateral(self):
        for n in range(1, 123):
            priority_col_name = f'priority_{n}_allocated_collateral_amount'
            priority_flag_col = f'priority_{n}_flag'

            ead_sum = self.input.loc[self.input[priority_flag_col] == 'Y'].groupby(
                'collateral_agreement_id')['ead_post_ccf'].transform('sum')

            self.input[priority_col_name] = self.input.apply(
                lambda row: (row['collateral_value_post_haircut'] * row['ead_post_ccf'] /
                             ead_sum[row.name]) if row[priority_flag_col] == 'Y' and ead_sum[row.name] != 0 else 0,
                axis=1
            )

        self.input['allocated_collateral'] = self.input[[
            f'priority_{n}_allocated_collateral_amount' for n in range(1, 123)]].sum(axis=1)
        self.input['allocated_collateral'] = pd.to_numeric(
            self.input['allocated_collateral'], errors='coerce')

        self.input['allocated_collateral_on'] = np.where(self.input['on_off_ind'] == 'ON',
                                                         self.input[[f'priority_{n}_allocated_collateral_amount' for n in range(
                                                             1, 123)]].sum(axis=1),
                                                         0)

        self.input['allocated_collateral_off'] = np.where(self.input['on_off_ind'] == 'OFF',
                                                          self.input[[f'priority_{n}_allocated_collateral_amount' for n in range(
                                                              1, 123)]].sum(axis=1),
                                                          0)

        return self.input

    def deal_coll_alloc(self, loan_df):
        """
        Allocate collateral from facility level to deal level
        """
        if self.input is None:
            raise ValueError("Input data is not set.")

        if self.input.empty:
            raise ValueError("Input data is empty.")

        # Group and aggregate the input data by facility_nr and collateral_agreement_type
        input_type_level = self.input.groupby(['facility_nr', 'collateral_agreement_type'], as_index=False).agg({
            'drawn_amount': 'sum',
            'as_of_dt': 'first',
            'undrawn_amount': 'sum',
            'collateral_agreement_id': 'first',
            'collateral_currency': 'first',
            'collateral_value_post_haircut': 'sum',
            'ead_post_ccf': 'sum',
            'allocated_collateral_on': 'sum',
            'allocated_collateral_off': 'sum',
        })

        # Clean the loan data
        loan_clean = loan_df[[
            'facility_nr', 'on_off_ind', 'cur_bal', 'deal_id', 'cur_rt']]

        # Calculate the total cur_bal for each facility
        loan_clean['fac_cur_bal'] = loan_clean.groupby(
            'facility_nr')['cur_bal'].transform('sum')

        # Calculate the portion of each row's cur_bal over the total cur_bal
        loan_clean['portion'] = loan_clean['cur_bal'] / \
            loan_clean['fac_cur_bal']

        # Merge input_type_level with loan_clean on facility_nr
        input_deal_level = pd.merge(
            input_type_level, loan_clean, on='facility_nr')

        # Allocate collateral to deal level
        input_deal_level['deal_allocated_collateral_on'] = input_deal_level['allocated_collateral_on'] * \
            input_deal_level['portion']
        input_deal_level['deal_allocated_collateral_off'] = input_deal_level['allocated_collateral_off'] * 0

        return input_deal_level
