import pandas as pd
import numpy as np


class AddColsHandler:
    """
    Handler for adding additional columns to DataFrames
    """

    def add_cols(self, df, param):
        """
        Add columns to the DataFrame using vectorized operations for better performance

        Args:
            df (pandas.DataFrame): Input DataFrame
            param (dict): Parameter dictionary containing lookup tables

        Returns:
            pandas.DataFrame: DataFrame with new columns added
        """
        # Add basic columns
        df = self._elim(df)
        df = self._c800(df, param)
        df = self._product(df, param)
        df = self._interco_cd(df, param)
        df = self._class(df)
        df = self._stage(df)
        df = self._entity1(df)
        df = self._entity2(df)
        df = self._coa_entity(df)
        df = self._bu1(df)
        df = self._bu_off2(df)
        df = self._bu2(df)
        # bu4 needs to be initialized before bu3 (bu3 checks bu4 for empty values)
        df = self._bu4(df)
        df = self._bu3(df)
        df = self._profit_centre_1(df)
        df = self._coa_prod_gp1(df)
        df = self._product1(df)
        df = self._ceo1(df)
        df = self._ceo2(df)

        return df

    def _elim(self, df):
        """
        Add elimination column: elim = 1 if intercompany == '000', else 0.
        See _add_cols_docs.FUNCTION_DOCS['_elim'] for detailed logic.
        """
        if 'intercompany' in df.columns:
            df['elim'] = (df['intercompany'].astype(str) == '000').astype(int)
        return df

    def _c800(self, df, param):
        """
        Add c800 column using vectorized operations.
        Only processes deal types that are not "UNDRWN" and can be converted to float.
        See _add_cols_docs.FUNCTION_DOCS['_c800'] for detailed logic.
        """
        if 'deal_type' not in df.columns or 'chart_of_accounts_param' not in param:
            return df

        chart_df = param['chart_of_accounts_param']
        deal_type_series = df['deal_type']

        # Create a mapping dictionary for faster lookup
        c800_mapping = {}
        for _, row in chart_df.iterrows():
            low = row.get('child value low')
            high = row.get('child value high')
            c800 = row.get('c800')

            if pd.notna(low) and pd.notna(high) and pd.notna(c800):
                try:
                    low_val = float(low)
                    high_val = float(high)
                    c800_mapping[(low_val, high_val)] = c800
                except (ValueError, TypeError):
                    continue

        # Vectorized lookup
        result = pd.Series(index=deal_type_series.index, dtype=object)

        # Vectorized validation - much faster than for loop
        # Convert to string and check for UNDRWN
        deal_type_str = deal_type_series.astype(str).str.upper()
        undrwn_mask = deal_type_str == 'UNDRWN'

        # Try to convert to float vectorized
        try:
            deal_type_float = pd.to_numeric(deal_type_series, errors='coerce')
            # Valid mask: not UNDRWN and not NaN (which means conversion failed)
            valid_mask = ~undrwn_mask & deal_type_float.notna()
        except:
            # Fallback if vectorized conversion fails
            valid_mask = pd.Series(
                [True] * len(deal_type_series), index=deal_type_series.index)
            for idx, deal_type in deal_type_series.items():
                if pd.isna(deal_type) or str(deal_type).upper() == 'UNDRWN':
                    valid_mask[idx] = False
                else:
                    try:
                        float(deal_type)
                    except (ValueError, TypeError):
                        valid_mask[idx] = False

        # Only process valid deal types
        valid_deal_types = deal_type_series[valid_mask]
        valid_deal_types_float = pd.to_numeric(
            valid_deal_types, errors='coerce')

        # Vectorized range checking for all mappings at once
        for (low, high), c800_val in c800_mapping.items():
            mask = (valid_deal_types_float >= low) & (
                valid_deal_types_float <= high)
            result[valid_deal_types[mask].index] = c800_val

        df['c800'] = result
        return df

    def _product(self, df, param):
        """
        Add product column using vectorized operations.
        Includes patch: if deal_type is "UNDRAWN" then product="OFF-balance".
        See _add_cols_docs.FUNCTION_DOCS['_product'] for detailed logic.
        """
        if 'c800' not in df.columns or 'c800_product_param' not in param:
            return df

        product_df = param['c800_product_param']
        c800_series = df['c800']

        # Create a mapping dictionary for faster lookup
        product_mapping = dict(zip(product_df['c800'], product_df['product']))

        # Vectorized lookup using map
        df['product'] = c800_series.map(product_mapping)

        # patch: if deal_type is "UNDRAWN" then product="OFF-balance" (vectorized)
        if 'deal_type' in df.columns:
            df.loc[df['deal_type'].astype(str).str.upper(
            ) == "UNDRAWN", 'product'] = "OFF-balance"

        return df

    def _interco_cd(self, df, param):
        """
        Add interco_cd column using vectorized operations.
        See _add_cols_docs.FUNCTION_DOCS['_interco_cd'] for detailed logic.
        """
        if 'interco_cd_param' not in param:
            return df

        interco_df = param['interco_cd_param']
        condition_fields = ['entity', 'cust_id', 'remarks',
                            'resd_country_cd', 'country_of_risk']

        # Filter condition fields that exist in both dataframes
        available_fields = [field for field in condition_fields
                            if field in df.columns and field in interco_df.columns]

        if not available_fields:
            df['interco_cd'] = pd.Series([None] * len(df), index=df.index)
            return df

        # Optimized composite key creation - pre-fill with empty strings
        df_subset = df[available_fields].fillna('')
        interco_subset = interco_df[available_fields].fillna('')

        # Convert to string once and join efficiently
        df_key = df_subset.astype(str).agg('_'.join, axis=1)
        interco_key = interco_subset.astype(str).agg('_'.join, axis=1)

        # Create mapping dictionary - use pandas merge for better performance
        interco_df_with_key = interco_df.copy()
        interco_df_with_key['_composite_key'] = interco_key

        # Use merge instead of map for better performance with large datasets
        df_with_key = df.copy()
        df_with_key['_composite_key'] = df_key

        # Merge and extract interco_cd
        merged = df_with_key[['_composite_key']].merge(
            interco_df_with_key[['_composite_key', 'interco_cd']],
            on='_composite_key',
            how='left'
        )

        df['interco_cd'] = merged['interco_cd']
        return df

    def _class(self, df):
        """
        Add class column: if product is "Loans" then "Loans" else "Non-loans".
        See _add_cols_docs.FUNCTION_DOCS['_class'] for detailed logic.
        """
        if 'product' in df.columns:
            df['class'] = np.where(
                df['product'] == "Loans", "Loans", "Non-loans")
        return df

    def _stage(self, df):
        """
        Add stage column: 'Stage ' + final_stage.
        See _add_cols_docs.FUNCTION_DOCS['_stage'] for detailed logic.
        """
        if 'final_stage' in df.columns:
            df['stage'] = 'Stage ' + df['final_stage'].astype(str).str.strip()
        return df

    def _entity1(self, df):
        """
        Add entity1 column based on entity mapping.
        Maps entity codes to entity names (e.g., '018' -> 'CNCBI').
        See _add_cols_docs.FUNCTION_DOCS['_entity1'] for detailed logic.
        """
        if 'entity' not in df.columns:
            return df

        # Handle entity conversion: ensure numeric entities are zero-padded to 3 digits
        # but preserve alphanumeric entities like '083LA', '083NY' as-is
        ent = df['entity'].astype(str)
        # Only zfill if the entity is purely numeric and <= 3 digits
        numeric_mask = ent.str.match(r'^\d{1,3}$')
        ent = ent.copy()  # Keep as pandas Series
        ent.loc[numeric_mask] = ent.loc[numeric_mask].str.zfill(3)

        conds = [
            ent.str.startswith('018'),
            ent.str.startswith('019'),
            ent.str.startswith('023'),
            ent.str.startswith('084'),
            ent.str.startswith('090'),
            ent.str.startswith('801'),
            ent.str.startswith('083LA'),
            ent.str.startswith('083NY'),
        ]
        choices = [
            'CNCBI',
            'HKCBF',
            'Viewcon',
            'MC Branch',
            'SG Branch',
            'CBI China',
            'LA Branch',
            'NY Branch',
        ]
        df['entity1'] = np.select(conds, choices, default='')
        return df

    def _entity2(self, df):
        """
        Add entity2 column based on entity1 mapping.
        Default: 'CNCBI', override if entity1 is 'HKCBF' or 'CBI China'.
        See _add_cols_docs.FUNCTION_DOCS['_entity2'] for detailed logic.
        """
        if 'entity1' not in df.columns:
            return df

        # Default value: 'CNCBI'
        df['entity2'] = 'CNCBI'

        # Override if entity1 == 'HKCBF'
        df.loc[df['entity1'] == 'HKCBF', 'entity2'] = 'HKCBF'

        # Override if entity1 == 'CBI China'
        df.loc[df['entity1'] == 'CBI China', 'entity2'] = 'CBI China'

        return df

    def _coa_entity(self, df):
        """
        Add coa_entity column based on entity1, location, cust_bk_group, product, and bu.
        Default: entity1, with conditional overrides based on location, cust_bk_group, and product.
        See _add_cols_docs.FUNCTION_DOCS['_coa_entity'] for detailed logic.
        """
        # Check required columns
        required_cols = ['entity1']
        if not all(col in df.columns for col in required_cols):
            return df

        # Prepare derived fields (LOCATION_F, CUST_BK_GROUP_F, BU_F)
        location_f = df['location'].astype(str).str.strip(
        ) if 'location' in df.columns else pd.Series('', index=df.index)
        cust_bk_group_f = df['cust_bk_group'].astype(str).str.strip(
        ) if 'cust_bk_group' in df.columns else pd.Series('', index=df.index)
        bu_f = df['bu'].astype(str).str.strip(
        ) if 'bu' in df.columns else pd.Series('', index=df.index)

        # Get entity1 and product
        entity1 = df['entity1'].astype(str)
        product = df['product'].astype(
            str) if 'product' in df.columns else pd.Series('', index=df.index)

        # Default value: coa_entity = entity1
        df['coa_entity'] = entity1

        # Apply conditional overrides based on LOCATION_F and CUST_BK_GROUP_F
        # Shanghai
        shanghai_pbg_mask = (location_f == 'Shanghai') & (
            cust_bk_group_f == '1')
        df.loc[shanghai_pbg_mask, 'coa_entity'] = 'CBIC_Shanghai_PBG'

        shanghai_wbg_mask = (location_f == 'Shanghai') & (
            cust_bk_group_f != '1')
        df.loc[shanghai_wbg_mask, 'coa_entity'] = 'CBIC_Shanghai_WBG'

        # Shenzhen
        shenzhen_pbg_mask = (location_f == 'Shenzhen') & (
            cust_bk_group_f == '1')
        df.loc[shenzhen_pbg_mask, 'coa_entity'] = 'CBIC_Shenzhen_PBG'

        shenzhen_wbg_mask = (location_f == 'Shenzhen') & (
            cust_bk_group_f != '1')
        df.loc[shenzhen_wbg_mask, 'coa_entity'] = 'CBIC_Shenzhen_WBG'

        # Beijing
        beijing_pbg_mask = (location_f == 'Beijing') & (cust_bk_group_f == '1')
        df.loc[beijing_pbg_mask, 'coa_entity'] = 'CBIC_Beijing_PBG'

        beijing_wbg_mask = (location_f == 'Beijing') & (cust_bk_group_f != '1')
        df.loc[beijing_wbg_mask, 'coa_entity'] = 'CBIC_Beijing_WBG'

        # Additional override: if entity1 = 'CBI China' and LOCATION_F = '' then coa_entity = 'CBIC_Shenzhen_WBG'
        cbi_china_empty_location_mask = (
            entity1 == 'CBI China') & (location_f == '')
        df.loc[cbi_china_empty_location_mask,
               'coa_entity'] = 'CBIC_Shenzhen_WBG'

        # Additional overrides for Loans + CNCBI
        # if product = 'Loans' and entity1 = 'CNCBI' and BU_F starts with 'PBG' then coa_entity = 'CNCBI_PBG'
        loans_cncbi_pbg_mask = (product == 'Loans') & (
            entity1 == 'CNCBI') & (bu_f.str.startswith('PBG'))
        df.loc[loans_cncbi_pbg_mask, 'coa_entity'] = 'CNCBI_PBG'

        # if product = 'Loans' and entity1 = 'CNCBI' and coa_entity != 'CNCBI_PBG' then coa_entity = 'CNCBI_WBG'
        loans_cncbi_wbg_mask = (product == 'Loans') & (
            entity1 == 'CNCBI') & (df['coa_entity'] != 'CNCBI_PBG')
        df.loc[loans_cncbi_wbg_mask, 'coa_entity'] = 'CNCBI_WBG'

        return df

    def _bu1(self, df):
        """
        Add bu1 column based on coa_entity and product.
        Only applies when Product = 'Loans'. Maps coa_entity to PBG-Non-BB, PBG-BB, WBG, or RAM.
        See _add_cols_docs.FUNCTION_DOCS['_bu1'] for detailed logic.
        """
        # Check required columns
        required_cols = ['coa_entity']
        if not all(col in df.columns for col in required_cols):
            return df

        # Prepare derived field: COA_ENTITY_F = COA_ENTITY
        coa_entity_f = df['coa_entity'].astype(str)

        # Get product
        product = df['product'].astype(
            str) if 'product' in df.columns else pd.Series('', index=df.index)

        # Initialize bu1 column (default empty)
        df['bu1'] = ''

        # Only apply logic if Product = 'Loans'
        loans_mask = product == 'Loans'

        if loans_mask.any():
            # PBG-Non-BB
            pbg_non_bb_values = ['HKCBF', 'CNCBI_PBG_nonBB', 'Viewcon']
            pbg_non_bb_mask = loans_mask & coa_entity_f.isin(pbg_non_bb_values)
            df.loc[pbg_non_bb_mask, 'bu1'] = 'PBG-Non-BB'

            # PBG-BB
            pbg_bb_values = [
                'CBIC_Beijing_PBG', 'CBIC_Shanghai_PBG', 'CBIC_Shenzhen_PBG', 'CNCBI_PBG_BB']
            pbg_bb_mask = loans_mask & coa_entity_f.isin(pbg_bb_values)
            df.loc[pbg_bb_mask, 'bu1'] = 'PBG-BB'

            # WBG
            wbg_values = ['CNCBI_WBG', 'LA Branch', 'MC Branch', 'NY Branch', 'CBIC_Beijing_WBG',
                          'CBIC_Shenzhen_WBG', 'CBIC_Shanghai_WBG', 'SG Branch']
            wbg_mask = loans_mask & coa_entity_f.isin(wbg_values)
            df.loc[wbg_mask, 'bu1'] = 'WBG'

            # RAM
            ram_values = ['CNCBI_RAM']
            ram_mask = loans_mask & coa_entity_f.isin(ram_values)
            df.loc[ram_mask, 'bu1'] = 'RAM'

        return df

    def _bu_off2(self, df):
        """
        Add bu_off2 column based on bu_off, cust_bk_group, and mcm3.
        Default: bu_off, with overrides based on cust_bk_group and mcm3.
        See _add_cols_docs.FUNCTION_DOCS['_bu_off2'] for detailed logic.
        """
        # Check if bu_off column exists
        if 'bu_off' not in df.columns:
            return df

        # Default value: bu_off2 = bu_off
        df['bu_off2'] = df['bu_off'].astype(str)

        # Get cust_bk_group and mcm3
        cust_bk_group = df['cust_bk_group'].astype(
            str) if 'cust_bk_group' in df.columns else pd.Series('', index=df.index)
        mcm3 = df['mcm3'].astype(
            str) if 'mcm3' in df.columns else pd.Series('', index=df.index)

        # Apply conditional overrides
        # if CUST_BK_GROUP = '1' then bu_off2 = 'PBG-Non-BB'
        df.loc[cust_bk_group == '1', 'bu_off2'] = 'PBG-Non-BB'

        # if CUST_BK_GROUP in ('2', 'R') then bu_off2 = 'PBG-BB'
        df.loc[cust_bk_group.isin(['2', 'R']), 'bu_off2'] = 'PBG-BB'

        # if CUST_BK_GROUP = '4' then bu_off2 = 'WBG'
        df.loc[cust_bk_group == '4', 'bu_off2'] = 'WBG'

        # if MCM3 = 'Credit Card' then bu_off2 = 'PBG-Non-BB'
        df.loc[mcm3 == 'Credit Card', 'bu_off2'] = 'PBG-Non-BB'

        return df

    def _bu2(self, df):
        """
        Add bu2 column based on bu1, bus_unit, coa_entity, deal_id, account_officer, and deal_subtype.
        Default: bu1, with conditional overrides when bu1 = 'PBG-Non-BB'.
        See _add_cols_docs.FUNCTION_DOCS['_bu2'] for detailed logic.
        """
        # Check required columns
        if 'bu1' not in df.columns:
            return df

        # Default value: bu2 = bu1
        df['bu2'] = df['bu1'].astype(str)

        # Get required fields
        bu1 = df['bu1'].astype(str)
        coa_entity_f = df['coa_entity'].astype(
            str) if 'coa_entity' in df.columns else pd.Series('', index=df.index)
        bus_unit = df['bus_unit'].astype(
            str) if 'bus_unit' in df.columns else pd.Series('', index=df.index)
        deal_tfi_id = df['deal_id'].astype(
            str) if 'deal_id' in df.columns else pd.Series('', index=df.index)
        account_officer = df['account_officer'].astype(
            str) if 'account_officer' in df.columns else pd.Series('', index=df.index)
        deal_subtype = df['deal_subtype'].astype(
            str) if 'deal_subtype' in df.columns else pd.Series('', index=df.index)

        # Apply conditional overrides (order matters)
        pbg_non_bb_mask = bu1 == 'PBG-Non-BB'

        # if BU1 = 'PBG-Non-BB' and (BUS_UNIT = 'MB' or COA_ENTITY_F = 'HKCBF') then BU2 = 'Mortgage & HKCBF'
        mask1 = pbg_non_bb_mask & (
            (bus_unit == 'MB') | (coa_entity_f == 'HKCBF'))
        df.loc[mask1, 'bu2'] = 'Mortgage & HKCBF'

        # if BU1 = 'PBG-Non-BB' and BU2 = 'PBG-Non-BB' and COA_ENTITY_F = 'HKCBF' then BU2 = 'Mortgage & HKCBF'
        mask2 = pbg_non_bb_mask & (
            df['bu2'] == 'PBG-Non-BB') & (coa_entity_f == 'HKCBF')
        df.loc[mask2, 'bu2'] = 'Mortgage & HKCBF'

        # if BU1 = 'PBG-Non-BB' and BUS_UNIT in ('CUCL', 'WM') then BU2 = 'Wealth Mgt & CF'
        mask3 = pbg_non_bb_mask & bus_unit.isin(['CUCL', 'WM'])
        df.loc[mask3, 'bu2'] = 'Wealth Mgt & CF'

        # if BU1 = 'PBG-Non-BB' and BU2 = 'PBG-Non-BB' and deal_tfi_id starts with 'CARDLINK' then BU2 = 'Wealth Mgt & CF'
        mask4 = pbg_non_bb_mask & (
            df['bu2'] == 'PBG-Non-BB') & (deal_tfi_id.str.startswith('CARDLINK'))
        df.loc[mask4, 'bu2'] = 'Wealth Mgt & CF'

        # if BU1 = 'PBG-Non-BB' and (BUS_UNIT in ('PB') or ACCOUNT_OFFICER starts with 'R8') then BU2 = 'Private Banking'
        mask5 = pbg_non_bb_mask & ((bus_unit == 'PB') | (
            account_officer.str.startswith('R8')))
        df.loc[mask5, 'bu2'] = 'Private Banking'

        # if BU1 = 'PBG-Non-BB' and BUS_UNIT in ('STAFF') then BU2 = 'Own Fund'
        mask6 = pbg_non_bb_mask & (bus_unit == 'STAFF')
        df.loc[mask6, 'bu2'] = 'Own Fund'

        # if BU1 = 'PBG-Non-BB' and BU2 = 'PBG-Non-BB' and deal_subtype = '018:ALS:MSI' then BU2 = 'Mortgage & HKCBF'
        mask7 = pbg_non_bb_mask & (
            df['bu2'] == 'PBG-Non-BB') & (deal_subtype == '018:ALS:MSI')
        df.loc[mask7, 'bu2'] = 'Mortgage & HKCBF'

        # if BU1 = 'PBG-Non-BB' and BU2 = 'PBG-Non-BB' and deal_subtype starts with '018:IM CORE' then BU2 = 'Wealth Mgt & CF'
        mask8 = pbg_non_bb_mask & (
            df['bu2'] == 'PBG-Non-BB') & (deal_subtype.str.startswith('018:IM CORE'))
        df.loc[mask8, 'bu2'] = 'Wealth Mgt & CF'

        return df

    def _bu3(self, df):
        """
        Add bu3 column based on entity1, product_1, bu2, entity, bu_off2, coa_prod_gp1, and bu4.
        Has two paths: ENTITY1+PRODUCT_1+BU1, and ENTITY+BU_OFF2 (overrides path 1).
        Also includes special conditions that may modify bu1, bu3, bu4, and ceo2.
        See _add_cols_docs.FUNCTION_DOCS['_bu3'] for detailed logic.
        """
        # Check required columns
        if 'entity1' not in df.columns:
            return df

        # Get required fields
        entity1 = df['entity1'].astype(str)
        entity = df['entity'].astype(
            str) if 'entity' in df.columns else pd.Series('', index=df.index)
        product_1 = df['product1'].astype(
            str) if 'product1' in df.columns else pd.Series('', index=df.index)
        bu1 = df['bu1'].astype(
            str) if 'bu1' in df.columns else pd.Series('', index=df.index)
        bu2 = df['bu2'].astype(
            str) if 'bu2' in df.columns else pd.Series('', index=df.index)
        bu_off2 = df['bu_off2'].astype(
            str) if 'bu_off2' in df.columns else pd.Series('', index=df.index)
        bu_off = df['bu_off'].astype(
            str) if 'bu_off' in df.columns else pd.Series('', index=df.index)
        mcm3 = df['mcm3'].astype(
            str) if 'mcm3' in df.columns else pd.Series('', index=df.index)
        coa_prod_gp1 = df['coa_prod_gp1'].astype(
            str) if 'coa_prod_gp1' in df.columns else pd.Series('', index=df.index)
        c800 = df['c800'].astype(
            str) if 'c800' in df.columns else pd.Series('', index=df.index)
        bu4 = df['bu4'].astype(
            str) if 'bu4' in df.columns else pd.Series('', index=df.index)

        # Initialize bu3 column
        df['bu3'] = ''

        # Path 1: ENTITY1 + PRODUCT_1 + BU1 -> BU3
        # Default: bu3 = bu2
        df['bu3'] = bu2

        # if ENTITY1 = 'CNCBI' and BU2 = 'WBG' then BU3 = 'WBGHK'
        df.loc[(entity1 == 'CNCBI') & (bu2 == 'WBG'), 'bu3'] = 'WBGHK'

        # if ENTITY1 = 'CBI China' and BU2 = 'PBG-BB' then BU3 = 'CBI China PBD'
        df.loc[(entity1 == 'CBI China') & (
            bu2 == 'PBG-BB'), 'bu3'] = 'CBI China PBD'

        # if ENTITY1 = 'CBI China' and BU2 = 'WBG' then BU3 = 'CBI China WBD'
        df.loc[(entity1 == 'CBI China') & (
            bu2 == 'WBG'), 'bu3'] = 'CBI China WBD'

        # if ENTITY1 = 'MC Branch' then BU3 = 'Macau'
        df.loc[entity1 == 'MC Branch', 'bu3'] = 'Macau'

        # if ENTITY1 = 'SG Branch' then BU3 = 'SG'
        df.loc[entity1 == 'SG Branch', 'bu3'] = 'SG'

        # if ENTITY1 = 'LA Branch' then BU3 = 'US (LA)'
        df.loc[entity1 == 'LA Branch', 'bu3'] = 'US (LA)'

        # if ENTITY1 = 'NY Branch' then BU3 = 'US (NY)'
        df.loc[entity1 == 'NY Branch', 'bu3'] = 'US (NY)'

        # if Product_1 = 'Other Account' and BU1 = 'RAM' then BU3 = 'WBGHK'
        df.loc[(product_1 == 'Other Account') &
               (bu1 == 'RAM'), 'bu3'] = 'WBGHK'

        # Path 2: ENTITY + BU_OFF2 -> BU3 (overrides path 1)
        # if MCM3 in ('Credit Card') or BU_OFF2 = 'PBG-Non-BB' then BU3 = 'Wealth Mgt & CF'
        df.loc[(mcm3 == 'Credit Card') | (
            bu_off2 == 'PBG-Non-BB'), 'bu3'] = 'Wealth Mgt & CF'

        # if ENTITY = 'CNCBI' and BU_OFF2 = 'WBG' then BU3 = 'WBGHK'
        df.loc[(entity == 'CNCBI') & (bu_off2 == 'WBG'), 'bu3'] = 'WBGHK'

        # if ENTITY = 'CNCBI' and BU_OFF2 = 'PBG-BB' then BU3 = 'PBG-BB'
        df.loc[(entity == 'CNCBI') & (bu_off2 == 'PBG-BB'), 'bu3'] = 'PBG-BB'

        # if ENTITY in ('SG Branch') then BU3 = 'SG'
        df.loc[entity == 'SG Branch', 'bu3'] = 'SG'

        # if ENTITY in ('MC Branch') then BU3 = 'Macau'
        df.loc[entity == 'MC Branch', 'bu3'] = 'Macau'

        # if ENTITY in ('LA Branch') then BU3 = 'US (LA)'
        df.loc[entity == 'LA Branch', 'bu3'] = 'US (LA)'

        # if ENTITY in ('NY Branch') then BU3 = 'US (NY)'
        df.loc[entity == 'NY Branch', 'bu3'] = 'US (NY)'

        # if ENTITY in ('CBI China') and BU_OFF = 'WBG' then BU3 = 'CBI China WBD'
        df.loc[(entity == 'CBI China') & (
            bu_off == 'WBG'), 'bu3'] = 'CBI China WBD'

        # if ENTITY in ('CBI China') and BU_OFF = 'PBG' then BU3 = 'CBI China PBD'
        df.loc[(entity == 'CBI China') & (
            bu_off.str.startswith('PBG')), 'bu3'] = 'CBI China PBD'

        # Special conditions based on COA_PROD_GP1 + Product_1 + ENTITY1 + BU3 + BU4
        # Check for empty strings (SAS uses ' ' for empty)
        # Re-extract bu3 after all modifications above
        bu3 = df['bu3'].astype(str)
        empty_mask = (bu1 == '') | (bu1.isna()) | (bu3 == '') | (
            bu3.isna()) | (bu4 == '') | (bu4.isna())

        # if COA_PROD_GP1 = 'LOA' and Product_1 = 'Loans' and ENTITY1 = 'CBI China' and BU1 = ' ' and BU3 = ' ' and BU4 = ' ' then:
        mask1 = (coa_prod_gp1 == 'LOA') & (product_1 == 'Loans') & (
            entity1 == 'CBI China') & empty_mask
        df.loc[mask1, 'bu1'] = 'WBG'
        df.loc[mask1, 'bu3'] = 'CBI China WBD'
        df.loc[mask1, 'bu4'] = 'WBG'
        if 'ceo2' not in df.columns:
            df['ceo2'] = ''
        df.loc[mask1, 'ceo2'] = 'CBI China_WBD'

        # if COA_PROD_GP1 = 'Fin Gua' and Product_1 = 'Off-balance' and ENTITY1 = 'CBI China' and BU1 = ' ' and BU3 = ' ' and BU4 = ' ' then:
        mask2 = (coa_prod_gp1 == 'Fin Gua') & (
            product_1 == 'Off-balance') & (entity1 == 'CBI China') & empty_mask
        df.loc[mask2, 'bu1'] = 'WBG'
        df.loc[mask2, 'bu3'] = 'CBI China WBD'
        df.loc[mask2, 'bu4'] = 'WBG'
        df.loc[mask2, 'ceo2'] = 'CBI China_WBD'

        # if COA_PROD_GP1 = 'LOA Com+Fact' and Product_1 = 'Off-balance' and ENTITY1 = 'CNCBI' and BU1 = ' ' and BU3 = ' ' and BU4 = ' '
        # and C800 in ('Forward Contract-MM Loan', 'Forward Contract-Reverse Repo') then:
        mask3 = (coa_prod_gp1 == 'LOA Com+Fact') & (product_1 == 'Off-balance') & (entity1 == 'CNCBI') & empty_mask & \
            c800.isin(['Forward Contract-MM Loan',
                      'Forward Contract-Reverse Repo'])
        df.loc[mask3, 'bu1'] = 'TMG'
        df.loc[mask3, 'bu3'] = 'TMG'
        df.loc[mask3, 'bu4'] = 'TMG'

        return df

    def _bu4(self, df):
        """
        Add bu4 column based on bu1, bus_unit, coa_entity, c800, and deal_subtype.
        Default: bu1, with conditional overrides when bu4 in ('PBG-BB', 'PBG-Non-BB').
        Final override: 'PBG-BB' -> 'BB - SME'.
        See _add_cols_docs.FUNCTION_DOCS['_bu4'] for detailed logic.
        """
        # Check required columns
        if 'bu1' not in df.columns:
            return df

        # Default value: bu4 = bu1
        df['bu4'] = df['bu1'].astype(str)

        # Get required fields
        coa_entity_f = df['coa_entity'].astype(
            str) if 'coa_entity' in df.columns else pd.Series('', index=df.index)
        bus_unit = df['bus_unit'].astype(
            str) if 'bus_unit' in df.columns else pd.Series('', index=df.index)
        c800 = df['c800'].astype(
            str) if 'c800' in df.columns else pd.Series('', index=df.index)
        deal_subtype = df['deal_subtype'].astype(
            str) if 'deal_subtype' in df.columns else pd.Series('', index=df.index)
        bu2 = df['bu2'].astype(
            str) if 'bu2' in df.columns else pd.Series('', index=df.index)

        # Base condition: BU4 in ('PBG-BB', 'PBG-Non-BB')
        pbg_mask = df['bu4'].isin(['PBG-BB', 'PBG-Non-BB'])

        # Apply conditional overrides (order matters)
        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and COA_ENTITY_F = 'HKCBF' then BU4 = 'HKCBF'
        df.loc[pbg_mask & (coa_entity_f == 'HKCBF'), 'bu4'] = 'HKCBF'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'AUTO' then BU4 = 'Auto Finance'
        df.loc[pbg_mask & (bus_unit == 'AUTO'), 'bu4'] = 'Auto Finance'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'BAS' and C800 != 'Instalment Loans' then BU4 = 'BB - BAS'
        df.loc[pbg_mask & (bus_unit == 'BAS') & (
            c800 != 'Instalment Loans'), 'bu4'] = 'BB - BAS'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'BAS' and C800 = 'Instalment Loans' then BU4 = 'Shared BAS'
        df.loc[pbg_mask & (bus_unit == 'BAS') & (
            c800 == 'Instalment Loans'), 'bu4'] = 'Shared BAS'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'CUCL' and C800 != 'Advance to Cardholders' then BU4 = 'UCL'
        df.loc[pbg_mask & (bus_unit == 'CUCL') & (
            c800 != 'Advance to Cardholders'), 'bu4'] = 'UCL'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'CUCL' and C800 = 'Advance to Cardholders' then BU4 = 'Credit Card'
        df.loc[pbg_mask & (bus_unit == 'CUCL') & (
            c800 == 'Advance to Cardholders'), 'bu4'] = 'Credit Card'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'M&E' then BU4 = 'M&E Finance'
        df.loc[pbg_mask & (bus_unit == 'M&E'), 'bu4'] = 'M&E Finance'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'MB' then BU4 = 'Mortgage'
        df.loc[pbg_mask & (bus_unit == 'MB'), 'bu4'] = 'Mortgage'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'PB' then BU4 = 'Private Banking'
        df.loc[pbg_mask & (bus_unit == 'PB'), 'bu4'] = 'Private Banking'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'SME' then BU4 = 'BB - SME'
        df.loc[pbg_mask & (bus_unit == 'SME'), 'bu4'] = 'BB - SME'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'STAFF' then BU4 = 'Staff Loans - Own Fund'
        df.loc[pbg_mask & (bus_unit == 'STAFF'),
               'bu4'] = 'Staff Loans - Own Fund'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'WM' then BU4 = 'Wealth Mgt'
        df.loc[pbg_mask & (bus_unit == 'WM'), 'bu4'] = 'Wealth Mgt'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and C800 = 'Advance to Cardholders' then BU4 = 'Credit Card'
        df.loc[pbg_mask & (c800 == 'Advance to Cardholders'),
               'bu4'] = 'Credit Card'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and C800 = 'Personal Instalment Loan' then BU4 = 'UCL'
        df.loc[pbg_mask & (c800 == 'Personal Instalment Loan'), 'bu4'] = 'UCL'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and COA_ENTITY in ('LA Branch', 'NY Branch', 'MC Branch', 'SG Branch', 'CBI China') then BU4 = 'WBG'
        df.loc[pbg_mask & coa_entity_f.isin(
            ['LA Branch', 'NY Branch', 'MC Branch', 'SG Branch', 'CBI China']), 'bu4'] = 'WBG'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and deal_subtype starts with '018:IM CORE' then BU4 = 'Wealth Mgt'
        df.loc[pbg_mask & (deal_subtype.str.startswith(
            '018:IM CORE')), 'bu4'] = 'Wealth Mgt'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and BU2 = 'Private Banking' then BU4 = 'Private Banking'
        df.loc[pbg_mask & (bu2 == 'Private Banking'),
               'bu4'] = 'Private Banking'

        # if BU4 in ('PBG-BB', 'PBG-Non-BB') and deal_subtype = '018:ALS:MSI' then BU4 = 'Private Banking'
        df.loc[pbg_mask & (deal_subtype == '018:ALS:MSI'),
               'bu4'] = 'Private Banking'

        # Final override: if BU4 = 'PBG-BB' then BU4 = 'BB - SME'
        df.loc[df['bu4'] == 'PBG-BB', 'bu4'] = 'BB - SME'

        return df

    def _profit_centre_1(self, df):
        """
        Add profit_centre_1 column: convert profit_centre to string and remove .0 suffix.
        See _add_cols_docs.FUNCTION_DOCS['_profit_centre_1'] for detailed logic.
        """
        if 'profit_centre' in df.columns:
            df['profit_centre_1'] = df['profit_centre'].astype(
                str).str.replace('.0', '')
        return df

    def _coa_prod_gp1(self, df):
        """
        Add coa_prod_gp1 column based on business rules.
        See _add_cols_docs.FUNCTION_DOCS['_coa_prod_gp1'] for detailed logic.
        """
        required_cols = ['deal_id', 'coa_mapping',
                         'entity1', 'profit_centre_1']
        if not all(col in df.columns for col in required_cols):
            return df

        df['coa_prod_gp1'] = np.where(
            df['deal_id'] == 'JETCO:001',
            'FVOCI_1304',
            np.where(
                (df['coa_mapping'].isin(['FVOCI', 'MM'])) & (
                    df['entity1'] == 'CNCBI'),
                df['coa_mapping'] + '_' + df['profit_centre_1'].astype(str),
                np.where(
                    df['coa_mapping'] == 'FVOCI',
                    'FVOCI_5851',
                    df['coa_mapping']
                )
            )
        )
        return df

    def _product1(self, df):
        """
        Add product1 column based on business rules.
        Includes ACCT_ID_BS extraction and PORT determination.
        See _add_cols_docs.FUNCTION_DOCS['_product1'] for detailed logic.
        """
        required_cols = ['deal_id', 'product', 'entity']
        if not all(col in df.columns for col in required_cols):
            return df

        # Prepare data
        deal_id_str = df['deal_id'].astype(str)
        entity_str = df['entity'].astype(str)
        product_str = df['product'].astype(str)

        # Extract ACCT_ID_BS using helper function
        acct_id_bs = self._extract_acct_id_bs(df, deal_id_str, entity_str)

        # Determine PORT using vectorized operations
        port = self._determine_port(product_str, acct_id_bs)

        # Calculate product1
        product1 = product_str.copy()
        # Special case: deal_id = '018:USER UPLOAD:BD1'
        product1 = np.where(
            deal_id_str == '018:USER UPLOAD:BD1', 'Bonds_P2', product1)
        # If product = 'Bonds' and PORT is determined
        product1 = np.where((product_str == 'Bonds') & (
            port != ''), 'Bonds_' + port, product1)

        df['product1'] = product1
        return df

    def _ceo1(self, df):
        """
        Add ceo1 column based on product1.
        Maps product1 to CEO1 categories: 'Loan' or 'Treasury'.
        See _add_cols_docs.FUNCTION_DOCS['_ceo1'] for detailed logic.
        """
        if 'product1' not in df.columns:
            return df

        product1 = df['product1'].astype(str)

        # Initialize ceo1 column
        df['ceo1'] = ''

        # if Product_1 in ('Loans', 'Off-balance', 'Other Account') then CEO1 = 'Loan'
        loan_products = ['Loans', 'Off-balance', 'Other Account']
        loan_mask = product1.isin(loan_products)
        df.loc[loan_mask, 'ceo1'] = 'Loan'

        # if Product_1 in ('Bonds_P1', 'Bonds_P2', 'Placement') then CEO1 = 'Treasury'
        treasury_products = ['Bonds_P1', 'Bonds_P2', 'Placement']
        treasury_mask = product1.isin(treasury_products)
        df.loc[treasury_mask, 'ceo1'] = 'Treasury'

        return df

    def _ceo2(self, df):
        """
        Add ceo2 column based on ceo1, coa_entity, bu1, entity1, and coa_prod_gp1.
        Has two paths: CEO1+COA_ENTITY+BU1, and ENTITY1 (overrides path 1).
        See _add_cols_docs.FUNCTION_DOCS['_ceo2'] for detailed logic.
        """
        # Check required columns
        if 'ceo1' not in df.columns:
            return df

        # Get required fields
        ceo1 = df['ceo1'].astype(str)
        coa_entity = df['coa_entity'].astype(
            str) if 'coa_entity' in df.columns else pd.Series('', index=df.index)
        bu1 = df['bu1'].astype(
            str) if 'bu1' in df.columns else pd.Series('', index=df.index)
        entity1 = df['entity1'].astype(
            str) if 'entity1' in df.columns else pd.Series('', index=df.index)
        coa_prod_gp1 = df['coa_prod_gp1'].astype(
            str) if 'coa_prod_gp1' in df.columns else pd.Series('', index=df.index)

        # Initialize ceo2 column
        df['ceo2'] = ''

        # Path 1: CEO1 + COA_ENTITY + BU1 -> CEO2
        # if CEO1 = 'Treasury' then do;
        treasury_mask = ceo1 == 'Treasury'
        if treasury_mask.any():
            # if COA_ENTITY in ('LA Branch') then CEO2 = '     LA'
            df.loc[treasury_mask & (
                coa_entity == 'LA Branch'), 'ceo2'] = '     LA'

            # if COA_ENTITY in ('NY Branch') then CEO2 = '     NY'
            df.loc[treasury_mask & (
                coa_entity == 'NY Branch'), 'ceo2'] = '     NY'

            # if COA_ENTITY in ('MC Branch') then CEO2 = 'Macau'
            df.loc[treasury_mask & (
                coa_entity == 'MC Branch'), 'ceo2'] = 'Macau'

            # if COA_ENTITY in ('SG Branch') then CEO2 = 'Singapore'
            df.loc[treasury_mask & (
                coa_entity == 'SG Branch'), 'ceo2'] = 'Singapore'

            # if COA_ENTITY in ('CBI China', 'CBIC_Shenzhen_WBG', 'CBIC_Beijing_WBG', 'CBIC_Shanghai_WBG') then CEO2 = 'CBIC'
            cbi_china_treasury = ['CBI China', 'CBIC_Shenzhen_WBG',
                                  'CBIC_Beijing_WBG', 'CBIC_Shanghai_WBG']
            df.loc[treasury_mask & coa_entity.isin(
                cbi_china_treasury), 'ceo2'] = 'CBIC'

            # if COA_ENTITY in ('CNCBI', 'HKCBF', 'Viewcon') then CEO2 = 'CNCBI'
            cncbi_treasury = ['CNCBI', 'HKCBF', 'Viewcon']
            df.loc[treasury_mask & coa_entity.isin(
                cncbi_treasury), 'ceo2'] = 'CNCBI'

        # if CEO1 = 'Loan' then do;
        loan_mask = ceo1 == 'Loan'
        if loan_mask.any():
            # if COA_ENTITY in ('LA Branch') then CEO2 = '     LA'
            df.loc[loan_mask & (coa_entity == 'LA Branch'), 'ceo2'] = '     LA'

            # if COA_ENTITY in ('NY Branch') then CEO2 = '     NY'
            df.loc[loan_mask & (coa_entity == 'NY Branch'), 'ceo2'] = '     NY'

            # if COA_ENTITY in ('MC Branch') then CEO2 = 'Macau'
            df.loc[loan_mask & (coa_entity == 'MC Branch'), 'ceo2'] = 'Macau'

            # if COA_ENTITY in ('SG Branch') then CEO2 = 'Singapore'
            df.loc[loan_mask & (coa_entity == 'SG Branch'),
                   'ceo2'] = 'Singapore'

            # if COA_ENTITY in ('CBI China') then CEO2 = 'CBIC'
            df.loc[loan_mask & (coa_entity == 'CBI China'), 'ceo2'] = 'CBIC'

            # if COA_ENTITY in ('CNCBI', 'CNCBI_RAM', 'CNCBI_WBG') then CEO2 = 'HK_WBG'
            hk_wbg_loan = ['CNCBI', 'CNCBI_RAM', 'CNCBI_WBG']
            df.loc[loan_mask & coa_entity.isin(hk_wbg_loan), 'ceo2'] = 'HK_WBG'

            # if COA_ENTITY in ('HKCBF') then CEO2 = 'HK_PBG_nonBB'
            df.loc[loan_mask & (coa_entity == 'HKCBF'),
                   'ceo2'] = 'HK_PBG_nonBB'

            # if COA_ENTITY in ('CBIC_Beijing_PBG', 'CBIC_Shanghai_PBG', 'CBIC_Shenzhen_PBG') then CEO2 = 'CBI China_PBD'
            cbi_china_pbd = ['CBIC_Beijing_PBG',
                             'CBIC_Shanghai_PBG', 'CBIC_Shenzhen_PBG']
            df.loc[loan_mask & coa_entity.isin(
                cbi_china_pbd), 'ceo2'] = 'CBI China_PBD'

            # if COA_ENTITY in ('CBIC_Beijing_WBG', 'CBIC_Shanghai_WBG', 'CBIC_Shenzhen_WBG') then CEO2 = 'CBI China_WBD'
            cbi_china_wbd = ['CBIC_Beijing_WBG',
                             'CBIC_Shanghai_WBG', 'CBIC_Shenzhen_WBG']
            df.loc[loan_mask & coa_entity.isin(
                cbi_china_wbd), 'ceo2'] = 'CBI China_WBD'

            # if COA_ENTITY in ('CNCBI_PBG') and BU1 = 'PBG-BB' then CEO2 = 'HK_PBG_BB'
            df.loc[loan_mask & (coa_entity == 'CNCBI_PBG') & (
                bu1 == 'PBG-BB'), 'ceo2'] = 'HK_PBG_BB'

            # if COA_ENTITY in ('CNCBI_PBG') and BU1 = 'PBG-Non-BB' then CEO2 = 'HK_PBG_nonBB'
            df.loc[loan_mask & (coa_entity == 'CNCBI_PBG') & (
                bu1 == 'PBG-Non-BB'), 'ceo2'] = 'HK_PBG_nonBB'

            # if COA_PROD_GP = 'LOA-Card' then CEO2 = 'HK_PBG_nonBB'
            df.loc[loan_mask & (coa_prod_gp1 == 'LOA-Card'),
                   'ceo2'] = 'HK_PBG_nonBB'

        # Path 2: ENTITY1 -> CEO2 (overrides path 1)
        # if ENTITY1 = 'CBI China' then CEO2 = 'CBI China_WBD'
        df.loc[entity1 == 'CBI China', 'ceo2'] = 'CBI China_WBD'

        # if ENTITY1 = 'CBI China' and BU1 = 'PBG-BB' then CEO2 = 'CBI China_PBD'
        df.loc[(entity1 == 'CBI China') & (bu1 == 'PBG-BB'),
               'ceo2'] = 'CBI China_PBD'

        # if ENTITY1 = 'CNCBI' and BU1 in ('WBG', 'RAM') then CEO2 = 'HK_WBG'
        df.loc[(entity1 == 'CNCBI') & bu1.isin(['WBG', 'RAM']),
               'ceo2'] = 'HK_WBG'

        # if ENTITY1 = 'CNCBI' and BU1 = 'PBG-BB' then CEO2 = 'HK_PBG_BB'
        df.loc[(entity1 == 'CNCBI') & (bu1 == 'PBG-BB'),
               'ceo2'] = 'HK_PBG_BB'

        # if ENTITY1 = 'CNCBI' and BU1 = 'PBG-Non-BB' then CEO2 = 'HK_PBG_nonBB'
        df.loc[(entity1 == 'CNCBI') & (bu1 == 'PBG-Non-BB'),
               'ceo2'] = 'HK_PBG_nonBB'

        # if ENTITY1 = 'LA Branch' then CEO2 = '     LA'
        df.loc[entity1 == 'LA Branch', 'ceo2'] = '     LA'

        # if ENTITY1 = 'NY Branch' then CEO2 = '     NY'
        df.loc[entity1 == 'NY Branch', 'ceo2'] = '     NY'

        # if ENTITY1 = 'SG Branch' then CEO2 = 'Singapore'
        df.loc[entity1 == 'SG Branch', 'ceo2'] = 'Singapore'

        # if ENTITY1 = 'MC Branch' then CEO2 = 'Macau'
        df.loc[entity1 == 'MC Branch', 'ceo2'] = 'Macau'

        # if ENTITY1 = 'HKCBF' then CEO2 = 'HK_PBG_nonBB'
        df.loc[entity1 == 'HKCBF', 'ceo2'] = 'HK_PBG_nonBB'

        return df

    def _extract_acct_id_bs(self, df, deal_id_str, entity_str):
        """
        Extract ACCT_ID_BS from deal_id based on multiple business rules.
        This is a helper function used by _product1().
        See _add_cols_docs.FUNCTION_DOCS['_extract_acct_id_bs'] for detailed logic.
        """
        # Split deal_id by ':'
        deal_id_parts = deal_id_str.str.split(':', expand=True)
        num_parts = deal_id_parts.shape[1] if deal_id_parts.shape[1] > 0 else 0

        # Helper function to safely get part as Series
        def get_part(idx):
            if num_parts > idx:
                return pd.Series(deal_id_parts[idx], index=df.index).fillna('').astype(str)
            return pd.Series('', index=df.index)

        # Extract parts
        deal_id_1st = get_part(0)
        deal_id_2nd = get_part(1)
        deal_id_3rd = get_part(
            2) if num_parts >= 3 else pd.Series('', index=df.index)
        deal_id_4th = get_part(
            3) if num_parts >= 4 else pd.Series('', index=df.index)

        # Get deal_subtype 3rd part if available
        if 'deal_subtype' in df.columns and num_parts > 0:
            deal_subtype_parts = df['deal_subtype'].astype(
                str).str.split(':', expand=True)
            deal_subtype_3rd = pd.Series(deal_subtype_parts[2], index=df.index).fillna('').astype(
                str) if deal_subtype_parts.shape[1] > 2 else pd.Series('', index=df.index)
        else:
            deal_subtype_3rd = pd.Series('', index=df.index)

        # Default: second part
        acct_id_bs = deal_id_2nd.copy()

        # Build conditions and values for np.select (order matters - more specific first)
        conditions = []
        choices = []

        # ELS: concatenate parts 2, 3, 4
        if num_parts >= 4:
            els_mask = deal_id_1st == 'ELS'
            els_value = (get_part(1) + get_part(2) + get_part(3)).astype(str)
            conditions.append(els_mask)
            choices.append(els_value)

        # TR + Bond + 5851: part2 + 'CTU_P1_' + part4 + '_008'
        if num_parts >= 4:
            tr_bond_5851_mask = (deal_id_1st == 'TR') & (
                deal_subtype_3rd == 'Bond') & (deal_id_3rd == '5851')
            tr_bond_5851_value = deal_id_2nd + 'CTU_P1_' + deal_id_4th + '_008'
            conditions.append(tr_bond_5851_mask)
            choices.append(tr_bond_5851_value)

        # TR + Bond + 5852: part2 + 'CTU_P2_' + part4 + '_008'
        if num_parts >= 4:
            tr_bond_5852_mask = (deal_id_1st == 'TR') & (
                deal_subtype_3rd == 'Bond') & (deal_id_3rd == '5852')
            tr_bond_5852_value = deal_id_2nd + 'CTU_P2_' + deal_id_4th + '_008'
            conditions.append(tr_bond_5852_mask)
            choices.append(tr_bond_5852_value)

        # TR + CALL: 'CALL_' + part2 + '_USD'
        if 'deal_subtype' in df.columns:
            tr_call_mask = (deal_id_1st == 'TR') & (deal_subtype_3rd == 'CALL')
            tr_call_value = 'CALL_' + deal_id_2nd + '_USD'
            conditions.append(tr_call_mask)
            choices.append(tr_call_value)

        # 083* + EIBS + NOS: substr(deal_id, 9, 8)
        eibs_083_nos_mask = entity_str.str.startswith('083') & (
            deal_id_1st == 'EIBS') & (deal_id_2nd.str[:3] == 'NOS')
        eibs_083_nos_value = deal_id_str.str[8:16]
        conditions.append(eibs_083_nos_mask)
        choices.append(eibs_083_nos_value)

        # 083NY + EIBS: part2
        eibs_083ny_mask = (entity_str == '083NY') & (deal_id_1st == 'EIBS')
        conditions.append(eibs_083ny_mask)
        choices.append(deal_id_2nd)

        # 084 + TAIBS + NOS: substr(deal_id, 10, 7)
        taibs_084_nos_mask = (entity_str == '084') & (
            deal_id_1st == 'TAIBS') & (deal_id_2nd.str[:3] == 'NOS')
        taibs_084_nos_value = deal_id_str.str[9:16]
        conditions.append(taibs_084_nos_mask)
        choices.append(taibs_084_nos_value)

        # 801 + TAIBS + NOS: substr(deal_id, 10)
        taibs_801_nos_mask = (entity_str == '801') & (
            deal_id_1st == 'TAIBS') & (deal_id_2nd.str[:3] == 'NOS')
        taibs_801_nos_value = deal_id_str.str[9:]
        conditions.append(taibs_801_nos_mask)
        choices.append(taibs_801_nos_value)

        # IMEX: concatenate parts 2-7
        if num_parts >= 7:
            imex_mask = deal_id_1st == 'IMEX'
            imex_parts = [get_part(i) for i in range(1, 7)]
            imex_value = (imex_parts[0] + imex_parts[1] + imex_parts[2] +
                          imex_parts[3] + imex_parts[4] + imex_parts[5]).astype(str)
            conditions.append(imex_mask)
            choices.append(imex_value)

        # Apply all conditions using np.select (evaluates in order, first match wins)
        if conditions:
            acct_id_bs = np.select(conditions, choices, default=acct_id_bs)
            # Ensure it's a Series after np.select
            if not isinstance(acct_id_bs, pd.Series):
                acct_id_bs = pd.Series(acct_id_bs, index=df.index)

        # customer_nr special case (applied after all other conditions)
        if 'customer_nr' in df.columns:
            customer_nr_mask = (df['customer_nr'].astype(
                str) == '084:USER UPLOAD:AMCM') & (acct_id_bs == '')
            customer_nr_value = deal_id_str.str[0:1]
            acct_id_bs = np.where(
                customer_nr_mask, customer_nr_value, acct_id_bs)
            # Ensure it's a Series after np.where
            if not isinstance(acct_id_bs, pd.Series):
                acct_id_bs = pd.Series(acct_id_bs, index=df.index)

        return acct_id_bs.fillna('').astype(str)

    def _determine_port(self, product_str, acct_id_bs):
        """
        Determine PORT based on product and ACCT_ID_BS.
        This is a helper function used by _product1().
        See _add_cols_docs.FUNCTION_DOCS['_determine_port'] for detailed logic.
        """
        port = pd.Series('', index=product_str.index, dtype=str)

        # Build conditions and values
        conditions = [
            product_str == 'TTFIBON',
            acct_id_bs.str.contains('_P1_', na=False),
            acct_id_bs.str.contains('_P2_', na=False)
        ]
        choices = ['P1', 'P1', 'P2']

        port = np.select(conditions, choices, default=port)
        return port
