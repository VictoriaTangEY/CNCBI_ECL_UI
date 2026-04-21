# Lock packages
import pandas as pd
import numpy as np
import time

from utils.loggers import createLogHandler
from ecl_calc.modules.io_handler.data_preprocessor import DataPreprocessor
from ecl_calc.modules.ecl_adjustment.mid_run_adjustment import mid_run_adj
from ecl_calc.modules.scenario_engine.pd_assignment import PDAssignmentFramework
from ecl_calc.modules.ecl_calculator.collateral_alloc import CollateralAllocator
from ecl_calc.modules.ecl_calculator.ead_layer_1 import CashflowLayerOne as ead_layer1
from ecl_calc.modules.ecl_calculator.ead_layer_2 import RepaymentFactoryCncbi as ead_layer2
from ecl_calc.modules.ecl_calculator.ead_layer_3 import RepaymentFactoryCncbi as ead_layer3
from ecl_calc.modules.ecl_calculator.ead_off_bal import OffBalEAD
from ecl_calc.modules.ecl_calculator.lgd_calculation import LGDCalculation
from ecl_calc.modules.ecl_calculator.discounting_factor import DiscountFactorCalculation
from ecl_calc.modules.ecl_calculator.ecl_calculation import ECLCalculation, run_pwa_ecl

# Ignore warnings
import warnings
# Show all columns and rows of a dataframe
pd.set_option('display.max_columns', None)


