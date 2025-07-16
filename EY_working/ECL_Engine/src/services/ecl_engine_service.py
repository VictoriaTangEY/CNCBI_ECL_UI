# Lock packages
import pandas as pd
import numpy as np
import time

from utils.loggers import createLogHandler
from config.env_setting import run_setting
from modules.io_handler.data_preprocessor import DataPreprocessor
from modules.ecl_adjustment.mid_run_adjustment import mid_run_adj
from modules.scenario_engine.pd_assignment import PDAssignmentFramework
from modules.scenario_engine.collateral_allocation import CollateralAllocator
from modules.ecl_calculator.ead_layer_1 import CashflowLayerOne as ead_layer1
from modules.ecl_calculator.ead_layer_2 import RepaymentFactoryCncbi as ead_layer2
from modules.ecl_calculator.ead_layer_3 import RepaymentFactoryCncbi as ead_layer3
from modules.ecl_calculator.ead_off_bal import OffBalEAD
from modules.ecl_calculator.lgd_calculation import SecuredLGDCalculator, FinalLGDCalculator
from modules.ecl_calculator.discounting_factor import DiscountFactorCalculation
from modules.ecl_calculator.ecl_calculation import ECLCalculation


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
        expo_df, expo_df_stage_3, coll_df, sched_df, fac_df, fac_df_stage_3, off_df_deal, off_df_fac = dp.run(
            context=context, param=param)
        logger.info('\tData loaded successfully')
    except Exception as e:
        logger.exception("\tFailed to load data")
        raise
    print(f"Completed 1.1 in {time.time() - start_time:.2f} seconds")

    # 1.2. Adjustment expo_df - Only proceed if ECL_ADJ_MODE is ON
    if context.ecl_adj_mode == "ON":
        print("\n1.2. Adjustment...")
        start_time = time.time()
        logger.info('1.2. Adjustment')
        try:
            expo_df = mid_run_adj(context, param, expo_df,
                                  'exposure_table_preprocessed')
        except Exception as e:
            logger.exception("\tAdjustment failed")
            raise
        print(f"Completed 1.2 in {time.time() - start_time:.2f} seconds")

    # # 2.1. On_Balance EAD Generation
    # print("\n2.1. On_Balance EAD Generation...")
    # start_time = time.time()
    # logger.info('2.1. On_Balance EAD Generation')
    # try:
    #     # Initialize EAD processing
    #     expo_df['ead_layer'] = None
    #     all_ids = set(expo_df['deal_id'].unique())
    #     sched_ids = set(sched_df['acct_id'].unique()
    #                     ) if not sched_df.empty else set()

    #     # Process each layer
    #     layer1_cfl, layer1_ead = process_layer1(
    #         expo_df, sched_df, sched_ids, context, logger)
    #     layer2_cfl, layer2_ead = process_layer2(
    #         expo_df, all_ids, sched_ids, context, logger)
    #     layer3_cfl, layer3_ead, expo_df = process_layer3(
    #         expo_df, all_ids, sched_ids, layer2_ead, context, param, logger)

    #     # Combine and export results
    #     cfl_df = pd.concat(
    #         [layer1_cfl, layer2_cfl, layer3_cfl], ignore_index=True)
    #     ead_df = pd.concat(
    #         [layer1_ead, layer2_ead, layer3_ead], ignore_index=True)

    #     # Save EAD results
    #     cfl_df.to_csv(context.outInterimPath/"cashflow_df.csv", index=False)
    #     ead_df.to_csv(context.outInterimPath/"ead_df.csv", index=False)
    #     expo_df.to_csv(context.outInterimPath /
    #                    "exposure_df_with_ead_layer.csv", index=False)

    #     # Log summary
    #     log_ead_summary(context, cfl_df, expo_df, logger)

    #     # Check if EAD data is empty before proceeding
    #     if ead_df.empty:
    #         logger.error('No EAD data generated. Skipping further processing.')
    #         print('No EAD data generated. Skipping further processing.')
    #         return ead_df

    #     logger.info('\tEAD generation completed')
    # except Exception as e:
    #     logger.exception("\tEAD generation failed")
    #     raise
    # print(f"Completed 2.1 in {time.time() - start_time:.2f} seconds")

    # 2.2. Off_Balance EAD Generation
    print("\n2.2. Off_Balance EAD Generation...")
    start_time = time.time()
    logger.info('2.2. Off_Balance EAD Generation')
    try:
        off_ead_generator = OffBalEAD(context, param)
        off_ead_df = off_ead_generator.run(off_df_deal, off_df_fac)
        off_ead_df.to_csv(context.outInterimPath /
                          "off_ead_df.csv", index=False)
        logger.info('\tOff_Balance EAD generation completed')
    except Exception as e:
        logger.exception("\tOff_Balance EAD generation failed")
        raise
    print(f"Completed 2.2 in {time.time() - start_time:.2f} seconds")

    # # 3. Collateral Allocation
    # print("\n3. Allocating Collateral...")
    # start_time = time.time()
    # logger.info('3. Allocating Collateral')
    # try:
    #     if not coll_df.empty:
    #         rule = param['collateral_param']
    #         coll_allocator = CollateralAllocator(
    #             context=context, coll_df=coll_df, coll_param=rule)
    #         deal_allocation_df = coll_allocator.process_all()

    #         # Save collateral allocation results
    #         deal_allocation_df.to_csv(
    #             context.outInterimPath/"collateral_allocated_df.csv", index=False)

    #         logger.info('\tCollateral allocation completed')
    # except Exception as e:
    #     logger.exception("\tCollateral allocation failed")
    #     raise
    # print(f"Completed 3 in {time.time() - start_time:.2f} seconds")

    # # 4. PD assignment
    # print("\n4. PD assignment...")
    # start_time = time.time()
    # logger.info('4. PD assignment')
    # try:
    #     PDAssignmentProcesser = PDAssignmentFramework(
    #         param=param, cf_table=ead_df, loan_table=expo_df)
    #     ead_df = PDAssignmentProcesser.process_all()

    #     # Save PD assignment results
    #     ead_df.to_csv(context.outInterimPath /
    #                   "ead_assigned_pd_df.csv", index=False)

    #     logger.info('\tPD assignment completed')
    # except Exception as e:
    #     logger.exception("\tPD assignment failed")
    #     raise
    # print(f"Completed 4 in {time.time() - start_time:.2f} seconds")

    # # 5. Discount factor calculation
    # print("\n5. Discount factor calculation...")
    # start_time = time.time()
    # logger.info('5. Discount factor calculation')
    # try:
    #     DiscountFactorProcesser = DiscountFactorCalculation(
    #         context=context,
    #         cf_table=ead_df,
    #         loan_table=expo_df)
    #     ead_df = DiscountFactorProcesser.process_all()

    #     # Save discount factor results
    #     ead_df.to_csv(context.outInterimPath /
    #                   "ead_discounted_df.csv", index=False)

    #     logger.info('\tDiscount factor calculation completed')
    # except Exception as e:
    #     logger.exception("\tDiscount factor calculation failed")
    #     raise
    # print(f"Completed 5 in {time.time() - start_time:.2f} seconds")

    # # TODO：Add dummy LGD values for testing
    # # TODO: update the ecl adjustment after ecl_details is generated
    # ead_df['lgd_base'] = 0.05
    # ead_df['lgd_mild'] = 0.05
    # ead_df['lgd_medium'] = 0.05
    # ead_df['lgd_severe'] = 0.05
    # ead_df['lgd_benign'] = 0.05

    # # 6. ECL calculation
    # print("\n6. ECL calculation...")
    # start_time = time.time()
    # logger.info('6. ECL calculation')
    # try:
    #     ECLCalculationProcesser = ECLCalculation(
    #         context=context, param=param, cf_table=ead_df, loan_table=expo_df)
    #     ecl_df = ECLCalculationProcesser.process_all()

    #     # add a col final_ecl as a copy of pwa_ecl, if no furthur adjustment, then final_ecl = pwa_ecl
    #     ecl_df['final_ecl'] = ecl_df['pwa_ecl']

    #     # Save final ECL results
    #     ecl_df.to_csv(context.outInterimPath /
    #                   "ecl_df.csv", index=False)

    #     logger.info('\tECL calculation completed')
    # except Exception as e:
    #     logger.exception("\tECL calculation failed")
    #     raise
    # print(f"Completed 6 in {time.time() - start_time:.2f} seconds")

    # logger.info('='*50)
    # logger.info('\tECL Calculation Process Completed Successfully')
    # logger.info('='*50)

    # # 7. stage 3 ECL calculation
    # print("\n7. Stage 3 ECL calculation...")
    # start_time = time.time()
    # logger.info('7. Stage 3 ECL calculation')
    # try:
    #     ecl_df_stage_3 = expo_df_stage_3.copy()
    #     # Assign 100% cur_bal as ECL
    #     ecl_df_stage_3['ecl_final'] = ecl_df_stage_3['cur_bal_hke']
    #     # Fill missing values in 'bu' column with "UNS"
    #     ecl_df_stage_3['bu'] = ecl_df_stage_3['bu'].fillna("UNS")

    #     ecl_df_stage_3.to_csv(context.outInterimPath /
    #                           "ecl_df_stage_3.csv", index=False)
    #     logger.info('\tStage 3 ECL calculation completed')
    # except Exception as e:
    #     logger.exception("\tStage 3 ECL calculation failed")
    #     raise
    # print(f"Completed 7 in {time.time() - start_time:.2f} seconds")

    # return


