import pandas as pd
from utils.loggers import createLogHandler
import logging


def mid_run_adj(context, param, df, interim_step):
    '''
    To adjust the value of certain cols in the expo_df after certain conditions are met.
    The conditions are defined in the mid_run_adj_param.
    The adjustment is applied to the interm output, e.g., exposure_table_preprocess, exposure_table_staged, etc.
    '''
    # Initialize logger - check if it already has handlers to prevent duplication
    logger_name = 'ecl_adjustment'
    logger = logging.getLogger(logger_name)

    # Only create handler if logger doesn't already have handlers
    if not logger.handlers:
        logger = createLogHandler(
            logger_name, context.outLogPath/'Log_file_ecl_adjustment.log')
    else:
        logger = logging.getLogger(logger_name)

    param_table = param['mid_run_adj_param_test']
    param_table = param_table[param_table['interim_output'] == interim_step]

    logger.info("="*60)
    logger.info(f"Starting mid-run adjustment for {interim_step}")
    logger.info("="*60)

    # Ensure all DataFrame columns are lowercase for consistency
    df.columns = df.columns.str.lower()

    valid_actions = {'Override', 'Delete'}
    valid_approaches = {'='}

    # Identify all condition columns
    cond_col_names = [
        col for col in param_table.columns if col.startswith('condition_column_')]
    cond_val_names = [
        col for col in param_table.columns if col.startswith('condition_value_')]
    cond_col_names.sort()
    cond_val_names.sort()

    logger.info(f"Processing {len(param_table)} adjustment rows")
    logger.info(f"Parameter table columns: {list(param_table.columns)}")

    for idx, row in param_table.iterrows():
        action = row['action']
        adj_approach = row['adj_approach']
        adj_column = str(row['adj_column']).strip().lower()
        adj_value = row['adj_value']
        adj_dtype = row['adj_dtype']

        # --- Validation ---
        if action not in valid_actions:
            raise ValueError(f"Invalid action '{action}' at row {idx}.")

        if action == 'Delete':
            if not (pd.isna(adj_approach) or pd.isna(adj_column) or pd.isna(adj_value)):
                logger.warning(
                    "Delete action has adjustment parameters but they will be ignored")
        else:  # action == 'Override'
            if adj_approach not in valid_approaches:
                raise ValueError(
                    f"Invalid adj_approach '{adj_approach}' at row {idx}.")
            if adj_approach == '=' and action != 'Override':
                raise ValueError(
                    f"adj_approach '=' only allowed for Override at row {idx}.")

        # Build condition description
        conditions = []
        for cond_col, cond_val in zip(cond_col_names, cond_val_names):
            col_name = str(row[cond_col]).strip().lower()
            val_expr = str(row[cond_val]).strip()
            if col_name and val_expr and val_expr.lower() != 'nan':
                # Check if condition column exists in DataFrame
                if col_name not in df.columns:
                    logger.warning(
                        f"Row {idx+1}: Condition column '{col_name}' not found in DataFrame")
                    continue
                conditions.append(f"{col_name}: {val_expr}")

        condition_desc = "; ".join(
            conditions) if conditions else "no conditions"

        # Apply conditions to get mask
        mask = pd.Series([True] * len(df), index=df.index)
        for cond_col, cond_val in zip(cond_col_names, cond_val_names):
            col_name = str(row[cond_col]).strip().lower()
            val_expr = str(row[cond_val]).strip()

            if not col_name or not val_expr or val_expr.lower() == 'nan':
                continue

            # Check if condition column exists in DataFrame
            if col_name not in df.columns:
                logger.warning(
                    f"Row {idx+1}: Condition column '{col_name}' not found in DataFrame")
                continue

            col_mask = pd.Series([True] * len(df), index=df.index)
            for clause in val_expr.split(';'):
                clause = clause.strip().replace(' ', '')

                if clause.startswith('in:'):
                    values = [v.strip() for v in clause[3:].split(',')]
                    mask_in = pd.Series([False] * len(df), index=df.index)
                    values_upper = [v.upper() for v in values]
                    if 'NAN' in values_upper:
                        mask_in |= df[col_name].isna()
                        values = [v for v in values if v.upper() != 'NAN']
                    if values:
                        mask_in |= df[col_name].isin(values)
                    col_mask &= mask_in

                elif clause.startswith('notin:'):
                    values = [v.strip() for v in clause[6:].split(',')]
                    mask_notin = pd.Series([True] * len(df), index=df.index)
                    values_upper = [v.upper() for v in values]
                    if 'NAN' in values_upper:
                        mask_notin &= ~df[col_name].isna()
                        values = [v for v in values if v.upper() != 'NAN']
                    if values:
                        mask_notin &= ~df[col_name].isin(values)
                    col_mask &= mask_notin

                else:
                    raise ValueError(
                        f"Unsupported clause '{clause}' in {cond_val} at row {idx}. Only 'in:' and 'notin:' are supported.")

            mask &= col_mask

        # Ensure mask is properly aligned and converted to boolean
        try:
            # Convert mask to boolean array and ensure it's aligned with DataFrame index
            mask_bool = mask.astype(bool)

            # Log the result
            if mask_bool.sum() > 0:
                if action == 'Delete':
                    # For delete, use the boolean mask directly
                    rows_to_delete = df.loc[mask_bool].copy()
                    df = df[~mask_bool].reset_index(drop=True)
                    logger.info(
                        f"Row {idx+1}: Deleted {len(rows_to_delete)} rows where {condition_desc}")
                else:  # action == 'Override'
                    # Check if the column exists in the DataFrame
                    if adj_column not in df.columns:
                        logger.warning(
                            f"Row {idx+1}: Adjustment column '{adj_column}' not found in DataFrame")
                        continue

                    # Ensure mask has the correct length
                    if len(mask_bool) != len(df):
                        logger.error(
                            f"Row {idx+1}: Mask length ({len(mask_bool)}) doesn't match DataFrame length ({len(df)})")
                        continue

                    try:
                        # Handle the adjustment value and dtype conversion
                        if adj_dtype and not pd.isna(adj_dtype):
                            try:
                                # Try to convert the adjustment value to the target dtype first
                                converted_value = pd.Series(
                                    [adj_value]).astype(adj_dtype).iloc[0]
                                df.loc[mask_bool, adj_column] = converted_value
                                logger.info(
                                    f"Row {idx+1}: Set {adj_column} = {converted_value} (converted to {adj_dtype}) for {mask_bool.sum()} rows where {condition_desc}")
                            except (ValueError, TypeError) as dtype_error:
                                logger.warning(
                                    f"Row {idx+1}: Failed to convert adjustment value {adj_value} to {adj_dtype}. "
                                    f"Error: {str(dtype_error)}. Applying value without dtype conversion.")
                                # Apply the original value without dtype conversion
                                df.loc[mask_bool, adj_column] = adj_value
                                logger.info(
                                    f"Row {idx+1}: Set {adj_column} = {adj_value} for {mask_bool.sum()} rows where {condition_desc}")
                        else:
                            # No dtype conversion needed
                            df.loc[mask_bool, adj_column] = adj_value
                            logger.info(
                                f"Row {idx+1}: Set {adj_column} = {adj_value} for {mask_bool.sum()} rows where {condition_desc}")

                        df.loc[mask_bool, 'adj_ind'] = action
                    except Exception as e:
                        logger.error(
                            f"Row {idx+1}: Error applying adjustment: {str(e)}")
                        logger.error(
                            f"Row {idx+1}: Mask sum: {mask_bool.sum()}, DataFrame shape: {df.shape}")
                        continue
            else:
                logger.warning(
                    f"Row {idx+1}: No rows matched conditions ({condition_desc})")
        except Exception as e:
            logger.error(f"Row {idx+1}: Error processing mask: {str(e)}")
            logger.error(
                f"Row {idx+1}: Mask type: {type(mask)}, DataFrame shape: {df.shape}")
            continue

    logger.info("="*60)
    logger.info(f"Mid-run adjustment complete - Final shape: {df.shape}")
    logger.info("="*60)

    return df