def run_ecl_engine(context, param):
    """Main ECL calculation engine"""
    # Initialize logger
    logger = createLogHandler(
        'ecl_calculation', context.outLogPath/'Log_file_ecl_calculation.log')
    logger.info('='*50)
    logger.info('Starting ECL Calculation Process')
    logger.info('='*50)

    # 1.1 Load Data
    print("\n1. Loading data...")
    start_time = time.time()
    logger.info('1.1. Loading data')
    try:
        # Load data
        dp = DataPreprocessor(context)
        on_off_df, stage_3_df, coll_df, sched_df = dp.run(
            context=context, param=param)

        # Export data
        on_off_df.to_csv(context.outInterimPath /
                         "chk_1_1_on_off_df.csv", index=False)
        stage_3_df.to_csv(context.outInterimPath /
                          "chk_1_1_stage_3_df.csv", index=False)
        coll_df.to_csv(context.outInterimPath /
                       "chk_1_1_coll_df.csv", index=False)
        sched_df.to_csv(context.outInterimPath /
                        "chk_1_1_sched_df.csv", index=False)

        logger.info('\tData loaded successfully')
    except Exception as e:
        logger.exception("\tFailed to load data")
        raise
    print(f"Completed 1.1 in {time.time() - start_time:.2f} seconds")

    # 1.2. Adjustment on_off_df - Only proceed if ECL_ADJ_MODE is ON
    if context.ecl_adj_mode == "ON":
        print("\n1.2. Adjustment...")
        start_time = time.time()
        logger.info('1.2. Adjustment')
        try:
            on_off_df = mid_run_adj(context, param, on_off_df,
                                    'exposure_table_preprocessed')
        except Exception as e:
            logger.exception("\tAdjustment failed")
            raise
        print(f"Completed 1.2 in {time.time() - start_time:.2f} seconds")

    # 2.1. On_Balance EAD Generation
    print("\n2.1. On_Balance EAD Generation...")
    start_time = time.time()
    logger.info('2.1. On_Balance EAD Generation')
    try:
        # separate on_off_df into on_df and off_df
        on_df = on_off_df[on_off_df['on_off_ind_final'] == 'ON']
        off_df = on_off_df[on_off_df['on_off_ind_final'] == 'OFF']

        # Initialize EAD processing
        all_ids = set(on_df['deal_id'].unique())

        # sched_ids should be the intersection of all_ids and sched_df['acct_id']
        # Only include deals that are both in on_df and have schedule data
        sched_ids = (set(sched_df['acct_id'].unique())
                     & all_ids) if not sched_df.empty else set()

        # Process each layer and collect ead_layer mappings
        layer1_cfl, layer1_ead, layer1_ead_layer_dict, layer1_input_deals = process_layer1(
            on_df, sched_df, sched_ids, context, logger)
        layer2_cfl, layer2_ead, layer2_ead_layer_dict, layer2_input_deals = process_layer2(
            on_df, all_ids, sched_ids, context, logger)
        layer3_cfl, layer3_ead, layer3_ead_layer_dict, repayment_type_dict, layer3_input_deals = process_layer3(
            on_df, all_ids, sched_ids, layer2_ead, context, param, logger)

        # Combine ead_layer mappings from all layers
        ead_layer_dict = {**layer1_ead_layer_dict, **
                          layer2_ead_layer_dict, **layer3_ead_layer_dict}

        # Merge ead_layer back to on_off_df using map (more efficient than merge)
        if ead_layer_dict:
            # Drop existing ead_layer column if it exists to avoid duplicate columns
            if 'ead_layer' in on_off_df.columns:
                on_off_df = on_off_df.drop(columns=['ead_layer'])
            # Use map instead of merge for better performance
            on_off_df['ead_layer'] = on_off_df['deal_id'].map(ead_layer_dict)

        # Merge repayment_type back to on_off_df using map (more efficient than merge)
        if repayment_type_dict:
            # Map repayment_type values, only update where dict has values
            repayment_type_mapped = on_off_df['deal_id'].map(
                repayment_type_dict)
            # Only update non-null values from the mapping
            mask = repayment_type_mapped.notna()
            on_off_df.loc[mask, 'repayment_type'] = repayment_type_mapped[mask]

        # Combine and export results
        cfl_df = pd.concat(
            [layer1_cfl, layer2_cfl, layer3_cfl], ignore_index=True)
        ead_df_on = pd.concat(
            [layer1_ead, layer2_ead, layer3_ead], ignore_index=True)

        # Log summary
        log_ead_summary(context, cfl_df, all_ids, layer1_input_deals,
                        layer2_input_deals, layer3_input_deals, logger)

        # Check if EAD data is empty before proceeding
        if ead_df_on.empty:
            logger.error('No EAD data generated. Skipping further processing.')
            print('No EAD data generated. Skipping further processing.')
            return None, None, None

        ead_df_on.to_csv(context.outInterimPath /
                         "chk_2_1_ead_on_balance.csv", index=False)
        cfl_df.to_csv(context.outInterimPath /
                      "chk_2_1_cfl_on_balance.csv", index=False)

        logger.info('\tEAD generation completed')
    except Exception as e:
        logger.exception("\tEAD generation failed")
        raise
    print(f"Completed 2.1 in {time.time() - start_time:.2f} seconds")

    # 2.2. Off_Balance EAD Generation
    print("\n2.2. Off_Balance EAD Generation...")
    start_time = time.time()
    logger.info('2.2. Off_Balance EAD Generation')
    try:
        off_ead_generator = OffBalEAD(context, param)
        ead_df_off = off_ead_generator.run(off_df)
        ead_df_off.to_csv(context.outInterimPath /
                          "chk_2_2_ead_off_balance.csv", index=False)
        logger.info('\tOff_Balance EAD generation completed')
    except Exception as e:
        logger.exception("\tOff_Balance EAD generation failed")
        raise
    print(f"Completed 2.2 in {time.time() - start_time:.2f} seconds")

    # 2.3. Generate final EAD: concat on/off and cut by stage
    print("\n2.3. Generating final EAD...")
    start_time = time.time()
    logger.info('2.3. Generate final EAD')
    try:
        ead_df = pd.concat([ead_df_on, ead_df_off], ignore_index=True)

        # start - tmp dup chk - remove later or add to dp
        # Check and remove duplicate deal_id from on_off_df and ead_df
        logger.info('\tChecking for duplicate deal_ids...')
        duplicate_deal_ids = on_off_df[on_off_df.duplicated(
            subset=['deal_id'], keep=False)]

        if not duplicate_deal_ids.empty:
            # Get unique deal_ids that have duplicates
            unique_duplicate_deal_ids = duplicate_deal_ids['deal_id'].unique()

            # Save all duplicate records from on_off_df for checking
            duplicate_deal_ids.to_csv(
                context.outInterimPath / "chk_2_3_duplicate_deal_id_records.csv",
                index=False
            )

            # Create summary statistics
            duplicate_summary = []
            for deal_id in unique_duplicate_deal_ids:
                deal_records = duplicate_deal_ids[duplicate_deal_ids['deal_id'] == deal_id]
                final_stages = deal_records['final_stage'].unique()
                duplicate_summary.append({
                    'deal_id': deal_id,
                    'record_count': len(deal_records),
                    'unique_final_stages': str(final_stages.tolist()),
                    'final_stage_min': deal_records['final_stage'].min(),
                    'final_stage_max': deal_records['final_stage'].max(),
                    'source_merged_table': str(deal_records['source_merged_table'].unique().tolist()) if 'source_merged_table' in deal_records.columns else 'N/A'
                })

            duplicate_summary_df = pd.DataFrame(duplicate_summary)
            duplicate_summary_df.to_csv(
                context.outInterimPath / "chk_2_3_duplicate_deal_id_summary.csv",
                index=False
            )

            logger.warning(
                f'\tFound {len(unique_duplicate_deal_ids)} duplicate deal_ids with {len(duplicate_deal_ids)} total records')
            logger.warning(
                f'\tRemoving duplicate deal_ids from on_off_df and ead_df...')

            # Remove duplicate records from on_off_df
            # For records with same deal_id, keep the one with maximum final_stage
            # If final_stage is same, keep the first one
            on_off_df_sorted = on_off_df.sort_values(
                'final_stage', ascending=False)
            on_off_df_cleaned = on_off_df_sorted.drop_duplicates(
                subset=['deal_id'], keep='first'
            )

            # Get the removed records from on_off_df (records that are in original but not in cleaned)
            removed_on_off_records = on_off_df_sorted[~on_off_df_sorted.index.isin(
                on_off_df_cleaned.index)]
            if not removed_on_off_records.empty:
                removed_on_off_records.to_csv(
                    context.outInterimPath / "chk_2_3_removed_on_off_duplicate_records.csv",
                    index=False
                )

            # Remove all records with duplicate deal_ids from ead_df
            ead_df_removed = ead_df[ead_df['deal_id'].isin(
                unique_duplicate_deal_ids)]
            ead_df_cleaned = ead_df[~ead_df['deal_id'].isin(
                unique_duplicate_deal_ids)]

            # Save removed ead_df records
            if not ead_df_removed.empty:
                ead_df_removed.to_csv(
                    context.outInterimPath / "chk_2_3_removed_ead_duplicate_deal_records.csv",
                    index=False
                )
                logger.warning(
                    f'\tRemoved {len(ead_df_removed)} EAD records for duplicate deal_ids')

            # Update on_off_df and ead_df to use cleaned versions
            on_off_df = on_off_df_cleaned
            ead_df = ead_df_cleaned

            logger.warning(
                f'\tRemoved {len(removed_on_off_records)} duplicate records from on_off_df')
            logger.warning(
                f'\tRemoved records saved to interim folder for checking')

        # Check for NaN deal_ids
        nan_deal_id_count = on_off_df['deal_id'].isna().sum()
        if nan_deal_id_count > 0:
            nan_deal_id_records = on_off_df[on_off_df['deal_id'].isna()]
            nan_deal_id_records.to_csv(
                context.outInterimPath / "chk_2_3_nan_deal_id_records.csv",
                index=False
            )
            logger.warning(
                f'\tFound {nan_deal_id_count} records with NaN deal_id')
            logger.warning(
                f'\tNaN deal_id records saved to: chk_2_3_nan_deal_id_records.csv')

            # Remove NaN deal_id records from on_off_df and ead_df
            on_off_df = on_off_df[on_off_df['deal_id'].notna()]
            ead_df = ead_df[ead_df['deal_id'].notna()]
            logger.warning(
                f'\tRemoved NaN deal_id records from on_off_df and ead_df')
        # end - tmp dup chk - remove later or add to dp

        # TODO: cut the ead_df by stage, using the stage2 floor param
        # when final_stage is 1, keep only 12 months of ead, else unchanged
        final_stage_map = on_off_df.set_index('deal_id')['final_stage']
        ead_df['final_stage'] = ead_df['deal_id'].map(final_stage_map)

        # Filter data: if final_stage == 1, keep only first 4 (4 quarters) rows for each deal
        stage_1_mask = ead_df['final_stage'] == 1
        stage_other_mask = ead_df['final_stage'] != 1

        # For stage 1 deals, keep only first 4 rows
        stage_1_data = ead_df[stage_1_mask].groupby('deal_id').head(4)

        # Keep all data for other stages
        stage_other_data = ead_df[stage_other_mask]

        # Combine all data
        ead_df = pd.concat(
            [stage_1_data, stage_other_data], ignore_index=True)
        ead_df = ead_df.drop(columns=['final_stage'])

        # Export final EAD
        ead_df.to_csv(context.outInterimPath /
                      "chk_2_3_ead_final.csv", index=False)
        logger.info('\tFinal EAD generation completed')
    except Exception as e:
        logger.exception("\tFinal EAD generation failed")
        raise
    print(f"Completed 2.3 in {time.time() - start_time:.2f} seconds")

    # 3. Collateral Allocation
    print("\n3. Allocating Collateral...")
    start_time = time.time()
    logger.info('3. Allocating Collateral')
    try:
        # Check if collateral data exists
        if coll_df.empty:
            logger.warning(
                '\tNo collateral data found - skipping collateral allocation')
            print('\tNo collateral data found - skipping collateral allocation')
        else:
            logger.info(
                f"\tProcessing {len(coll_df['collateral_agreement_id'].unique())} collateral records")
            print(
                f"\tProcessing {len(coll_df['collateral_agreement_id'].unique())} collateral records")

            # Check if collateral parameters exist
            if 'collateral_param' not in param or param['collateral_param'].empty:
                logger.warning(
                    '\tNo collateral parameters found - using default values')
                print('\tNo collateral parameters found - using default values')

        # Initialize collateral allocator
        collateral_allocator = CollateralAllocator(
            context=context, param=param)

        # Run collateral allocation process (handles empty collateral data internally)
        on_off_df, coll_df = collateral_allocator.run(on_off_df, coll_df)

        if not coll_df.empty:
            # coll_df.to_csv(context.outInterimPath /
            #                "coll_df_processed.csv", index=False)
            logger.info(
                f"\tCollateral allocation completed with {len(coll_df['collateral_agreement_id'].unique())} collateral records")
            print(
                f"\tCollateral allocation completed with {len(coll_df['collateral_agreement_id'].unique())} collateral records")

            # export updated on_off_df and coll_df to chk
            on_off_df.to_csv(context.outInterimPath /
                             "chk_3_on_off_with_allocated_collateral.csv", index=False)
            coll_df.to_csv(context.outInterimPath /
                           "chk_3_coll_allocated.csv", index=False)

        logger.info('\tCollateral allocation completed')
        print('\tCollateral allocation completed')

    except Exception as e:
        logger.exception("\tCollateral allocation failed")
        print(f"\tCollateral allocation failed: {str(e)}")
        raise

    print(f"Completed 3 in {time.time() - start_time:.2f} seconds")

    # Note: coll_df now contains allocated_collateral_amount for LGD assignment
    # It contains: facility_nr, collateral_agreement_id, collateral_agreement_type,
    #              collateral_amount_hke, collateral_amount_post_haircut_hke, allocated_collateral_amount

    # 4. PD assignment
    print("\n4. PD assignment...")
    start_time = time.time()
    logger.info('4. PD assignment')
    try:
        PDAssignmentProcesser = PDAssignmentFramework(
            param=param, cf_table=ead_df, loan_table=on_off_df)
        ead_df_1 = PDAssignmentProcesser.process_all()

        # Store PD assignment results for later export
        ead_df_1.to_csv(context.outInterimPath /
                        "chk_4_ead_assigned_pd.csv", index=False)
        logger.info('\tPD assignment completed')
    except Exception as e:
        logger.exception("\tPD assignment failed")
        raise
    print(f"Completed 4 in {time.time() - start_time:.2f} seconds")

    # 5. LGD calculation
    print("\n5. LGD calculation...")
    start_time = time.time()
    logger.info('5. LGD calculation')

    try:
        # Store original ead_df_1 before LGD calculation to preserve all columns
        ead_df_1_original = ead_df_1.copy()

        # Initialize LGD calculator
        lgd_calculator = LGDCalculation(
            context=context, param=param, on_off_df=on_off_df)

        # Run LGD calculation process (only returns LGD-related columns)
        ead_df_1_lgd = lgd_calculator.run(ead_df_1, coll_df)

        # Merge LGD results back to original ead_df_1
        # Extract only the LGD-related columns from LGD calculation result
        lgd_columns = ['deal_id', 'snapshot_dt'] + \
            [col for col in ead_df_1_lgd.columns if col.startswith(
                'applied_lgd_')]
        ead_df_1_lgd_subset = ead_df_1_lgd[lgd_columns]

        # Merge LGD results back to original ead_df_1
        ead_df_1 = ead_df_1_original.merge(
            ead_df_1_lgd_subset,
            on=['deal_id', 'snapshot_dt'],
            how='left'
        )

        # Export LGD calculation results for debugging/verification
        ead_df_1.to_csv(context.outInterimPath /
                        "chk_5_ead_with_lgd.csv", index=False)

        logger.info('\tLGD calculation completed')
        print('\tLGD calculation completed')

    except Exception as e:
        logger.exception("\tLGD calculation failed")
        print(f"\tLGD calculation failed: {str(e)}")
        raise
    print(f"Completed 5 in {time.time() - start_time:.2f} seconds")

    # 6. Discount factor calculation
    print("\n6. Discount factor calculation...")
    start_time = time.time()
    logger.info('6. Discount factor calculation')

    try:
        DiscountFactorProcesser = DiscountFactorCalculation(
            context=context,
            cf_table=ead_df_1,
            loan_table=on_off_df)
        ead_df_1 = DiscountFactorProcesser.process_all()

        # Store discount factor results for later export
        ead_df_1.to_csv(context.outInterimPath /
                        "chk_6_ead_with_discount_factor.csv", index=False)

        logger.info('\tDiscount factor calculation completed')
    except Exception as e:
        logger.exception("\tDiscount factor calculation failed")
        raise
    print(f"Completed 6 in {time.time() - start_time:.2f} seconds")

    # 7. Apply CCF to EAD
    print("\n7. Applying CCF to EAD...")
    start_time = time.time()
    logger.info('7. Applying CCF to EAD')
    try:
        # Create a mapping of deal_id to ccf from on_off_df
        ccf_mapping = on_off_df[['deal_id', 'ccf']].drop_duplicates()

        # Merge CCF values to EAD dataframe
        ead_df_1 = pd.merge(ead_df_1, ccf_mapping, on='deal_id', how='left')

        # Apply CCF to EAD (multiply EAD by CCF)
        ead_df_1['ead'] = ead_df_1['ead'] * ead_df_1['ccf']

        # Drop the ccf column as it's no longer needed
        ead_df_1 = ead_df_1.drop(columns=['ccf'])

        # Export EAD after CCF application
        ead_df_1.to_csv(context.outInterimPath /
                        "chk_7_ead_with_ccf.csv", index=False)

        logger.info('\tCCF application to EAD completed')
    except Exception as e:
        logger.exception("\tCCF application to EAD failed")
        raise
    print(f"Completed 7 in {time.time() - start_time:.2f} seconds")

    # 8. ECL calculation
    print("\n8. ECL calculation...")
    start_time = time.time()
    logger.info('8. ECL calculation')
    try:
        ECLCalculationProcesser = ECLCalculation(param=param, ead_df=ead_df_1)

        scenario_ecl_detailed, scenario_ecl_by_deal = ECLCalculationProcesser.run_scenario_ecl()

        pwa_ecl_detailed, pwa_ecl_by_deal = run_pwa_ecl(
            param, on_off_df, scenario_ecl_detailed, scenario_ecl_by_deal)

        # Export ECL calculation results
        pwa_ecl_detailed.to_csv(context.outInterimPath /
                                "chk_8_ecl_detailed.csv", index=False)
        pwa_ecl_by_deal.to_csv(context.outInterimPath /
                               "chk_8_ecl_by_deal.csv", index=False)
        logger.info('\tECL calculation completed')
    except Exception as e:
        logger.exception("\tECL calculation failed")
        raise
    print(f"Completed 8 in {time.time() - start_time:.2f} seconds")

    logger.info('='*50)
    logger.info('\tECL Calculation Process Completed Successfully')
    logger.info('='*50)

    # 9. stage 3 ECL calculation
    print("\n9. Stage 3 ECL calculation...")
    start_time = time.time()
    logger.info('9. Stage 3 ECL calculation')
    try:
        ecl_df_stage_3 = stage_3_df.copy()
        # Assign 100% cur_bal as ECL
        ecl_df_stage_3['ecl_final_hke'] = ecl_df_stage_3['cur_bal_hke']
        # Fill missing values in 'bu' column with "UNS"
        ecl_df_stage_3['bu'] = ecl_df_stage_3['bu'].fillna("UNS")

        # Store stage 3 ECL results for later export
        ecl_df_stage_3.to_csv(context.outInterimPath /
                              "chk_9_ecl_stage3.csv", index=False)
        logger.info('\tStage 3 ECL calculation completed')
    except Exception as e:
        logger.exception("\tStage 3 ECL calculation failed")
        raise
    print(f"Completed 9 in {time.time() - start_time:.2f} seconds")

    # 10. ECL result concat
    print("\n10. Concatenating ECL results...")
    start_time = time.time()
    logger.info('10. ECL result concat')
    try:
        pwa_ecl_by_deal = pd.concat(
            [pwa_ecl_by_deal, ecl_df_stage_3], ignore_index=True)

        # Export final ECL results
        pwa_ecl_by_deal.to_csv(context.outInterimPath /
                               "chk_10_ecl_final_by_deal.csv", index=False)

        logger.info('\tECL result concatenation completed')
    except Exception as e:
        logger.exception("\tECL result concatenation failed")
        raise
    print(f"Completed 10 in {time.time() - start_time:.2f} seconds")

    # TODO: to be confirmed if the stage 3 will be concat into pwa_ecl_by_deal
    # Return all DataFrames for later export
    return ead_df, coll_df, pwa_ecl_detailed, pwa_ecl_by_deal