def process_layer1(expo_df, sched_df, sched_ids, context, logger):
    """Process Layer 1 deals (Schedule-based deals)"""
    logger.info('\tProcessing Layer 1 (Schedule-based deals)...')
    logger.info(f'\tSchedule IDs found: {len(sched_ids)}')

    # Check if there are any deals with schedule data
    if not sched_ids:
        logger.info('\tNo deals with schedule data found - skipping Layer 1')
        return pd.DataFrame(), pd.DataFrame()

    # Assign Layer 1 to all deals that have schedule data
    expo_df.loc[expo_df['deal_id'].isin(sched_ids), 'ead_layer'] = 1

    if context.test_mode == "ON" and context.test_deal_list != []:
        print(f'\tLayer 1 deals: {list(sched_ids)}')

    # Create calculator and process
    layer1_calculator = ead_layer1(
        reporting_date=context.data_yymm,
        data=expo_df,
        sched_data=sched_df,
        rounding=10,
        grace_period=0,
        parallel_by_deals=False,
        chunk_size=30
    )
    layer1_cfl, layer1_ead = layer1_calculator.batch_process()

    # Rename columns for consistency
    if not layer1_cfl.empty and not layer1_ead.empty:
        layer1_cfl.rename(columns={'acct_id': 'deal_id'}, inplace=True)
        layer1_ead.rename(columns={'acct_id': 'deal_id'}, inplace=True)

    return layer1_cfl, layer1_ead


