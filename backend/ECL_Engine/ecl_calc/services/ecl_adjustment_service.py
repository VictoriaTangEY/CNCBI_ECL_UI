# Lock packages
import pandas as pd
import numpy as np
import time
import logging

from utils.loggers import createLogHandler

# Ignore warnings
import warnings
# Show all columns and rows of a dataframe
pd.set_option('display.max_columns', None)


def pre_run_deal_append(context, param):
    # TODO: may need to add from facility table too
    """ECL adjustment"""
    print('\nECL adjustment - deal append...')

    # Initialize logger
    logger = createLogHandler(
        'ecl_adjustment', context.outLogPath/'Log_file_ecl_adjustment.log')
    logger.info('Starting ECL Adjustment Process...')

    # 1. Load Parameters and Data
    start_time = time.time()
    # align the cols with exposure_table
    expo_df_append = param['pre_run_deal_append_param']
    expo_df_param = param['exposure_table_param']
    # Ensure all columns in expo_df_param['colname'] exist in expo_df_append
    required_cols = expo_df_param['colname'].to_list()
    for col in required_cols:
        if col not in expo_df_append.columns:
            expo_df_append[col] = ''
    expo_df_append = expo_df_append[required_cols]

    # extract deal to append from adj param and save to csv
    expo_df_append.to_csv(context.inDataPath /
                          'exposure_table_append.csv', index=False)

# TODO: update into class


def post_run_stage_3_adj(context, param):
    # Initialize logger - check if it already has handlers to prevent duplication
    logger_name = 'ecl_adjustment'
    logger = logging.getLogger(logger_name)

    # Only create handler if logger doesn't already have handlers
    if not logger.handlers:
        logger = createLogHandler(
            logger_name, context.outLogPath/'Log_file_ecl_adjustment.log')
    else:
        logger = logging.getLogger(logger_name)

    logger.info("="*60)
    logger.info("Starting stage 3 adjustment...")
    logger.info("="*60)

    # load ecl result
    ecl_df = pd.read_csv(context.outInterimPath /
                         'interim_output_ecl_by_deal.csv')

    logger.info(
        f"Loaded ECL result: {len(ecl_df)} rows, {len(ecl_df.columns)} columns")

    stage_3_adj_param = param['post_run_stage3_param']
    adj_param_df = stage_3_adj_param.copy()

    # Add adj_ind column to the adjustment parameter dataframe
    adj_param_df['adj_ind'] = 'Stage_3'

    logger.info(f"Processing {len(adj_param_df)} stage 3 adjustment rows")

    # Remove existing deals that are in the adjustment parameter
    existing_deal_ids = adj_param_df['deal_id'].unique()
    original_count = len(ecl_df)
    ecl_df = ecl_df[~ecl_df['deal_id'].isin(
        existing_deal_ids)]
    removed_count = original_count - len(ecl_df)

    if removed_count > 0:
        logger.info(
            f"Removed {removed_count} existing deals that are in adjustment parameters")

    # Concatenate the dataframes - pandas will automatically handle missing columns
    ecl_df = pd.concat(
        [ecl_df, adj_param_df], ignore_index=True)

    logger.info(
        f"Added {len(adj_param_df)} new deals from adjustment parameters")

    logger.info("="*60)
    logger.info("Stage 3 adjustment complete")
    logger.info("="*60)

    return ecl_df