########################################################################################
# helper functions for EAD calculation
########################################################################################


def process_layer1(on_df, sched_df, sched_ids, context, logger):
    """Process Layer 1 deals (Schedule-based deals)"""
    logger.info('\tProcessing Layer 1 (Schedule-based deals)...')
    logger.info(f'\tSchedule IDs found: {len(sched_ids)}')

    # Check if there are any deals with schedule data
    if not sched_ids:
        logger.info('\tNo deals with schedule data found - skipping Layer 1')
        return pd.DataFrame(), pd.DataFrame(), {}, set()

    # Create ead_layer mapping dict for Layer 1 deals
    # layer1_input_deals are the deals that actually enter Layer 1 calculation
    layer1_input_deals = {
        deal_id for deal_id in sched_ids if deal_id in on_df['deal_id'].values}
    ead_layer_dict = {deal_id: 1 for deal_id in layer1_input_deals}

    if context.test_mode == "ON" and context.test_deal_list != []:
        print(f'\tLayer 1 deals: {list(layer1_input_deals)}')

    # Create calculator and process
    layer1_calculator = ead_layer1(
        reporting_date=context.data_yymm,
        data=on_df,
        sched_data=sched_df,
        rounding=10,
        grace_period=0
    )
    layer1_cfl, layer1_ead = layer1_calculator.batch_process()

    # Rename columns for consistency
    if not layer1_cfl.empty and not layer1_ead.empty:
        layer1_cfl.rename(columns={'acct_id': 'deal_id'}, inplace=True)
        layer1_ead.rename(columns={'acct_id': 'deal_id'}, inplace=True)

    return layer1_cfl, layer1_ead, ead_layer_dict, layer1_input_deals


