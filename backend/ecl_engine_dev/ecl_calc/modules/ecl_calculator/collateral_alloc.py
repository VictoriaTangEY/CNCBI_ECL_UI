import pandas as pd
import numpy as np
import re


class CollateralAllocator:
    def __init__(self, context, param):
        self.context = context
        self.coll_param = param['collateral_param']

    def run(self, on_off_df, coll_df):
        """
        Main method to run collateral allocation process

        Args:
            on_off_df: DataFrame containing on/off balance sheet data
            coll_df: DataFrame containing collateral data

        Returns:
            tuple: (processed_on_off_df, processed_coll_df)
        """
        # Check if collateral data exists
        if coll_df.empty:
            # Return original data without allocation
            return on_off_df, coll_df

        # Step 1: Prepare base amounts in on_off_df
        on_off_df = self._prepare_base_amounts(on_off_df)

        # Step 2: Process collateral data
        coll_df = self._process_collateral_data(on_off_df, coll_df)

        # Step 3: Perform collateral allocation
        coll_df = self._allocate_collateral(coll_df)

        # Step 4: Map allocated collateral to on_off_df
        on_off_df = self._map_collateral_to_on_off(on_off_df, coll_df)

        return on_off_df, coll_df

    def _prepare_base_amounts(self, on_off_df):
        """
        Prepare base amounts for collateral allocation

        Args:
            on_off_df: DataFrame containing on/off balance sheet data

        Returns:
            DataFrame: Updated on_off_df with base amount columns
        """
        # Create a copy to avoid modifying original data
        df = on_off_df.copy()

        # Calculate base_amt_post_ccf_hke = cur_bal_hke * ccf
        # Handle both possible column names from data preprocessor
        if 'cur_bal_hke' in df.columns:
            df['post_ccf_base_amount'] = df['cur_bal_hke'] * df['ccf']
        else:
            raise ValueError(
                "No 'cur_bal_hke' column found in on_off_df")

        # Calculate base_amt_fac_level using transform (avoid merge)
        df['post_ccf_base_amt_fac_level'] = df.groupby(
            'facility_nr')['post_ccf_base_amount'].transform('sum')

        # Calculate base_amt_deal_pct = deal's base_amt_post_ccf / base_amt_fac_level
        # Handle division by zero by using safe division
        df['post_ccf_base_amt_deal_pct'] = df['post_ccf_base_amount'] / \
            df['post_ccf_base_amt_fac_level'].replace(0, np.nan)

        # Fill NaN values (from division by zero) with 0
        df['post_ccf_base_amt_deal_pct'] = df['post_ccf_base_amt_deal_pct'].fillna(
            0)

        # print('on_off_df + base amount\n', df.head())

        return df

    def _process_collateral_data(self, on_off_df, coll_df):
        """
        Process collateral data by joining with collateral parameters and calculating collateral amounts

        Args:
            coll_df: DataFrame containing collateral data

        Returns:
            DataFrame: Updated coll_df with processed collateral amounts
        """
        # Create a copy to avoid modifying original data
        df = coll_df.copy()

        # Get collateral parameters from param
        if self.coll_param.empty:
            raise ValueError(
                "Collateral parameters (collateral_param) are required but not provided or empty.")
        else:
            # Left join collateral_param on collateral_agreement_type
            df = df.merge(
                self.coll_param,
                on='collateral_agreement_type',
                how='left'
            )
            # Fill missing haircut values with 0
            df['haircut'] = df['haircut'].fillna(0)
            # Fill missing priority values with 999 (low priority)
            if 'collateral_allocation_priority' in df.columns:
                df['collateral_allocation_priority'] = df['collateral_allocation_priority'].fillna(
                    999)

        # Calculate coll_amt = collateral_amount_hke * (1 - haircut)
        # Handle both possible column names from data preprocessor
        if 'collateral_amount_hke' in df.columns:
            df['post_haircut_coll_amt'] = df['collateral_amount_hke'] * \
                (1 - df['haircut'])
        else:
            raise ValueError(
                "No 'collateral_amount_hke' column found in collateral data")

        # Merge base_amt_fac_level from on_off_df using facility_nr
        if 'facility_nr' in df.columns and 'post_ccf_base_amt_fac_level' in on_off_df.columns:
            df = df.merge(
                on_off_df[['facility_nr', 'post_ccf_base_amt_fac_level']
                          ].drop_duplicates(),
                on='facility_nr',
                how='left'
            )
        else:
            raise ValueError(
                "facility_nr or post_ccf_base_amt_fac_level missing in on_off_df")

        return df

    def _allocate_collateral(self, coll_df):
        """
        Perform collateral allocation based on new methodology

        Args:
            coll_df: Processed collateral DataFrame with coll_amt column

        Returns:
            DataFrame: Updated coll_df with allocated_collateral_amount column
        """
        df = coll_df.copy()

        # Initialize allocated_collateral_amount column
        df['allocated_collateral_amount'] = 0.0

        # Classify collateral_agreement_id into two types:
        # secure one: one collateral_agreement_id only covers one facility_nr
        # secure many: one collateral_agreement_id covers more than one facility_nr
        facility_counts = df.groupby('collateral_agreement_id')[
            'facility_nr'].nunique()
        secure_one_coll_ids = facility_counts[facility_counts == 1].index
        secure_many_coll_ids = facility_counts[facility_counts > 1].index

        print(
            f'secure one: {len(secure_one_coll_ids)}, secure many: {len(secure_many_coll_ids)}')

        # Step 1: Handle secure_one case - direct allocation (batch operation)
        if len(secure_one_coll_ids) > 0:
            # Create mask for secure_one cases
            secure_one_mask = df['collateral_agreement_id'].isin(
                secure_one_coll_ids)

            # Direct allocation: allocated_collateral_amount = coll_amt
            df.loc[secure_one_mask,
                   'allocated_collateral_amount'] = df.loc[secure_one_mask, 'post_haircut_coll_amt']

            print(f'Processed {secure_one_mask.sum()} secure_one allocations')

        # Step 2: Handle secure_many case using pivot table approach
        # All secure_many collaterals are processed once, without considering priority
        if len(secure_many_coll_ids) > 0:
            print(
                f'Processing {len(secure_many_coll_ids)} secure_many cases (all at once, no priority)')

            # Initialize remaining base amount (exposure after secure_one allocation)
            df['remaining_base_amt'] = np.maximum(0, df['post_ccf_base_amt_fac_level'] -
                                                  df['allocated_collateral_amount'])

            # Filter all secure_many collateral data (no priority filtering)
            secure_many_df = df[df['collateral_agreement_id'].isin(
                secure_many_coll_ids)].copy()

            if secure_many_df.empty:
                print('No secure_many collateral data found')
            else:
                # Filter facilities that have remaining base amount > 0
                # (Note: over-collateralization is allowed, so this is just for allocation weights)
                active_facilities = df[df['remaining_base_amt']
                                       > 0]['facility_nr'].unique()
                secure_many_df = secure_many_df[secure_many_df['facility_nr'].isin(
                    active_facilities)]

                if secure_many_df.empty:
                    print('No active facilities for secure_many allocation')
                else:
                    # Create pivot table: facility_nr × collateral_agreement_id
                    pivot_data = secure_many_df.pivot_table(
                        index='facility_nr',
                        columns='collateral_agreement_id',
                        values='post_haircut_coll_amt',
                        aggfunc='first',  # Should be same for each coll_id
                        fill_value=0
                    )

                    print(f'Pivot table shape: {pivot_data.shape}')

                    # Get remaining base amounts for active facilities (from secure_one allocation)
                    remaining_amt = df[df['facility_nr'].isin(active_facilities)].groupby(
                        'facility_nr')['remaining_base_amt'].first()

                    # Create allocation matrix using vectorized operations
                    allocation_matrix = pd.DataFrame(
                        0, index=pivot_data.index, columns=pivot_data.columns)

                    # Process each collateral agreement
                    for coll_id in pivot_data.columns:
                        # Get facilities covered by this collateral
                        covered_facilities = pivot_data[pivot_data[coll_id] > 0].index

                        if len(covered_facilities) == 0:
                            continue

                        # Get total collateral amount for this coll_id
                        total_coll_amt = secure_many_df[secure_many_df['collateral_agreement_id']
                                                        == coll_id]['post_haircut_coll_amt'].iloc[0]

                        # Get remaining base amounts for covered facilities
                        fac_remaining = remaining_amt[covered_facilities]
                        total_remaining = fac_remaining.sum()

                        # If total remaining is 0 or negative, skip allocation
                        # (This shouldn't happen if we filtered active_facilities, but safe check)
                        if total_remaining <= 0:
                            continue

                        # Calculate allocation weights based on remaining base amounts
                        weights = fac_remaining / total_remaining

                        # Allocate collateral proportionally
                        allocations = total_coll_amt * weights

                        # Store in allocation matrix
                        allocation_matrix.loc[covered_facilities,
                                              coll_id] = allocations

                    # Batch update allocated_collateral_amount using vectorized operations
                    # Convert allocation matrix to long format for efficient merging
                    allocation_long = allocation_matrix.stack().reset_index()
                    allocation_long.columns = [
                        'facility_nr', 'collateral_agreement_id', 'allocation_amount']
                    allocation_long = allocation_long[allocation_long['allocation_amount'] > 0]

                    if not allocation_long.empty:
                        # Merge with main dataframe for batch update
                        df_temp = df.merge(allocation_long, on=[
                                           'facility_nr', 'collateral_agreement_id'], how='left')
                        df_temp['allocation_amount'] = df_temp['allocation_amount'].fillna(
                            0)
                        df['allocated_collateral_amount'] += df_temp['allocation_amount']
                        print(
                            f'Allocated secure_many collateral to {len(allocation_long)} facility-collateral pairs')
                    else:
                        print('No secure_many allocations made')

        return df

    def _map_collateral_to_on_off(self, on_off_df, coll_df):
        """
        Map allocated collateral to on_off_df at deal level

        Args:
            on_off_df: DataFrame with deal-level data
            coll_df: DataFrame with allocated collateral amounts

        Returns:
            DataFrame: Updated on_off_df with deal-level allocated collateral
        """
        df = on_off_df.copy()

        # Create facility-level allocation DataFrame from coll_df
        facility_allocation = coll_df.groupby(
            'facility_nr')['allocated_collateral_amount'].sum().reset_index()
        facility_allocation.rename(columns={
                                   'allocated_collateral_amount': 'facility_allocated_collateral_amt'}, inplace=True)

        # Merge with on_off_df
        df = df.merge(facility_allocation, on='facility_nr', how='left')
        df['facility_allocated_collateral_amt'] = df['facility_allocated_collateral_amt'].fillna(
            0)

        # Calculate deal-level allocated collateral using base_amt_deal_pct
        df['allocated_collateral_amt'] = df['facility_allocated_collateral_amt'] * \
            df['post_ccf_base_amt_deal_pct']

        return df
