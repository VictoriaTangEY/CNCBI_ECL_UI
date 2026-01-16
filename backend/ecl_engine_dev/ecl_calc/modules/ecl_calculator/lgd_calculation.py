import pandas as pd
import numpy as np
import time
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from ecl_calc.modules.scenario_engine.unsecured_lgd_map import calculate_unsecured_lgd


class LGDCalculation:
    def __init__(self, context, param, on_off_df):
        self.context = context
        self.param = param
        self.on_off_df = on_off_df[['deal_id',
                                    'facility_nr', 'allocated_collateral_amt', 'segment', 'sub_segment', 'eir']].copy()

        # Extract frequently used parameters to avoid repeated access
        self.collateral_param = param.get('collateral_param', pd.DataFrame())
        self.forward_looking_collateral_param = param.get(
            'foward_looking_collateral_param', pd.DataFrame())
        self.unsecured_lgd_param = param.get(
            'unsecured_lgd_param', pd.DataFrame())
        self.option_param = param.get('option_param', pd.DataFrame())

        # Extract option settings for ead_ calculation
        self.use_constant_ead = False
        if not self.option_param.empty:
            constant_ead_mask = (
                (self.option_param['function'] == 'constant_ead_for_lgd') &
                (self.option_param['option'] == 'Y')
            )
            self.use_constant_ead = constant_ead_mask.any()

        # get scenarios
        self.scenarios = self.unsecured_lgd_param['scenario'].unique().tolist()

        # Create rank mapping dictionary once for efficiency
        self.rank_mapping = {}
        if not self.collateral_param.empty:
            self.rank_mapping = self.collateral_param.set_index('collateral_agreement_type')[
                'collateral_secured_rank_for_ead_allocation'].to_dict()
            self.recovery_time_mapping = self.collateral_param.set_index('collateral_agreement_type')[
                'recovery_time'].to_dict()

        # create eir mapping
        self.eir_mapping = self.on_off_df.set_index('deal_id')['eir'].to_dict()

        # Pre-create forward looking collateral pivot table for efficiency
        self.forward_looking_pivot = None
        if not self.forward_looking_collateral_param.empty:
            self.forward_looking_pivot = self.forward_looking_collateral_param.pivot_table(
                index=['forward_adjustment_factor', 'quarter'],
                columns='scenario',
                values='forecast_value',
                aggfunc='first'
            )

    def run(self, ead_df, coll_df):
        """
        Run the complete LGD calculation process - optimized by deal processing

        Args:
            ead_df: DataFrame containing EAD data
            coll_df: DataFrame containing collateral type data (facility_nr, collateral_agreement_type)

        Returns:
            DataFrame: EAD DataFrame with LGD calculations
        """
        start_time = time.time()
        print(
            f"Starting LGD calculation for {len(ead_df['deal_id'].unique())} deals...")

        if ead_df.empty:
            return ead_df

        # Step 1: Prepare collateral data
        prep_start = time.time()
        # Merge coll_df (collateral types) with on_off_df (deal level amounts) using facility_nr
        coll_alloc_df_prepared = coll_df.merge(
            self.on_off_df[['deal_id', 'facility_nr',
                            'allocated_collateral_amt']],
            on='facility_nr',
            how='inner'
        ).groupby(['deal_id', 'collateral_agreement_type']).agg({
            'allocated_collateral_amt': 'sum'
        }).reset_index()
        print(f"Collateral preparation: {time.time() - prep_start:.2f}s")

        # Step 2: Separate secured vs unsecured deals
        sep_start = time.time()
        unique_deals = set(ead_df['deal_id'].unique())
        secured_deals = set(coll_alloc_df_prepared['deal_id'].unique())
        unsecured_deals = unique_deals - secured_deals
        print(
            f"Deal separation: {len(secured_deals)} secured, {len(unsecured_deals)} unsecured - {time.time() - sep_start:.2f}s")

        # Step 3: Pre-compute unsecured LGD for all deals
        unsec_start = time.time()
        ead_with_unsecured_lgd = calculate_unsecured_lgd(
            ead_df, self.on_off_df, self.unsecured_lgd_param)
        print(f"Unsecured LGD calculation: {time.time() - unsec_start:.2f}s")

        # Step 4: Process unsecured deals
        unsec_proc_start = time.time()
        ead_unsecured = ead_with_unsecured_lgd[ead_with_unsecured_lgd['deal_id'].isin(
            unsecured_deals)].copy()

        # Rename unsecured_lgd columns to applied_lgd for consistency
        for scenario in self.scenarios:
            if f'unsecured_lgd_{scenario}' in ead_unsecured.columns:
                ead_unsecured[f'applied_lgd_{scenario}'] = ead_unsecured[f'unsecured_lgd_{scenario}']
                ead_unsecured = ead_unsecured.drop(
                    columns=[f'unsecured_lgd_{scenario}'])
        print(
            f"Unsecured deal processed: {time.time() - unsec_proc_start:.2f}s")

        # Step 5: Process secured deals in parallel
        sec_start = time.time()
        print(f"Processing {len(secured_deals)} secured deals in parallel...")
        secured_result_dfs = self._process_secured_deals_parallel(
            ead_df, coll_alloc_df_prepared, ead_with_unsecured_lgd, secured_deals)
        print(f"Secured deal processed: {time.time() - sec_start:.2f}s")

        # Step 6: Combine results
        combine_start = time.time()
        result_dfs = []
        if not ead_unsecured.empty:
            result_dfs.append(ead_unsecured)
        if secured_result_dfs:
            secured_result = pd.concat(secured_result_dfs, ignore_index=True)
            result_dfs.append(secured_result)

        if result_dfs:
            final_result = pd.concat(result_dfs, ignore_index=True)
        else:
            final_result = ead_df
        print(f"Result combined: {time.time() - combine_start:.2f}s")

        total_time = time.time() - start_time
        print(f"Total LGD calculation completed in {total_time:.2f}s")
        return final_result

    def _process_secured_deals_parallel(self, ead_df, coll_alloc_df_prepared, ead_with_unsecured_lgd, secured_deals):
        """
        Process secured deals in parallel using multiprocessing

        Args:
            ead_df: DataFrame containing EAD data
            coll_alloc_df_prepared: DataFrame containing prepared collateral allocation data
            ead_with_unsecured_lgd: DataFrame with pre-computed unsecured LGD
            secured_deals: Set of secured deal IDs

        Returns:
            List of DataFrames: Results from processing each secured deal
        """
        if not secured_deals:
            return []

        prep_group_start = time.time()
        print(
            f"Pre-grouping DataFrames by deal_id for {len(secured_deals)} secured deals...")

        # Group ead_df by deal_id (only for secured deals to save memory)
        secured_deals_list = list(secured_deals)
        ead_df_secured = ead_df[ead_df['deal_id'].isin(secured_deals_list)]
        ead_df_grouped = {deal_id: group_df for deal_id,
                          group_df in ead_df_secured.groupby('deal_id')}

        # Group coll_alloc_df_prepared by deal_id
        coll_alloc_grouped = {deal_id: group_df for deal_id,
                              group_df in coll_alloc_df_prepared.groupby('deal_id')}

        # Group ead_with_unsecured_lgd by deal_id (only for secured deals to save memory)
        unsecured_lgd_secured = ead_with_unsecured_lgd[ead_with_unsecured_lgd['deal_id'].isin(
            secured_deals_list)]
        unsecured_lgd_grouped = {deal_id: group_df for deal_id,
                                 group_df in unsecured_lgd_secured.groupby('deal_id')}

        print(f"DataFrames grouped in {time.time() - prep_group_start:.2f}s")

        # Optimized: Use batch processing instead of single deal processing
        # This reduces process communication overhead from 35000 tasks to ~70-350 batches
        batch_prep_start = time.time()

        # Determine optimal batch size based on number of deals
        if len(secured_deals) >= 20000:
            batch_size = 1000  # Large datasets: larger batches to reduce overhead
        elif len(secured_deals) >= 5000:
            batch_size = 500   # Medium datasets: medium batches
        else:
            batch_size = 200   # Small datasets: smaller batches for better load balancing

        # Split secured_deals into batches
        secured_deals_list = list(secured_deals)
        batches = []
        for i in range(0, len(secured_deals_list), batch_size):
            batch_deal_ids = secured_deals_list[i:i + batch_size]
            batches.append({
                'deal_ids': batch_deal_ids,
                'ead_df_grouped': {deal_id: ead_df_grouped.get(deal_id, pd.DataFrame())
                                   for deal_id in batch_deal_ids},
                'coll_alloc_grouped': {deal_id: coll_alloc_grouped.get(deal_id, pd.DataFrame())
                                       for deal_id in batch_deal_ids},
                'unsecured_lgd_grouped': {deal_id: unsecured_lgd_grouped.get(deal_id, pd.DataFrame())
                                          for deal_id in batch_deal_ids},
                'context': self.context,
                'param': self.param,
                'on_off_df': self.on_off_df
            })

        print(
            f"Split into {len(batches)} batches (batch_size={batch_size}) in {time.time() - batch_prep_start:.2f}s")

        # Process batches in parallel with dynamic worker limit based on CPU cores
        secured_result_dfs = []
        cpu_count = os.cpu_count() or 4

        # Calculate workers based on CPU cores (at least 1, at most CPU cores - 1)
        cpu_based_workers = max(1, cpu_count - 1)

        # Dynamic upper limit based on CPU core count
        if cpu_count >= 16:
            max_workers_limit = 10  # High-end servers: up to 10 workers
        elif cpu_count >= 8:
            max_workers_limit = 8   # Medium servers: up to 8 workers
        elif cpu_count >= 4:
            max_workers_limit = 5   # Standard servers: up to 5 workers
        else:
            # Low-end: use available cores
            max_workers_limit = max(1, cpu_count - 1)

        # Final worker count: min of (CPU-based, dynamic limit, number of batches)
        max_workers = min(cpu_based_workers,
                          max_workers_limit, len(batches))
        print(f"Using {max_workers} worker(s) for parallel processing (CPU cores: {cpu_count}, max limit: {max_workers_limit}, batches: {len(batches)})")

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batch tasks (much fewer tasks than individual deals)
            submit_start = time.time()
            future_to_batch = {
                executor.submit(_process_batch_deals_worker, batch_data): batch_data
                for batch_data in batches
            }
            submit_time = time.time() - submit_start
            print(
                f"Submitted {len(batches)} batch tasks in {submit_time:.2f}s")

            # Collect results as they complete
            completed_batches = 0
            total_deals_processed = 0
            for future in as_completed(future_to_batch):
                batch_data = future_to_batch[future]
                try:
                    batch_results = future.result()  # List of DataFrames
                    secured_result_dfs.extend(batch_results)
                    completed_batches += 1
                    total_deals_processed += len(batch_data['deal_ids'])

                    # Print progress for every batch completion
                    print(
                        f"Completed {completed_batches}/{len(batches)} batches ({total_deals_processed}/{len(secured_deals)} deals)")
                except Exception as exc:
                    print(
                        f'Batch {completed_batches + 1} generated an exception: {exc}')

        return secured_result_dfs

    def _process_single_deal(self, deal_id, deal_ead_df, deal_coll_alloc_df, deal_unsecured_lgd):
        """
        Process LGD calculation for a single deal

        Args:
            deal_id: Deal ID
            deal_ead_df: DataFrame with EAD data for a single deal
            deal_coll_alloc_df: DataFrame with collateral allocation data for a single deal
            deal_unsecured_lgd: DataFrame with pre-computed unsecured LGD for this deal

        Returns:
            DataFrame: EAD DataFrame with LGD calculations for the deal
        """
        # Step 1-3: merge/explode coll type and coll amt for this deal
        ead_with_coll = self.merge_and_explode_collateral(
            deal_ead_df, deal_coll_alloc_df)

        # Step 4: Calculate forward-looking collateral
        ead_with_coll = self.calculate_forward_looking_collateral(
            ead_with_coll)

        # Step 5: Calculate collateral recover rank
        ead_with_coll = self.calculate_collateral_recover_rank(ead_with_coll)

        # Step 6: Calculate secured LGD
        ead_with_coll = self.calculate_secured_lgd(ead_with_coll)

        # Step 7: Use pre-computed unsecured LGD
        ead_with_coll = self._merge_precomputed_unsecured_lgd(
            ead_with_coll, deal_unsecured_lgd)

        # Step 8: Calculate corresponding exposure and secured portion
        ead_with_coll = self.calculate_corresponding_exposure_and_secured_portion(
            ead_with_coll)

        # Step 9: Calculate final LGD
        ead_with_coll = self.calculate_final_lgd(ead_with_coll)

        # Step 10: Simple aggregation to deal & snapshot_dt level
        final_result = self._aggregate_to_deal_level(ead_with_coll)

        return final_result

    def _merge_precomputed_unsecured_lgd(self, ead_with_coll, deal_unsecured_lgd):
        """
        Merge pre-computed unsecured LGD values to the deal data

        Args:
            ead_with_coll: DataFrame with exploded collateral data
            deal_unsecured_lgd: DataFrame with pre-computed unsecured LGD for this deal

        Returns:
            DataFrame: DataFrame with unsecured LGD columns added
        """
        if deal_unsecured_lgd.empty:
            # If no unsecured LGD data, set all scenarios to 1
            for scenario in self.scenarios:
                ead_with_coll[f'unsecured_lgd_{scenario}'] = 1.0
            return ead_with_coll

        # Get unsecured LGD columns from pre-computed data
        unsecured_lgd_cols = [
            col for col in deal_unsecured_lgd.columns if col.startswith('unsecured_lgd_')]

        # For each unsecured LGD column, take the first value (should be same for all records of same deal)
        for col in unsecured_lgd_cols:
            ead_with_coll[col] = deal_unsecured_lgd[col].iloc[0]

        return ead_with_coll

    def _aggregate_to_deal_level(self, ead_with_coll):
        """
        Simple aggregation to deal & snapshot_dt level using weighted average

        Args:
            ead_with_coll: DataFrame with final LGD calculations

        Returns:
            DataFrame: Aggregated DataFrame at deal & snapshot_dt level
        """
        if ead_with_coll.empty:
            return ead_with_coll

        # Get final_lgd columns
        final_lgd_cols = [
            col for col in ead_with_coll.columns if col.startswith('final_lgd_')]

        # Group by deal_id and snapshot_dt
        grouped = ead_with_coll.groupby(['deal_id', 'snapshot_dt'])

        # Define aggregation dictionary
        agg_dict = {}

        # For basic columns, take first value
        basic_cols = ['prin_rem', 'accrued_int', 'ead', 'ead_', 'quarter',
                      'forward_adjustment_factor', 'eir', 'recovery_time',
                      'secured_lgd', 'segment', 'sub_segment']

        for col in basic_cols:
            if col in ead_with_coll.columns:
                agg_dict[col] = 'first'

        # For unsecured LGD columns, take first value (should be same for all records)
        for col in ead_with_coll.columns:
            if col.startswith('unsecured_lgd_'):
                agg_dict[col] = 'first'

        # For final LGD columns, calculate weighted average using corr_ttl_ead as weight
        for col in final_lgd_cols:
            scenario = col.replace('final_lgd_', '')
            weight_col = f'corr_ttl_ead_{scenario}'
            if weight_col in ead_with_coll.columns:
                # Calculate weighted average
                ead_with_coll[f'{col}_weighted'] = ead_with_coll[col] * \
                    ead_with_coll[weight_col]
                ead_with_coll[f'{weight_col}_sum'] = ead_with_coll[weight_col]
                agg_dict[f'{col}_weighted'] = 'sum'
                agg_dict[f'{weight_col}_sum'] = 'sum'

        # Perform aggregation
        result = grouped.agg(agg_dict).reset_index()

        # Calculate final weighted averages and rename to applied_lgd
        for col in final_lgd_cols:
            scenario = col.replace('final_lgd_', '')
            weight_col = f'corr_ttl_ead_{scenario}'
            if f'{col}_weighted' in result.columns:
                # Calculate weighted average: sum(weighted_values) / sum(weights)
                applied_lgd_col = f'applied_lgd_{scenario}'
                result[applied_lgd_col] = result[f'{col}_weighted'] / \
                    result[f'{weight_col}_sum'].replace(0, 1)
                result[applied_lgd_col] = result[applied_lgd_col].fillna(0)
                # Clean up temporary columns
                result = result.drop(
                    columns=[f'{col}_weighted', f'{weight_col}_sum'])

        return result

    def merge_and_explode_collateral(self, ead_df, deal_coll_alloc_df):
        """
        Merge collateral allocation data to EAD data and explode by collateral types
        Each EAD record will be mapped to all collateral types for the deal

        Args:
            ead_df: DataFrame containing EAD data for a single deal
            deal_coll_alloc_df: DataFrame containing collateral allocation for a single deal

        Returns:
            DataFrame: EAD DataFrame with exploded collateral information
        """
        if deal_coll_alloc_df.empty:
            # If no collateral data, return original ead_df with empty collateral columns
            ead_df_result = ead_df.copy()
            ead_df_result['collateral_agreement_type'] = None
            ead_df_result['allocated_collateral_amt'] = 0.0
            return ead_df_result

        # Create exploded records
        exploded_records = []

        for _, ead_row in ead_df.iterrows():
            # Get all collateral types for this deal
            for _, coll_row in deal_coll_alloc_df.iterrows():
                # Create a new record for each collateral type
                new_record = ead_row.copy()
                new_record['collateral_agreement_type'] = coll_row['collateral_agreement_type']
                new_record['allocated_collateral_amt'] = coll_row['allocated_collateral_amt']
                exploded_records.append(new_record)

        # Convert exploded records to DataFrame
        if exploded_records:
            ead_df_result = pd.DataFrame(exploded_records)
        else:
            ead_df_result = pd.DataFrame()

        return ead_df_result

    def calculate_forward_looking_collateral(self, ead_df):
        """
        Calculate forward-looking adjusted allocated collateral amount

        Args:
            ead_df: DataFrame with exploded collateral information

        Returns:
            DataFrame: EAD DataFrame with forward-looking collateral amounts
        """
        if ead_df.empty:
            return ead_df

        df = ead_df.copy()

        # Step 1: Calculate quarter for each deal
        df = self._calculate_quarter(df)

        # Step 2: Map forward_adjustment_factor from collateral_param
        df = self._map_forward_adjustment_factor(df)

        # Step 3: Calculate scenario-based collateral amounts
        df = self._calculate_scenario_collateral_amounts(df)

        return df

    def _calculate_quarter(self, df):
        """
        Calculate quarter for each deal based on snapshot_dt order
        Optimized for single deal processing

        Args:
            df: DataFrame with deal_id and snapshot_dt (single deal)

        Returns:
            DataFrame: DataFrame with quarter column added
        """
        # Since we're processing single deal, simplify the logic
        df_sorted = df.sort_values('snapshot_dt')

        # Create quarter mapping for unique snapshot_dt values
        unique_snapshots = df_sorted['snapshot_dt'].unique()
        quarter_mapping = {snapshot: i for i,
                           snapshot in enumerate(unique_snapshots)}

        # Map quarter values
        df_sorted['quarter'] = df_sorted['snapshot_dt'].map(quarter_mapping)

        return df_sorted

    def _map_forward_adjustment_factor(self, df):
        """
        Map forward_adjustment_factor from collateral_param based on collateral_agreement_type

        Args:
            df: DataFrame with collateral_agreement_type

        Returns:
            DataFrame: DataFrame with forward_adjustment_factor column
        """
        if self.collateral_param.empty:
            # If no collateral_param, set all to "N/A"
            df['forward_adjustment_factor'] = "N/A"
            return df

        # Map collateral_agreement_type to forward_adjustment_factor
        # Using collateral_agreement_type column to map to forward_adjustment_factor
        mapping = self.collateral_param.set_index('collateral_agreement_type')[
            'forward_adjustment_factor'].to_dict()

        # Map the forward_adjustment_factor
        df['forward_adjustment_factor'] = df['collateral_agreement_type'].map(
            mapping)

        # Fill missing values with "N/A"
        df['forward_adjustment_factor'] = df['forward_adjustment_factor'].fillna(
            "N/A")

        return df

    def _calculate_scenario_collateral_amounts(self, df):
        """
        Calculate scenario-based collateral amounts using forward_looking_collateral_param
        Optimized version using pre-created pivot table and vectorized operations

        Args:
            df: DataFrame with forward_adjustment_factor, quarter, and allocated_collateral_amt

        Returns:
            DataFrame: DataFrame with scenario-based collateral amounts
        """
        if self.forward_looking_pivot is None or self.forward_looking_pivot.empty:
            # If no forward looking data, initialize with original amounts
            for scenario in self.scenarios:
                df[f'alloc_coll_amt_{scenario}'] = df['allocated_collateral_amt']
            return df

        # Initialize scenario columns with original amount
        for scenario in self.scenarios:
            df[f'alloc_coll_amt_{scenario}'] = df['allocated_collateral_amt']

        # More efficient approach: directly use pivot table with MultiIndex merge
        # Reset index to convert MultiIndex to columns for easier merging
        pivot_reset = self.forward_looking_pivot.reset_index()

        # Filter out N/A factors
        pivot_reset = pivot_reset[pivot_reset['forward_adjustment_factor'] != "N/A"]

        if not pivot_reset.empty:
            # Merge directly using forward_adjustment_factor and quarter
            df = df.merge(
                pivot_reset,
                on=['forward_adjustment_factor', 'quarter'],
                how='left',
                suffixes=('', '_forecast')
            )

            # Apply forecast values vectorized for each scenario
            for scenario in self.scenarios:
                if scenario in df.columns:
                    # Only apply where forecast value exists
                    mask = df[scenario].notna()
                    df.loc[mask, f'alloc_coll_amt_{scenario}'] = (
                        df.loc[mask, 'allocated_collateral_amt'] *
                        (1 + df.loc[mask, scenario] / 100)
                    )
                    # Clean up forecast column (scenario column from merge)
                    df = df.drop(columns=[scenario])

        return df

    def calculate_collateral_recover_rank(self, ead_df):
        """
        Calculate collateral agreement type recover rank for each deal using simplified logic

        Args:
            ead_df: DataFrame with deal_id and collateral_agreement_type

        Returns:
            DataFrame: DataFrame with collateral_recover_rank column
        """
        if ead_df.empty:
            return ead_df

        df = ead_df.copy()

        # Use simplified logic: process each deal's collateral types independently
        # Since this is called from _process_single_deal, we know it's for one deal
        df = self._convert_to_natural_rank(df)

        return df

    def _convert_to_natural_rank(self, df):
        """
        Create final rank for collateral types for a single deal

        Args:
            df: DataFrame with collateral_agreement_type for a single deal

        Returns:
            DataFrame: DataFrame with collateral_recover_rank column
        """
        if not self.rank_mapping:
            # If no collateral_param, set all to 1
            df['collateral_recover_rank'] = 1
            return df

        # 1. Extract unique collateral types for this deal
        unique_coll_types = df['collateral_agreement_type'].unique()

        # 2. Create collateral type rank table
        coll_rank_df = pd.DataFrame({
            'collateral_agreement_type': unique_coll_types
        })

        # 3. Add original rank from param
        coll_rank_df['collateral_secured_rank'] = coll_rank_df['collateral_agreement_type'].map(
            self.rank_mapping)
        coll_rank_df['collateral_secured_rank'] = coll_rank_df['collateral_secured_rank'].fillna(
            1)

        # 4. Sort by rank and collateral_agreement_type (for tie-breaking)
        coll_rank_df = coll_rank_df.sort_values(
            ['collateral_secured_rank', 'collateral_agreement_type'])

        # 5. Assign final rank (starting from 1)
        coll_rank_df['final_rank'] = range(1, len(coll_rank_df) + 1)

        # 6. Create mapping for this deal
        deal_rank_mapping = coll_rank_df.set_index('collateral_agreement_type')[
            'final_rank'].to_dict()

        # 7. Map back to deal data
        df['collateral_recover_rank'] = df['collateral_agreement_type'].map(
            deal_rank_mapping)

        return df

    def calculate_secured_lgd(self, ead_df):
        """
        Calculate secured LGD using the formula:
        secured_lgd = 1 - (1 + eir)^(-recovery_time)

        Args:
            ead_df: DataFrame with deal_id and collateral_agreement_type

        Returns:
            DataFrame: DataFrame with secured_lgd column
        """
        if ead_df.empty:
            return ead_df

        df = ead_df.copy()

        # Step 1: Map EIR from eir_mapping using deal_id
        df['eir'] = df['deal_id'].map(self.eir_mapping)
        # TODO: chk eir=0?
        df['eir'] = df['eir'].fillna(0.0)

        # Step 2: Map recovery_time from collateral_param using collateral_agreement_type
        df['recovery_time'] = df['collateral_agreement_type'].map(
            self.recovery_time_mapping)
        df['recovery_time'] = df['recovery_time'].fillna("N/A")

        # Step 3: Calculate secured LGD
        df = self._apply_secured_lgd_formula(df)

        return df

    def _apply_secured_lgd_formula(self, df):
        """
        Apply secured LGD formula using vectorized operations: secured_lgd = 1 - (1 + eir)^(-recovery_time)

        Args:
            df: DataFrame with eir and recovery_time columns

        Returns:
            DataFrame: DataFrame with secured_lgd column
        """
        # Convert recovery_time to numeric, "N/A" and invalid values will become NaN
        recovery_time_numeric = pd.to_numeric(
            df['recovery_time'], errors='coerce')

        # Apply formula using vectorized operations: secured_lgd = 1 - (1 + eir)^(-recovery_time)
        # For rows where recovery_time is "N/A" or invalid, recovery_time_numeric will be NaN,
        # and the calculation result will also be NaN
        df['secured_lgd'] = 1 - (1 + df['eir']) ** (-recovery_time_numeric)

        # Fill NaN values (from "N/A" or invalid recovery_time) with 0.0
        df['secured_lgd'] = df['secured_lgd'].fillna(0.0)

        return df

    def calculate_corresponding_exposure_and_secured_portion(self, ead_df):
        """
        Calculate corresponding total exposure and secured portion

        Args:
            ead_df: DataFrame with ead, collateral_recover_rank, and scenario collateral amounts

        Returns:
            DataFrame: DataFrame with ead_, corr_ttl_ead_scenario, and secured_portion_scenario columns
        """
        if ead_df.empty:
            return ead_df

        df = ead_df.copy()

        # Step 1: Calculate ead_ based on option
        df = self._calculate_ead_underscore(df)

        # Step 2: Calculate corresponding total exposure for each scenario
        df = self._calculate_corresponding_total_exposure(df)

        # Step 3: Calculate secured portion for each scenario
        df = self._calculate_secured_portion(df)

        return df

    def _calculate_ead_underscore(self, df):
        """
        Calculate ead_ based on option from self.use_constant_ead

        Args:
            df: DataFrame with deal_id, snapshot_dt, and ead

        Returns:
            DataFrame: DataFrame with ead_ column
        """
        if self.use_constant_ead:
            # Option 2: ead_ is constant (first snapshot_dt ead for each deal)
            df = self._apply_option_2_ead(df)
        else:
            # Option 1: ead_ = ead (current ead)
            df['ead_'] = df['ead']

        return df

    def _apply_option_2_ead(self, df):
        """
        Apply option 2: ead_ is constant (first snapshot_dt ead for each collateral type)
        Optimized for single deal processing

        Args:
            df: DataFrame with deal_id, snapshot_dt, and ead (single deal)

        Returns:
            DataFrame: DataFrame with ead_ column
        """
        # Sort by snapshot_dt to ensure proper ordering
        df_sorted = df.sort_values('snapshot_dt')

        # For each collateral type, get the first snapshot_dt ead
        first_ead = df_sorted.groupby('collateral_agreement_type')[
            'ead'].first().reset_index()
        first_ead = first_ead.rename(columns={'ead': 'ead_first'})

        # Merge back to get the first ead for each row
        df_sorted = df_sorted.merge(
            first_ead,
            on='collateral_agreement_type',
            how='left'
        )

        # Set ead_ to the first ead for each collateral type
        df_sorted['ead_'] = df_sorted['ead_first']

        # Drop temporary column
        df_sorted = df_sorted.drop(columns=['ead_first'])

        return df_sorted

    def _calculate_corresponding_total_exposure(self, df):
        """
        Calculate corresponding total exposure for each scenario using vectorized operations
        Optimized version: batch process all scenarios, avoid repeated sorting and filtering

        Args:
            df: DataFrame with ead_, collateral_recover_rank, and scenario collateral amounts

        Returns:
            DataFrame: DataFrame with corr_ttl_ead_scenario columns
        """
        if df.empty:
            return df

        # Get scenario columns (alloc_coll_amt_*)
        scenario_cols = [
            col for col in df.columns if col.startswith('alloc_coll_amt_')]

        if not scenario_cols:
            return df

        # Step 1: Sort once for all scenarios (shared operation)
        df = df.sort_values(['snapshot_dt', 'collateral_recover_rank'])

        # Step 2: Calculate max_rank once for all scenarios (shared operation)
        df['_max_rank'] = df.groupby('snapshot_dt')[
            'collateral_recover_rank'].transform('max')

        # Step 3: For each scenario, batch calculate using vectorized operations
        for scenario_col in scenario_cols:
            scenario_name = scenario_col.replace('alloc_coll_amt_', '')
            corr_ttl_ead_col = f'corr_ttl_ead_{scenario_name}'

            # Calculate cumulative sum of lower ranks (vectorized)
            # shift(1) excludes current row, only sums previous rows
            cumsum_col = f'_cumsum_{scenario_name}'
            df[cumsum_col] = df.groupby('snapshot_dt')[scenario_col].transform(
                lambda x: x.shift(1).fillna(0).cumsum()
            )

            # Calculate remaining EAD (vectorized)
            remaining_col = f'_remaining_{scenario_name}'
            df[remaining_col] = np.maximum(0, df['ead_'] - df[cumsum_col])

            # Apply three rules using vectorized operations
            # Rule 1: rank == 1
            mask_rank1 = df['collateral_recover_rank'] == 1
            # Rule 2: 1 < rank < max_rank
            mask_middle = (df['collateral_recover_rank'] > 1) & (
                df['collateral_recover_rank'] < df['_max_rank'])
            # Rule 3: rank == max_rank
            mask_max_rank = df['collateral_recover_rank'] == df['_max_rank']

            # Initialize result column
            df[corr_ttl_ead_col] = 0.0

            # Rule 1: min(ead_, alloc_coll_amt)
            df.loc[mask_rank1, corr_ttl_ead_col] = np.minimum(
                df.loc[mask_rank1, 'ead_'],
                df.loc[mask_rank1, scenario_col]
            )

            # Rule 2: min(remaining_ead, alloc_coll_amt)
            df.loc[mask_middle, corr_ttl_ead_col] = np.minimum(
                df.loc[mask_middle, remaining_col],
                df.loc[mask_middle, scenario_col]
            )

            # Rule 3: max(0, ead_ - sum_lower_ranks) = remaining_ead
            df.loc[mask_max_rank,
                   corr_ttl_ead_col] = df.loc[mask_max_rank, remaining_col]

            # Clean up temporary columns
            df = df.drop(columns=[cumsum_col, remaining_col])

        # Clean up max_rank column
        df = df.drop(columns=['_max_rank'])

        return df

    def _calculate_secured_portion(self, df):
        """
        Calculate secured portion for each scenario using vectorized operations
        Optimized version: batch process all scenarios using numpy operations

        Args:
            df: DataFrame with corr_ttl_ead_scenario and alloc_coll_amt_scenario columns

        Returns:
            DataFrame: DataFrame with secured_portion_scenario columns
        """
        if df.empty:
            return df

        # Get corresponding total exposure columns (corr_ttl_ead_*)
        corr_ttl_ead_cols = [
            col for col in df.columns if col.startswith('corr_ttl_ead_')]

        if not corr_ttl_ead_cols:
            return df

        # For each scenario, calculate secured portion using vectorized operations
        for corr_ttl_ead_col in corr_ttl_ead_cols:
            scenario_name = corr_ttl_ead_col.replace('corr_ttl_ead_', '')
            alloc_coll_amt_col = f'alloc_coll_amt_{scenario_name}'
            secured_portion_col = f'secured_portion_{scenario_name}'

            # Vectorized calculation: IF(corr_ttl_ead=0, 1, alloc_coll_amt/corr_ttl_ead)
            # Use np.where for conditional logic
            df[secured_portion_col] = np.where(
                df[corr_ttl_ead_col] == 0,
                1.0,
                df[alloc_coll_amt_col] / df[corr_ttl_ead_col]
            )

            # Limit maximum value to 1.0
            df[secured_portion_col] = np.minimum(df[secured_portion_col], 1.0)

        return df

    def calculate_final_lgd(self, ead_df):
        """
        Calculate final LGD for each scenario using the formula:
        final_lgd_scenario = secured_lgd * secured_portion_scenario + unsecured_lgd * (1 - secured_portion_scenario)

        Args:
            ead_df: DataFrame with secured_lgd, unsecured_lgd, and secured_portion_scenario columns

        Returns:
            DataFrame: DataFrame with final_lgd_scenario columns
        """
        if ead_df.empty:
            return ead_df

        df = ead_df.copy()

        # Get secured_portion columns (secured_portion_*)
        secured_portion_cols = [
            col for col in df.columns if col.startswith('secured_portion_')]

        # For each scenario, calculate final LGD
        for secured_portion_col in secured_portion_cols:
            scenario_name = secured_portion_col.replace('secured_portion_', '')
            final_lgd_col = f'final_lgd_{scenario_name}'
            unsecured_lgd_col = f'unsecured_lgd_{scenario_name}'

            # Check if unsecured_lgd_scenario column exists
            if unsecured_lgd_col in df.columns:
                # Calculate final_lgd = secured_lgd * secured_portion + unsecured_lgd_scenario * (1 - secured_portion)
                df[final_lgd_col] = (
                    df['secured_lgd'] * df[secured_portion_col] +
                    df[unsecured_lgd_col] * (1 - df[secured_portion_col])
                )
            else:
                # Fallback to single unsecured_lgd if scenario-specific column doesn't exist
                df[final_lgd_col] = (
                    df['secured_lgd'] * df[secured_portion_col] +
                    df['unsecured_lgd'] * (1 - df[secured_portion_col])
                )

        return df