def process_layer2(on_df, all_ids, sched_ids, context, logger):
    """Process Layer 2 deals (AMRT_TYPE_CD = 100 and PMT_AMT > 0)"""
    logger.info('\tProcessing Layer 2 (AMRT_TYPE_CD = 100 and PMT_AMT > 0)...')
    remaining_deals = all_ids - sched_ids
    logger.info(f'\tRemaining deals after Layer 1: {len(remaining_deals)}')

    if not remaining_deals:
        logger.info('\tNo remaining deals for Layer 2')
        return pd.DataFrame(), pd.DataFrame(), {}, set()

    # Filter deals for Layer
    layer2_deals = on_df[
        (on_df['deal_id'].isin(remaining_deals)) &
        (on_df['amrt_type_cd'] == '100') &
        (on_df['pmt_amt_hke'] > 0)
    ].copy()

    if layer2_deals.empty:
        logger.info('\tNo Layer 2 deals found - skipping Layer 2')
        return pd.DataFrame(), pd.DataFrame(), {}, set()

    # Create ead_layer mapping dict for Layer 2 deals
    # layer2_input_deals are the deals that actually enter Layer 2 calculation
    layer2_deal_ids = layer2_deals['deal_id'].unique()
    layer2_input_deals = set(layer2_deal_ids)
    ead_layer_dict = {deal_id: 2 for deal_id in layer2_input_deals}

    if context.test_mode == "ON" and context.test_deal_list != []:
        print(f'\tLayer 2 deals: {list(layer2_input_deals)}')

    # Create calculator and process
    factory_layer2 = ead_layer2(
        data_cols=None,
        rounding=10,
        grace_period=0
    )
    layer2_cfl, layer2_ead = factory_layer2.batch_process(
        loan_table=layer2_deals,
        reporting_date=context.data_yymm
    )

    # Rename columns for consistency if needed
    if not layer2_cfl.empty and 'acct_id' in layer2_cfl.columns:
        layer2_cfl.rename(columns={'acct_id': 'deal_id'}, inplace=True)
    if not layer2_ead.empty and 'acct_id' in layer2_ead.columns:
        layer2_ead.rename(columns={'acct_id': 'deal_id'}, inplace=True)

    return layer2_cfl, layer2_ead, ead_layer_dict, layer2_input_deals