def process_layer2(expo_df, all_ids, sched_ids, context, logger):
    """Process Layer 2 deals (AMRT_TYPE_CD = 100 and PMT_AMT > 0)"""
    logger.info('\tProcessing Layer 2 (AMRT_TYPE_CD = 100 and PMT_AMT > 0)...')
    remaining_deals = all_ids - sched_ids
    logger.info(f'\tRemaining deals after Layer 1: {len(remaining_deals)}')

    if not remaining_deals:
        logger.info('\tNo remaining deals for Layer 2')
        return pd.DataFrame(), pd.DataFrame()

    # Filter deals for Layer
    layer2_deals = expo_df[
        (expo_df['deal_id'].isin(remaining_deals)) &
        (expo_df['amrt_type_cd'] == '100') &
        (expo_df['pmt_amt_hke'] > 0)
    ].copy()

    if layer2_deals.empty:
        logger.info('\tNo Layer 2 deals found - skipping Layer 2')
        return pd.DataFrame(), pd.DataFrame()

    # Assign Layer 2 to eligible deals
    layer2_deal_ids = layer2_deals['deal_id'].unique()
    expo_df.loc[expo_df['deal_id'].isin(layer2_deal_ids), 'ead_layer'] = 2

    if context.test_mode == "ON" and context.test_deal_list != []:
        print(f'\tLayer 2 deals: {list(layer2_deal_ids)}')

    # Create calculator and process
    factory_layer2 = ead_layer2(
        data_cols=None,
        rounding=10,
        grace_period=0,
        parallel_by_deals=False,
        chunk_size=300
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

    return layer2_cfl, layer2_ead


def process_layer3(expo_df, all_ids, sched_ids, layer2_ead, context, param, logger):
    """Process Layer 3 deals (Remaining deals)"""
    logger.info('\tProcessing Layer 3 (Remaining deals)...')
    processed_deals = sched_ids.union(
        set(layer2_ead['deal_id'].unique()) if not layer2_ead.empty else set()
    )
    remaining_deals = all_ids - processed_deals
    logger.info(f'\tRemaining deals after Layer 2: {len(remaining_deals)}')

    if not remaining_deals:
        logger.info('\tNo remaining deals for Layer 3')
        return pd.DataFrame(), pd.DataFrame(), expo_df

    # Filter deals for Layer 3
    layer3_deals = expo_df[expo_df['deal_id'].isin(remaining_deals)].copy()

    if layer3_deals.empty:
        logger.info('\tNo Layer 3 deals found - skipping Layer 3')
        return pd.DataFrame(), pd.DataFrame(), expo_df

    # Assign Layer 3 to remaining deals
    layer3_deal_ids = layer3_deals['deal_id'].unique()
    expo_df.loc[expo_df['deal_id'].isin(layer3_deal_ids), 'ead_layer'] = 3

    if context.test_mode == "ON" and context.test_deal_list != []:
        print(f'\tLayer 3 deals: {list(layer3_deal_ids)}')

    # Create calculator and process
    factory_layer3 = ead_layer3(
        repayment_mapping=param['repayment_type_param'],
        rounding=10,
        grace_period=0,
        parallel_by_deals=False,
        chunk_size=300
    )
    layer3_cfl, layer3_ead, updated_expo_df = factory_layer3.batch_process(
        loan_table=layer3_deals,
        reporting_date=context.data_yymm
    )

    # Rename columns for consistency if needed
    if not layer3_cfl.empty and 'acct_id' in layer3_cfl.columns:
        layer3_cfl.rename(columns={'acct_id': 'deal_id'}, inplace=True)
    if not layer3_ead.empty and 'acct_id' in layer3_ead.columns:
        layer3_ead.rename(columns={'acct_id': 'deal_id'}, inplace=True)

    # Update repayment_type information
    if not updated_expo_df.empty:
        for deal_id in updated_expo_df['deal_id'].unique():
            repayment_type = updated_expo_df.loc[
                updated_expo_df['deal_id'] == deal_id, 'repayment_type'].iloc[0]
            if pd.notna(repayment_type):
                expo_df.loc[expo_df['deal_id'] == deal_id,
                            'repayment_type'] = repayment_type

    return layer3_cfl, layer3_ead, expo_df


def log_ead_summary(context, cfl_df, expo_df, logger):
    """Log EAD processing summary"""
    logger.info("\tEAD Generation Summary:")

    # Debug: Log available columns in cfl_df
    if not cfl_df.empty:
        logger.info(f"\tCashflow DataFrame columns: {list(cfl_df.columns)}")
    else:
        logger.info("\tCashflow DataFrame is empty")

    # Count deals by layer from exposure data
    layer1_deals = expo_df[expo_df['ead_layer'] == 1]['deal_id'].unique()
    layer2_deals = expo_df[expo_df['ead_layer'] == 2]['deal_id'].unique()
    layer3_deals = expo_df[expo_df['ead_layer'] == 3]['deal_id'].unique()

    # Count deals with successful EAD output
    # Handle case where cfl_df might be empty or have different column names
    if cfl_df.empty:
        layer1_output = np.array([])
        layer2_output = np.array([])
        layer3_output = np.array([])
        logger.warning("\tNo cashflow data available for processing summary")
    else:
        # Try to find the deal ID column - could be 'deal_id' or 'acct_id'
        deal_id_col = None
        for col in ['deal_id', 'acct_id']:
            if col in cfl_df.columns:
                deal_id_col = col
                break

        if deal_id_col is None:
            layer1_output = np.array([])
            layer2_output = np.array([])
            layer3_output = np.array([])
            logger.warning(
                f"\tNo deal ID column found in cashflow data. Available columns: {list(cfl_df.columns)}")
        else:
            logger.info(
                f"\tUsing '{deal_id_col}' column for deal identification")
            layer1_output = cfl_df[cfl_df[deal_id_col].isin(
                layer1_deals)][deal_id_col].unique()
            layer2_output = cfl_df[cfl_df[deal_id_col].isin(
                layer2_deals)][deal_id_col].unique()
            layer3_output = cfl_df[cfl_df[deal_id_col].isin(
                layer3_deals)][deal_id_col].unique()

    # Calculate unprocessed deals
    layer1_unprocessed = len(layer1_deals) - len(layer1_output)
    layer2_unprocessed = len(layer2_deals) - len(layer2_output)
    layer3_unprocessed = len(layer3_deals) - len(layer3_output)

    # Log summary
    logger.info(
        f"\tLayer 1: {len(layer1_deals)} deals in, {len(layer1_output)} processed, {layer1_unprocessed} unprocessed")
    logger.info(
        f"\tLayer 2: {len(layer2_deals)} deals in, {len(layer2_output)} processed, {layer2_unprocessed} unprocessed")
    logger.info(
        f"\tLayer 3: {len(layer3_deals)} deals in, {len(layer3_output)} processed, {layer3_unprocessed} unprocessed")
    logger.info(f"\tTotal deals: {len(expo_df['deal_id'].unique())}")

    # Log any unprocessed deals for debugging
    if layer1_unprocessed > 0:
        unprocessed_layer1 = set(layer1_deals) - set(layer1_output)
        pd.DataFrame({'deal_id': list(unprocessed_layer1)}).to_csv(
            context.outInterimPath/"unprocessed_layer1.csv", index=False)

    if layer2_unprocessed > 0:
        unprocessed_layer2 = set(layer2_deals) - set(layer2_output)
        pd.DataFrame({'deal_id': list(unprocessed_layer2)}).to_csv(
            context.outInterimPath/"unprocessed_layer2.csv", index=False)

    if layer3_unprocessed > 0:
        unprocessed_layer3 = set(layer3_deals) - set(layer3_output)
        pd.DataFrame({'deal_id': list(unprocessed_layer3)}).to_csv(
            context.outInterimPath/"unprocessed_layer3.csv", index=False)
