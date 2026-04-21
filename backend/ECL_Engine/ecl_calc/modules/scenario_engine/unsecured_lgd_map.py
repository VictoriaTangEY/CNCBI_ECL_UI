import pandas as pd


def calculate_unsecured_lgd(ead_df, on_off_df, unsecured_lgd_param):
    """
    Calculate unsecured LGD by mapping segment and sub_segment from on_off_df
    to unsecured_lgd_param

    Args:
        ead_df: DataFrame with deal_id
        on_off_df: DataFrame containing on/off balance sheet data with segment and sub_segment
        unsecured_lgd_param: DataFrame containing unsecured LGD parameters by segment/sub_segment/scenario

    Returns:
        DataFrame: DataFrame with unsecured_lgd columns for each scenario
    """
    if ead_df.empty:
        return ead_df

    df = ead_df.copy()

    # Step 1: Map segment and sub_segment from on_off_df using deal_id
    df = map_segment_from_on_off(df, on_off_df)

    # Step 2: Map unsecured_lgd from unsecured_lgd_param using segment and sub_segment
    df = map_unsecured_lgd_from_param(df, unsecured_lgd_param)

    return df


def map_segment_from_on_off(df, on_off_df):
    """
    Map segment and sub_segment from on_off_df using deal_id

    Args:
        df: DataFrame with deal_id
        on_off_df: DataFrame containing on/off balance sheet data

    Returns:
        DataFrame: DataFrame with segment and sub_segment columns
    """
    if on_off_df.empty:
        # If no on_off_df available, set to None
        df['segment'] = None
        df['sub_segment'] = None
        return df

    # Create mapping from deal_id to segment and sub_segment
    segment_mapping = on_off_df.set_index('deal_id')['segment'].to_dict()
    sub_segment_mapping = on_off_df.set_index(
        'deal_id')['sub_segment'].to_dict()

    # Map segment and sub_segment
    df['segment'] = df['deal_id'].map(segment_mapping)
    df['sub_segment'] = df['deal_id'].map(sub_segment_mapping)

    return df


def map_unsecured_lgd_from_param(df, unsecured_lgd_param):
    """
    Map unsecured_lgd_scenario from unsecured_lgd_param using segment and sub_segment

    Args:
        df: DataFrame with segment and sub_segment columns
        unsecured_lgd_param: DataFrame containing unsecured LGD parameters

    Returns:
        DataFrame: DataFrame with unsecured_lgd_scenario columns
    """
    if unsecured_lgd_param.empty:
        # If no unsecured_lgd_param, set all to None and log warning
        print(
            "Warning: No unsecured_lgd_param found - all unsecured_lgd values set to None")
        return df

    # Get unique scenarios from the parameter
    scenarios = unsecured_lgd_param['scenario'].unique().tolist()

    # Create a composite key for mapping
    unsecured_lgd_param_copy = unsecured_lgd_param.copy()
    unsecured_lgd_param_copy['composite_key'] = (
        unsecured_lgd_param_copy['segment'].astype(str) + '_' +
        unsecured_lgd_param_copy['sub_segment'].astype(str)
    )

    # Create composite key for the main dataframe
    df['composite_key'] = df['segment'].astype(
        str) + '_' + df['sub_segment'].astype(str)

    # Create pivot table for efficient lookup
    lgd_pivot = unsecured_lgd_param_copy.pivot_table(
        index='composite_key',
        columns='scenario',
        values='unsecured_lgd',
        aggfunc='first'
    ).reset_index()

    # Map unsecured_lgd for each scenario
    for scenario in scenarios:
        scenario_mapping = lgd_pivot.set_index(
            'composite_key')[scenario].to_dict()
        df[f'unsecured_lgd_{scenario}'] = df['composite_key'].map(
            scenario_mapping)

    # Check for unmapped records and set to 1
    unmapped_mask = ~df['composite_key'].isin(lgd_pivot['composite_key'])
    if unmapped_mask.any():
        # unmapped_count = unmapped_mask.sum()
        # unmapped_deals = df[unmapped_mask]['deal_id'].unique()
        # print(
        #     f"Warning: {unmapped_count} records could not be mapped to unsecured_lgd_param - setting to 1")
        # print(f"Unmapped deal_ids: {unmapped_deals[:10]}...")

        # Set all scenario unsecured_lgd to 1 for unmapped records
        for scenario in scenarios:
            df.loc[unmapped_mask, f'unsecured_lgd_{scenario}'] = 1.0

    # Drop temporary composite_key column
    df = df.drop(columns=['composite_key'])

    return df