def process_layer3(on_df, all_ids, sched_ids, layer2_ead, context, param, logger):
    """Process Layer 3 deals (Remaining deals)"""
    logger.info('\tProcessing Layer 3 (Remaining deals)...')
    processed_deals = sched_ids.union(
        set(layer2_ead['deal_id'].unique()) if not layer2_ead.empty else set()
    )
    remaining_deals = all_ids - processed_deals
    logger.info(f'\tRemaining deals after Layer 2: {len(remaining_deals)}')

    if not remaining_deals:
        logger.info('\tNo remaining deals for Layer 3')
        return pd.DataFrame(), pd.DataFrame(), {}, {}, set()

    # Filter deals for Layer 3
    layer3_deals = on_df[on_df['deal_id'].isin(remaining_deals)].copy()

    if layer3_deals.empty:
        logger.info('\tNo Layer 3 deals found - skipping Layer 3')
        return pd.DataFrame(), pd.DataFrame(), {}, {}, set()

    # Create ead_layer mapping dict for Layer 3 deals
    # layer3_input_deals are the deals that actually enter Layer 3 calculation
    layer3_deal_ids = layer3_deals['deal_id'].unique()
    layer3_input_deals = set(layer3_deal_ids)
    ead_layer_dict = {deal_id: 3 for deal_id in layer3_input_deals}

    if context.test_mode == "ON" and context.test_deal_list != []:
        print(f'\tLayer 3 deals: {list(layer3_input_deals)}')

    # Create calculator and process
    # Note: Batch parallel processing for Layer 3 (to be tested on Linux)
    # On Windows: Sequential processing is faster (~3.568s vs ~6.497s)
    # On Linux: Batch parallel processing is expected to be faster (~1.3s vs ~3.568s)
    # Batch size is now dynamically determined based on number of deals for optimal performance
    factory_layer3 = ead_layer3(
        repayment_mapping=param['repayment_type_param'],
        rounding=10,
        grace_period=0,
        use_batch_parallel=True,  # Enable batch processing for better performance on Linux
        # Use dynamic batch sizing (will be determined based on number of deals)
        batch_size=None
    )
    layer3_cfl, layer3_ead, updated_on_df = factory_layer3.batch_process(
        loan_table=layer3_deals,
        reporting_date=context.data_yymm
    )

    # Rename columns for consistency if needed
    if not layer3_cfl.empty and 'acct_id' in layer3_cfl.columns:
        layer3_cfl.rename(columns={'acct_id': 'deal_id'}, inplace=True)
    if not layer3_ead.empty and 'acct_id' in layer3_ead.columns:
        layer3_ead.rename(columns={'acct_id': 'deal_id'}, inplace=True)

    # Create repayment_type mapping dict (more efficient using drop_duplicates)
    repayment_type_dict = {}
    if not updated_on_df.empty:
        # Use drop_duplicates to get unique deal_id-repayment_type pairs, then filter non-null values
        repayment_type_df = updated_on_df[[
            'deal_id', 'repayment_type']].drop_duplicates(subset='deal_id')
        repayment_type_df = repayment_type_df[repayment_type_df['repayment_type'].notna(
        )]
        repayment_type_dict = dict(
            zip(repayment_type_df['deal_id'], repayment_type_df['repayment_type']))

    return layer3_cfl, layer3_ead, ead_layer_dict, repayment_type_dict, layer3_input_deals