def post_run_output_adj(context, param):
    # Initialize logger - check if it already has handlers to prevent duplication
    logger_name = 'ecl_adjustment'
    logger = logging.getLogger(logger_name)

    # Only create handler if logger doesn't already have handlers
    if not logger.handlers:
        logger = createLogHandler(
            logger_name, context.outLogPath/'Log_file_ecl_adjustment.log')
    else:
        logger = logging.getLogger(logger_name)

    logger.info("="*60)
    logger.info("Starting post-run output adjustment...")
    logger.info("="*60)

    param_table = param['post_run_output_adj_param_test']

    ecl_df = pd.read_csv(context.outInterimPath /
                         'interim_output_ecl_by_deal.csv')

    logger.info(
        f"Loaded ECL DataFrame: {len(ecl_df)} rows, {len(ecl_df.columns)} columns")

    # Ensure all DataFrame columns are lowercase for consistency
    ecl_df.columns = ecl_df.columns.str.lower()

    valid_actions = {'Override', 'Overlay'}
    valid_approaches = {'=', '+', '-', '*', '/'}

    # Identify all condition columns
    cond_col_names = [
        col for col in param_table.columns if col.startswith('condition_column_')]
    cond_val_names = [
        col for col in param_table.columns if col.startswith('condition_value_')]
    cond_col_names.sort()
    cond_val_names.sort()

    logger.info(f"Processing {len(param_table)} adjustment rows")

    for idx, row in param_table.iterrows():
        action = row['action']
        customer_level = row['customer_level']
        adj_approach = row['adj_approach']
        adj_column = str(row['adj_column']).strip().lower()
        adj_value = row['adj_value']
        adj_dtype = row['adj_dtype']

        # --- Validation ---
        if action not in valid_actions:
            raise ValueError(f"Invalid action '{action}' at row {idx}.")
        if adj_approach not in valid_approaches:
            raise ValueError(
                f"Invalid adj_approach '{adj_approach}' at row {idx}.")
        if adj_approach == '=' and action != 'Override':
            raise ValueError(
                f"adj_approach '=' only allowed for Override at row {idx}.")
        if customer_level not in ['N', 'Y']:
            raise ValueError(
                f"Invalid customer_level '{customer_level}' at row {idx}. Only 'N' and 'Y' are supported.")

        # Build condition description
        conditions = []
        for cond_col, cond_val in zip(cond_col_names, cond_val_names):
            col_name = str(row[cond_col]).strip().lower()
            val_expr = str(row[cond_val]).strip()
            if col_name and val_expr and val_expr.lower() != 'nan':
                conditions.append(f"{col_name}: {val_expr}")

        condition_desc = "; ".join(
            conditions) if conditions else "no conditions"

        if customer_level == 'N':
            # Apply conditions to get mask
            mask = pd.Series([True] * len(ecl_df))
            for cond_col, cond_val in zip(cond_col_names, cond_val_names):
                col_name = str(row[cond_col]).strip().lower()
                val_expr = str(row[cond_val]).strip()

                if not col_name or not val_expr or val_expr.lower() == 'nan':
                    continue

                col_mask = pd.Series([True] * len(ecl_df))
                for clause in val_expr.split(';'):
                    clause = clause.strip().replace(' ', '')

                    if clause.startswith('in:'):
                        values = [v.strip() for v in clause[3:].split(',')]
                        mask_in = pd.Series([False] * len(ecl_df))
                        values_upper = [v.upper() for v in values]
                        if 'NAN' in values_upper:
                            mask_in |= ecl_df[col_name].isna()
                            values = [v for v in values if v.upper() != 'NAN']
                        if values:
                            mask_in |= ecl_df[col_name].isin(values)
                        col_mask &= mask_in

                    elif clause.startswith('notin:'):
                        values = [v.strip() for v in clause[6:].split(',')]
                        mask_notin = pd.Series([True] * len(ecl_df))
                        values_upper = [v.upper() for v in values]
                        if 'NAN' in values_upper:
                            mask_notin &= ~ecl_df[col_name].isna()
                            values = [v for v in values if v.upper() != 'NAN']
                        if values:
                            mask_notin &= ~ecl_df[col_name].isin(values)
                        col_mask &= mask_notin

                    else:
                        raise ValueError(
                            f"Unsupported clause '{clause}' in {cond_val} at row {idx}. Only 'in:' and 'notin:' are supported.")

                mask &= col_mask

            # Log the result
            if mask.sum() > 0:
                # Apply adjustment
                if adj_approach == '=':
                    ecl_df.loc[mask, adj_column] = adj_value
                    logger.info(
                        f"Row {idx+1}: Set {adj_column} = {adj_value} for {mask.sum()} rows where {condition_desc}")
                elif adj_approach == '+':
                    ecl_df.loc[mask, adj_column] = ecl_df.loc[mask,
                                                              adj_column] + adj_value
                    logger.info(
                        f"Row {idx+1}: Added {adj_value} to {adj_column} for {mask.sum()} rows where {condition_desc}")
                elif adj_approach == '-':
                    ecl_df.loc[mask, adj_column] = ecl_df.loc[mask,
                                                              adj_column] - adj_value
                    logger.info(
                        f"Row {idx+1}: Subtracted {adj_value} from {adj_column} for {mask.sum()} rows where {condition_desc}")
                elif adj_approach == '*':
                    ecl_df.loc[mask, adj_column] = ecl_df.loc[mask,
                                                              adj_column] * adj_value
                    logger.info(
                        f"Row {idx+1}: Multiplied {adj_column} by {adj_value} for {mask.sum()} rows where {condition_desc}")
                elif adj_approach == '/':
                    ecl_df.loc[mask, adj_column] = ecl_df.loc[mask,
                                                              adj_column] / adj_value
                    logger.info(
                        f"Row {idx+1}: Divided {adj_column} by {adj_value} for {mask.sum()} rows where {condition_desc}")

                if adj_dtype:
                    ecl_df.loc[mask, adj_column] = ecl_df.loc[mask,
                                                              adj_column].astype(adj_dtype)

                ecl_df.loc[mask, 'adj_ind'] = action
            else:
                logger.warning(
                    f"Row {idx+1}: No rows matched conditions ({condition_desc})")

        else:  # customer_level == 'Y'
            col_name = str(row['condition_column_1']).strip().lower()
            val_expr = str(row['condition_value_1']).strip()

            mask = pd.Series([True] * len(ecl_df))
            for clause in val_expr.split(';'):
                clause = clause.strip().replace(' ', '')

                if clause.startswith('in:'):
                    values = [v.strip() for v in clause[3:].split(',')]
                    mask_in = pd.Series([False] * len(ecl_df))
                    values_upper = [v.upper() for v in values]
                    if 'NAN' in values_upper:
                        mask_in |= ecl_df[col_name].isna()
                        values = [v for v in values if v.upper() != 'NAN']
                    if values:
                        mask_in |= ecl_df[col_name].isin(values)
                    mask &= mask_in

                elif clause.startswith('notin:'):
                    values = [v.strip() for v in clause[6:].split(',')]
                    mask_notin = pd.Series([True] * len(ecl_df))
                    values_upper = [v.upper() for v in values]
                    if 'NAN' in values_upper:
                        mask_notin &= ~ecl_df[col_name].isna()
                        values = [v for v in values if v.upper() != 'NAN']
                    if values:
                        mask_notin &= ~ecl_df[col_name].isin(values)
                    mask &= mask_notin

                else:
                    raise ValueError(
                        f"Unsupported clause '{clause}' in {val_expr} at row {idx}. Only 'in:' and 'notin:' are supported.")

            customer_nrs = ecl_df.loc[mask, col_name].unique()

            if len(customer_nrs) > 0:
                total_deals_affected = 0
                for cust_nr in customer_nrs:
                    cust_mask = (ecl_df[col_name] == cust_nr)
                    deals = ecl_df[cust_mask]
                    total_deals_affected += len(deals)

                    weights = deals['cur_bal_hke'].fillna(
                        0) + deals['int_accr_hke'].fillna(0)
                    total = weights.sum()

                    if total == 0:
                        weights = pd.Series(
                            [1] * len(deals), index=deals.index)
                        total = weights.sum()

                    if adj_approach == '+':
                        distributed_values = adj_value * (weights / total)
                        ecl_df.loc[cust_mask,
                                   adj_column] = deals[adj_column] + distributed_values
                    elif adj_approach == '=':
                        distributed_values = adj_value * (weights / total)
                        ecl_df.loc[cust_mask, adj_column] = distributed_values
                    elif adj_approach == '*':
                        ecl_df.loc[cust_mask,
                                   adj_column] = deals[adj_column] * adj_value
                    elif adj_approach == '/':
                        ecl_df.loc[cust_mask,
                                   adj_column] = deals[adj_column] / adj_value
                    elif adj_approach == '-':
                        ecl_df.loc[cust_mask,
                                   adj_column] = deals[adj_column] - adj_value

                    if adj_dtype:
                        ecl_df.loc[cust_mask, adj_column] = ecl_df.loc[cust_mask, adj_column].astype(
                            adj_dtype)

                    ecl_df.loc[cust_mask, 'adj_ind'] = action

                logger.info(
                    f"Row {idx+1}: Applied {adj_approach} adjustment to {adj_column} for {len(customer_nrs)} customers ({total_deals_affected} deals) where {condition_desc}")
            else:
                logger.warning(
                    f"Row {idx+1}: No customers matched conditions ({condition_desc})")

    logger.info("="*60)
    logger.info(f"Post-run adjustment complete - Final shape: {ecl_df.shape}")
    logger.info("="*60)

    return ecl_df