def _process_batch_deals_worker(batch_data):
    """
    Worker function for parallel processing of batches of deals
    This function processes multiple deals in a single worker process, sharing one LGDCalculation instance
    This significantly reduces process communication overhead compared to single deal processing

    Args:
        batch_data: Dictionary containing:
            - deal_ids: List of deal IDs to process
            - ead_df_grouped: Dictionary of {deal_id: ead_df} for deals in this batch
            - coll_alloc_grouped: Dictionary of {deal_id: coll_alloc_df} for deals in this batch
            - unsecured_lgd_grouped: Dictionary of {deal_id: unsecured_lgd_df} for deals in this batch
            - context: Context data
            - param: Parameter data
            - on_off_df: On/off balance sheet DataFrame

    Returns:
        List of DataFrames: Processed results for all deals in the batch
    """
    # Extract batch data
    deal_ids = batch_data['deal_ids']
    ead_df_grouped = batch_data['ead_df_grouped']
    coll_alloc_grouped = batch_data['coll_alloc_grouped']
    unsecured_lgd_grouped = batch_data['unsecured_lgd_grouped']
    context = batch_data['context']
    param = batch_data['param']
    on_off_df = batch_data['on_off_df']

    # Create a single LGDCalculation instance for the entire batch
    # This avoids recreating the instance for each deal, saving initialization time
    lgd_calc = LGDCalculation(context, param, on_off_df)

    # Process all deals in the batch using the shared instance
    batch_results = []
    for deal_id in deal_ids:
        # Get deal-specific data from dictionaries
        deal_ead_df = ead_df_grouped.get(deal_id, pd.DataFrame())
        deal_coll_alloc_df = coll_alloc_grouped.get(deal_id, pd.DataFrame())
        deal_unsecured_lgd = unsecured_lgd_grouped.get(deal_id, pd.DataFrame())

        # Skip if no EAD data for this deal
        if deal_ead_df.empty:
            continue

        # Process the deal using the shared LGDCalculation instance
        try:
            result = lgd_calc._process_single_deal(
                deal_id, deal_ead_df, deal_coll_alloc_df, deal_unsecured_lgd)
            batch_results.append(result)
        except Exception as exc:
            # Log error but continue processing other deals in the batch
            print(f'Error processing deal {deal_id} in batch: {exc}')
            continue

    return batch_results