def log_ead_summary(context, cfl_df, all_ids, layer1_input_deals,
                    layer2_input_deals, layer3_input_deals, logger):
    """Log EAD processing summary

    Args:
        context: Context object
        cfl_df: Combined cashflow DataFrame
        all_ids: Set of all deal_ids in on_df (total deals to process)
        layer1_input_deals: Set of deal_ids that entered Layer 1 calculation
        layer2_input_deals: Set of deal_ids that entered Layer 2 calculation
        layer3_input_deals: Set of deal_ids that entered Layer 3 calculation
        logger: Logger object
    """
    logger.info("\tEAD Generation Summary:")

    # Use the actual input deals for each layer (not from results)
    layer1_deals_set = layer1_input_deals
    layer2_deals_set = layer2_input_deals
    layer3_deals_set = layer3_input_deals

    # Total deals is all_ids from step 2.1
    ttl_deals = len(all_ids)

    # Count deals with successful EAD output
    if cfl_df.empty:
        layer1_output = np.array([])
        layer2_output = np.array([])
        layer3_output = np.array([])
        logger.warning("\tNo cashflow data available for processing summary")
    else:
        # Find the deal ID column - could be 'deal_id' or 'acct_id'
        deal_id_col = 'deal_id' if 'deal_id' in cfl_df.columns else 'acct_id'

        if deal_id_col not in cfl_df.columns:
            layer1_output = np.array([])
            layer2_output = np.array([])
            layer3_output = np.array([])
            logger.warning(
                f"\tNo deal ID column found in cashflow data. Available columns: {list(cfl_df.columns)}")
        else:
            layer1_output = set(cfl_df[cfl_df[deal_id_col].isin(
                layer1_deals_set)][deal_id_col].unique())
            layer2_output = set(cfl_df[cfl_df[deal_id_col].isin(
                layer2_deals_set)][deal_id_col].unique())
            layer3_output = set(cfl_df[cfl_df[deal_id_col].isin(
                layer3_deals_set)][deal_id_col].unique())

    # Calculate unprocessed deals
    layer1_unprocessed = len(layer1_deals_set) - len(layer1_output)
    layer2_unprocessed = len(layer2_deals_set) - len(layer2_output)
    layer3_unprocessed = len(layer3_deals_set) - len(layer3_output)

    # Log summary
    logger.info(
        f"\tLayer 1: {len(layer1_deals_set)} deals in, {len(layer1_output)} processed, {layer1_unprocessed} unprocessed")
    logger.info(
        f"\tLayer 2: {len(layer2_deals_set)} deals in, {len(layer2_output)} processed, {layer2_unprocessed} unprocessed")
    logger.info(
        f"\tLayer 3: {len(layer3_deals_set)} deals in, {len(layer3_output)} processed, {layer3_unprocessed} unprocessed")
    logger.info(f"\tTotal deals in on_df: {ttl_deals}")

    # Calculate deals that didn't enter any layer
    processed_deals = layer1_deals_set | layer2_deals_set | layer3_deals_set
    unprocessed_total = all_ids - processed_deals
    if unprocessed_total:
        logger.warning(
            f"\tDeals not processed by any layer: {len(unprocessed_total)}")
        pd.DataFrame({'deal_id': list(unprocessed_total)}).to_csv(
            context.outInterimPath/"chk_2_1_unprocessed_total.csv", index=False)

    # Log any unprocessed deals for debugging
    if layer1_unprocessed > 0:
        unprocessed_layer1 = layer1_deals_set - layer1_output
        pd.DataFrame({'deal_id': list(unprocessed_layer1)}).to_csv(
            context.outInterimPath/"chk_2_1_unprocessed_layer1.csv", index=False)

    if layer2_unprocessed > 0:
        unprocessed_layer2 = layer2_deals_set - layer2_output
        pd.DataFrame({'deal_id': list(unprocessed_layer2)}).to_csv(
            context.outInterimPath/"chk_2_1_unprocessed_layer2.csv", index=False)

    if layer3_unprocessed > 0:
        unprocessed_layer3 = layer3_deals_set - layer3_output
        pd.DataFrame({'deal_id': list(unprocessed_layer3)}).to_csv(
            context.outInterimPath/"chk_2_1_unprocessed_layer3.csv", index=False)
