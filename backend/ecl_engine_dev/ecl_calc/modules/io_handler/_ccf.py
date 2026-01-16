import pandas as pd


def ccf_calculation(param: dict, df: pd.DataFrame):
    """
    Calculate the CCF for the given dataframe - off_df.
    """
    df = df.copy()
    ead_param = param['ead_param']
    ccf_param = param['ccf_param']

    # Initialize category column if it doesn't exist
    if 'category' not in df.columns:
        df['category'] = None

    # Initialize ccf column if it doesn't exist
    if 'ccf' not in df.columns:
        df['ccf'] = None

    # Handle on_off_ind_final logic first
    if 'on_off_ind_final' in df.columns:
        # Convert to string and strip whitespace for consistent comparison
        df['on_off_ind_final'] = df['on_off_ind_final'].astype(
            str).str.strip().str.upper()

        # Assign ccf=1 for "ON" records
        on_mask = df['on_off_ind_final'] == 'ON'
        df.loc[on_mask, 'ccf'] = 1

        # For "OFF" records, we'll apply the existing calculation logic
        off_mask = df['on_off_ind_final'] == 'OFF'
        off_df = df[off_mask].copy()

        # Apply existing logic only to OFF records
        if not off_df.empty:
            off_df = _apply_ccf_logic(ead_param, ccf_param, off_df)
            # Update the main dataframe with calculated values for OFF records
            df.loc[off_mask, 'ccf'] = off_df['ccf']
    else:
        # If on_off_ind_final column doesn't exist, apply existing logic to all records
        df = _apply_ccf_logic(ead_param, ccf_param, df)

    return df


def _apply_ccf_logic(ead_param, ccf_param, df):
    """
    Apply the existing CCF calculation logic.
    """
    # Check if ead_param has the required columns
    if not ead_param.empty and 'deal_subtype' in ead_param.columns and 'category' in ead_param.columns:
        # Iterate through each deal_subtype in ead_param
        for _, row in ead_param.iterrows():
            deal_subtype = row['deal_subtype'].strip().lower()
            category = row['category'].strip().lower()

            # Skip if deal_subtype is empty or NaN
            if pd.isna(deal_subtype) or deal_subtype == '':
                continue

            # Check if key contains the deal_subtype (case-insensitive)
            df['deal_subtype'] = df['deal_subtype'].str.strip().str.lower()
            mask = df['deal_subtype'].str.contains(
                deal_subtype, case=False, na=False)

            # Assign category where key contains the deal_subtype
            df.loc[mask, 'category'] = category

    # Assign CCF based on category and additional conditions
    if not ccf_param.empty and 'category' in ccf_param.columns and 'ccf' in ccf_param.columns:
        # Iterate through each row in ccf_param
        for _, param_row in ccf_param.iterrows():
            param_category = param_row['category'].strip().lower()
            param_ccf = param_row['ccf']

            # Skip if category is empty or NaN
            if pd.isna(param_category) or param_category == '':
                continue

            # Create mask for category match
            df['category'] = df['category'].str.strip().str.lower()
            mask = df['category'] == param_category

            # Add additional conditions if they exist in ccf_param
            if 'segment' in ccf_param.columns and param_row['segment'] != '':
                mask = mask & (df['segment'] == param_row['segment'])

            if 'sub_segment' in ccf_param.columns and param_row['sub_segment'] != '':
                mask = mask & (df['sub_segment'] ==
                               param_row['sub_segment'])

            if 'life_condition' in ccf_param.columns and param_row['life_condition'] != '':
                life_cond = param_row['life_condition']
                if life_cond.startswith('<='):
                    value = int(life_cond[2:])
                    mask = mask & (df['remaining_life'] <= value)
                elif life_cond.startswith('>='):
                    value = int(life_cond[2:])
                    mask = mask & (df['remaining_life'] >= value)
                elif life_cond.startswith('<'):
                    value = int(life_cond[1:])
                    mask = mask & (df['remaining_life'] < value)
                elif life_cond.startswith('>'):
                    value = int(life_cond[1:])
                    mask = mask & (df['remaining_life'] > value)
                elif life_cond.startswith('='):
                    value = int(life_cond[1:])
                    mask = mask & (df['remaining_life'] == value)

            # Assign CCF where all conditions are satisfied
            df.loc[mask, 'ccf'] = param_ccf

    return df
