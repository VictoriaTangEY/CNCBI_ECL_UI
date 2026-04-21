"""
Documentation for _add_cols.py functions.
Contains detailed pseudo-code logic for each function.
"""

# Documentation dictionary mapping function names to their detailed logic
FUNCTION_DOCS = {
    '_elim': """
    Add elimination column based on intercompany field.
    
    Pseudo-code logic:
    1. Check if 'intercompany' column exists in dataframe
    2. If exists:
       - if intercompany == '000' then elim = 1
       - else elim = 0
    3. Return dataframe with elim column added
    """,

    '_c800': """
    Add c800 column using vectorized operations.
    
    Pseudo-code logic:
    1. Check if 'deal_type' column exists and 'chart_of_accounts_param' exists in param
    2. Build mapping dictionary from chart_of_accounts_param:
       - For each row in chart_of_accounts_param:
         - Extract 'child value low', 'child value high', and 'c800'
         - Convert low and high to float
         - Create mapping: (low, high) -> c800
    3. Validate deal_type:
       - Skip if deal_type == 'UNDRWN' (case insensitive)
       - Skip if deal_type cannot be converted to float
    4. For each valid deal_type:
       - Find the range (low, high) that contains deal_type
       - Assign corresponding c800 value
    5. Return dataframe with c800 column added
    """,

    '_product': """
    Add product column using vectorized operations.
    
    Pseudo-code logic:
    1. Check if 'c800' column exists and 'c800_product_param' exists in param
    2. Create mapping dictionary from c800_product_param:
       - Map c800 -> product
    3. Apply mapping to c800 column to get product
    4. Special patch:
       - if deal_type == 'UNDRAWN' (case insensitive) then product = 'OFF-balance'
    5. Return dataframe with product column added
    """,

    '_interco_cd': """
    Add interco_cd column using vectorized operations.
    
    Pseudo-code logic:
    1. Check if 'interco_cd_param' exists in param
    2. Define condition fields: ['entity', 'cust_id', 'remarks', 'resd_country_cd', 'country_of_risk']
    3. Filter to only fields that exist in both dataframe and interco_cd_param
    4. Create composite key for both dataframes:
       - For each row, join all condition field values with '_'
       - Fill NaN with empty string before joining
    5. Merge dataframes on composite key to get interco_cd
    6. Return dataframe with interco_cd column added
    """,

    '_class': """
    Add class column based on product.
    
    Pseudo-code logic:
    1. Check if 'product' column exists in dataframe
    2. If exists:
       - if product == 'Loans' then class = 'Loans'
       - else class = 'Non-loans'
    3. Return dataframe with class column added
    """,

    '_stage': """
    Add stage column based on final_stage.
    
    Pseudo-code logic:
    1. Check if 'final_stage' column exists in dataframe
    2. If exists:
       - stage = 'Stage ' + trim(final_stage)
       - Remove leading/trailing whitespace from final_stage before concatenation
    3. Return dataframe with stage column added
    """,

    '_entity1': """
    Add entity1 column based on entity mapping.
    
    Pseudo-code logic:
    1. Extract entity field from dataframe
    2. Handle entity conversion:
       - Convert to string
       - If entity is purely numeric and <= 3 digits, zero-pad to 3 digits (e.g., '18' -> '018')
       - Preserve alphanumeric entities as-is (e.g., '083LA', '083NY')
    3. Perform prefix match comparison:
       - if entity starts with '018' then entity1 = 'CNCBI'
       - else if entity starts with '019' then entity1 = 'HKCBF'
       - else if entity starts with '023' then entity1 = 'Viewcon'
       - else if entity starts with '084' then entity1 = 'MC Branch'
       - else if entity starts with '090' then entity1 = 'SG Branch'
       - else if entity starts with '801' then entity1 = 'CBI China'
       - else if entity starts with '083LA' then entity1 = 'LA Branch'
       - else if entity starts with '083NY' then entity1 = 'NY Branch'
       - else entity1 = '' (empty string)
    4. Return dataframe with entity1 column added
    """,

    '_entity2': """
    Add entity2 column based on entity1 mapping.
    
    Pseudo-code logic:
    1. Extract entity1 field from dataframe (must be created by _entity1 first)
    2. Set default value: entity2 = 'CNCBI'
    3. Override if entity1 == 'HKCBF': entity2 = 'HKCBF'
    4. Override if entity1 == 'CBI China': entity2 = 'CBI China'
    5. Return dataframe with entity2 column added
    
    Note: This function depends on entity1 column existing in the dataframe.
    """,

    '_coa_entity': """
    Add coa_entity column based on entity1, location, cust_bk_group, product, and bu.
    
    Pseudo-code logic:
    1. Prepare derived fields:
       - LOCATION_F = LOCATION
       - CUST_BK_GROUP_F = CUST_BK_GROUP
       - BU_F = BU
    
    2. Set default value: coa_entity = entity1
    
    3. Apply conditional overrides (in order):
       - if LOCATION_F = 'Shanghai' and CUST_BK_GROUP_F = '1' then coa_entity = 'CBIC_Shanghai_PBG'
       - else if LOCATION_F = 'Shanghai' and CUST_BK_GROUP_F != '1' then coa_entity = 'CBIC_Shanghai_WBG'
       - else if LOCATION_F = 'Shenzhen' and CUST_BK_GROUP_F = '1' then coa_entity = 'CBIC_Shenzhen_PBG'
       - else if LOCATION_F = 'Shenzhen' and CUST_BK_GROUP_F != '1' then coa_entity = 'CBIC_Shenzhen_WBG'
       - else if LOCATION_F = 'Beijing' and CUST_BK_GROUP_F = '1' then coa_entity = 'CBIC_Beijing_PBG'
       - else if LOCATION_F = 'Beijing' and CUST_BK_GROUP_F != '1' then coa_entity = 'CBIC_Beijing_WBG'
    
    4. Apply additional overrides:
       - if entity1 = 'CBI China' and LOCATION_F = '' then coa_entity = 'CBIC_Shenzhen_WBG'
       - if product = 'Loans' and entity1 = 'CNCBI' and BU_F starts with 'PBG' then coa_entity = 'CNCBI_PBG'
       - if product = 'Loans' and entity1 = 'CNCBI' and coa_entity != 'CNCBI_PBG' then coa_entity = 'CNCBI_WBG'
    
    5. Return dataframe with coa_entity column added
    
    Note: This function depends on entity1 and product columns existing in the dataframe.
    """,

    '_bu1': """
    Add bu1 column based on coa_entity and product.
    
    Pseudo-code logic:
    1. Prepare derived field: COA_ENTITY_F = COA_ENTITY
    
    2. Initialize bu1 column (default empty or NaN)
    
    3. If Product = 'Loans', then apply the following conditions (independent if statements):
       - if COA_ENTITY_F in ('HKCBF', 'CNCBI_PBG_nonBB', 'Viewcon') then BU1 = 'PBG-Non-BB'
       - if COA_ENTITY_F in ('CBIC_Beijing_PBG', 'CBIC_Shanghai_PBG', 'CBIC_Shenzhen_PBG', 'CNCBI_PBG_BB') then BU1 = 'PBG-BB'
       - if COA_ENTITY_F in ('CNCBI_WBG', 'LA Branch', 'MC Branch', 'NY Branch', 'CBIC_Beijing_WBG', 
                             'CBIC_Shenzhen_WBG', 'CBIC_Shanghai_WBG', 'SG Branch') then BU1 = 'WBG'
       - if COA_ENTITY_F in ('CNCBI_RAM') then BU1 = 'RAM'
    
    4. Return dataframe with bu1 column added
    
    Note: This function depends on coa_entity and product columns existing in the dataframe.
    """,

    '_bu_off2': """
    Add bu_off2 column based on bu_off, cust_bk_group, and mcm3.
    
    Pseudo-code logic:
    1. Set default value: bu_off2 = bu_off
    
    2. Apply conditional overrides (independent if statements):
       - if CUST_BK_GROUP = '1' then bu_off2 = 'PBG-Non-BB'
       - if CUST_BK_GROUP in ('2', 'R') then bu_off2 = 'PBG-BB'
       - if CUST_BK_GROUP = '4' then bu_off2 = 'WBG'
       - if MCM3 = 'Credit Card' then bu_off2 = 'PBG-Non-BB'
    
    3. Return dataframe with bu_off2 column added
    """,

    '_bu2': """
    Add bu2 column based on bu1, bus_unit, coa_entity, deal_tfi_id, account_officer, and deal_subtype.
    
    Pseudo-code logic:
    1. Set default value: bu2 = bu1
    
    2. Apply conditional overrides (independent if statements, order matters):
       - if BU1 = 'PBG-Non-BB' and (BUS_UNIT = 'MB' or COA_ENTITY_F = 'HKCBF') then BU2 = 'Mortgage & HKCBF'
       - if BU1 = 'PBG-Non-BB' and BU2 = 'PBG-Non-BB' and COA_ENTITY_F = 'HKCBF' then BU2 = 'Mortgage & HKCBF'
       - if BU1 = 'PBG-Non-BB' and BUS_UNIT in ('CUCL', 'WM') then BU2 = 'Wealth Mgt & CF'
       - if BU1 = 'PBG-Non-BB' and BU2 = 'PBG-Non-BB' and deal_tfi_id starts with 'CARDLINK' then BU2 = 'Wealth Mgt & CF'
       - if BU1 = 'PBG-Non-BB' and (BUS_UNIT in ('PB') or ACCOUNT_OFFICER starts with 'R8') then BU2 = 'Private Banking'
       - if BU1 = 'PBG-Non-BB' and BUS_UNIT in ('STAFF') then BU2 = 'Own Fund'
       - if BU1 = 'PBG-Non-BB' and BU2 = 'PBG-Non-BB' and deal_subtype = '018:ALS:MSI' then BU2 = 'Mortgage & HKCBF'
       - if BU1 = 'PBG-Non-BB' and BU2 = 'PBG-Non-BB' and deal_subtype starts with '018:IM CORE' then BU2 = 'Wealth Mgt & CF'
    
    3. Return dataframe with bu2 column added
    
    Note: deal_tfi_id = deal_id
    """,

    '_bu3': """
    Add bu3 column based on multiple conditions from entity1, product_1, bu1, entity, bu_off2, coa_prod_gp1, and bu4.
    
    Pseudo-code logic:
    1. Initialize bu3 column (default empty)
    
    2. Path 1: ENTITY1 + PRODUCT_1 + BU1 -> BU3
       - Set default: bu3 = bu2
       - if ENTITY1 = 'CNCBI' and BU2 = 'WBG' then BU3 = 'WBGHK'
       - if ENTITY1 = 'CBI China' and BU2 = 'PBG-BB' then BU3 = 'CBI China PBD'
       - if ENTITY1 = 'CBI China' and BU2 = 'WBG' then BU3 = 'CBI China WBD'
       - if ENTITY1 = 'MC Branch' then BU3 = 'Macau'
       - if ENTITY1 = 'SG Branch' then BU3 = 'SG'
       - if ENTITY1 = 'LA Branch' then BU3 = 'US (LA)'
       - if ENTITY1 = 'NY Branch' then BU3 = 'US (NY)'
       - if Product_1 = 'Other Account' and BU1 = 'RAM' then BU3 = 'WBGHK'
    
    3. Path 2: ENTITY + BU_OFF2 -> BU3 (overrides path 1)
       - if MCM3 in ('Credit Card') or BU_OFF2 = 'PBG-Non-BB' then BU3 = 'Wealth Mgt & CF'
       - if ENTITY = 'CNCBI' and BU_OFF2 = 'WBG' then BU3 = 'WBGHK'
       - if ENTITY = 'CNCBI' and BU_OFF2 = 'PBG-BB' then BU3 = 'PBG-BB'
       - if ENTITY in ('SG Branch') then BU3 = 'SG'
       - if ENTITY in ('MC Branch') then BU3 = 'Macau'
       - if ENTITY in ('LA Branch') then BU3 = 'US (LA)'
       - if ENTITY in ('NY Branch') then BU3 = 'US (NY)'
       - if ENTITY in ('CBI China') and BU_OFF = 'WBG' then BU3 = 'CBI China WBD'
       - if ENTITY in ('CBI China') and BU_OFF = 'PBG' then BU3 = 'CBI China PBD'
    
    4. Special conditions based on COA_PROD_GP1 + Product_1 + ENTITY1 + BU3 + BU4:
       - if COA_PROD_GP1 = 'LOA' and Product_1 = 'Loans' and ENTITY1 = 'CBI China' and BU1 = ' ' and BU3 = ' ' and BU4 = ' ' then:
         BU1 = 'WBG', BU3 = 'CBI China WBD', BU4 = 'WBG', CEO2 = 'CBI China_WBD'
       - if COA_PROD_GP1 = 'Fin Gua' and Product_1 = 'Off-balance' and ENTITY1 = 'CBI China' and BU1 = ' ' and BU3 = ' ' and BU4 = ' ' then:
         BU1 = 'WBG', BU3 = 'CBI China WBD', BU4 = 'WBG', CEO2 = 'CBI China_WBD'
       - if COA_PROD_GP1 = 'LOA Com+Fact' and Product_1 = 'Off-balance' and ENTITY1 = 'CNCBI' and BU1 = ' ' and BU3 = ' ' and BU4 = ' ' 
         and C800 in ('Forward Contract-MM Loan', 'Forward Contract-Reverse Repo') then:
         BU1 = 'TMG', BU3 = 'TMG', BU4 = 'TMG'
    
    5. Return dataframe with bu3 column added
    """,

    '_profit_centre_1': """
    Add profit_centre_1 column based on profit_centre.
    
    Pseudo-code logic:
    1. Check if 'profit_centre' column exists in dataframe
    2. If exists:
       - Convert profit_centre to string
       - Remove '.0' suffix (e.g., '5851.0' -> '5851')
       - profit_centre_1 = profit_centre (with .0 removed)
    3. Return dataframe with profit_centre_1 column added
    """,

    '_coa_prod_gp1': """
    Add coa_prod_gp1 column based on business rules.
    
    Pseudo-code logic:
    1. Check required columns: ['deal_id', 'coa_mapping', 'entity1', 'profit_centre_1']
    2. Apply nested conditions:
       - IF deal_id == 'JETCO:001' THEN coa_prod_gp1 = 'FVOCI_1304'
       - ELSE IF (coa_mapping in ['FVOCI', 'MM'] AND entity1 == 'CNCBI') THEN 
         coa_prod_gp1 = coa_mapping + '_' + profit_centre_1
       - ELSE IF coa_mapping == 'FVOCI' THEN coa_prod_gp1 = 'FVOCI_5851'
       - ELSE coa_prod_gp1 = coa_mapping
    3. Return dataframe with coa_prod_gp1 column added
    """,

    '_product1': """
    Add product1 column based on business rules.
    
    Pseudo-code logic:
    1. Check required columns: ['deal_id', 'product', 'entity']
    2. Set default: product1 = product
    3. Extract ACCT_ID_BS from deal_id using _extract_acct_id_bs():
       - Default: ACCT_ID_BS = second part of deal_id (split by ':')
       - Multiple special cases based on entity, deal_id prefix, and deal_subtype
       - See _extract_acct_id_bs() for detailed extraction rules
    4. Determine PORT using _determine_port():
       - If product == 'TTFIBON' then PORT = 'P1'
       - Else if ACCT_ID_BS contains '_P1_' then PORT = 'P1'
       - Else if ACCT_ID_BS contains '_P2_' then PORT = 'P2'
       - Else PORT = '' (empty)
    5. Apply special cases:
       - If deal_id == '018:USER UPLOAD:BD1' then product1 = 'Bonds_P2'
       - Else if (product == 'Bonds' AND PORT != '') then product1 = 'Bonds_' + PORT
       - Else product1 = product (default)
    6. Return dataframe with product1 column added
    
    Helper functions:
    - _extract_acct_id_bs(): Extracts ACCT_ID_BS from deal_id with multiple business rules
    - _determine_port(): Determines PORT based on product and ACCT_ID_BS
    """,

    '_extract_acct_id_bs': """
    Extract ACCT_ID_BS from deal_id based on multiple business rules.
    This is a helper function used by _product1().
    
    Pseudo-code logic:
    1. Split deal_id by ':' to get parts
    2. Extract deal_id parts: part1, part2, part3, part4 (if available)
    3. Extract deal_subtype 3rd part if available
    4. Set default: ACCT_ID_BS = part2
    5. Apply special conditions in order (first match wins):
       - ELS: if part1 == 'ELS' and num_parts >= 4, then ACCT_ID_BS = parts[2] + parts[3] + parts[4]
       - TR + Bond + 5851: if part1 == 'TR' and deal_subtype_3rd == 'Bond' and part3 == '5851',
         then ACCT_ID_BS = part2 + 'CTU_P1_' + part4 + '_008'
       - TR + Bond + 5852: if part1 == 'TR' and deal_subtype_3rd == 'Bond' and part3 == '5852',
         then ACCT_ID_BS = part2 + 'CTU_P2_' + part4 + '_008'
       - TR + CALL: if part1 == 'TR' and deal_subtype_3rd == 'CALL',
         then ACCT_ID_BS = 'CALL_' + part2 + '_USD'
       - 083* + EIBS + NOS: if entity starts with '083' and part1 == 'EIBS' and part2[:3] == 'NOS',
         then ACCT_ID_BS = substr(deal_id, 9, 8)
       - 083NY + EIBS: if entity == '083NY' and part1 == 'EIBS', then ACCT_ID_BS = part2
       - 084 + TAIBS + NOS: if entity == '084' and part1 == 'TAIBS' and part2[:3] == 'NOS',
         then ACCT_ID_BS = substr(deal_id, 10, 7)
       - 801 + TAIBS + NOS: if entity == '801' and part1 == 'TAIBS' and part2[:3] == 'NOS',
         then ACCT_ID_BS = substr(deal_id, 10)
       - IMEX: if part1 == 'IMEX' and num_parts >= 7,
         then ACCT_ID_BS = parts[2] + parts[3] + ... + parts[7]
    6. Special case: if customer_nr == '084:USER UPLOAD:AMCM' and ACCT_ID_BS == '',
       then ACCT_ID_BS = substr(deal_id, 0, 1)
    7. Return ACCT_ID_BS (filled with empty string if NaN)
    """,

    '_determine_port': """
    Determine PORT based on product and ACCT_ID_BS.
    This is a helper function used by _product1().
    
    Pseudo-code logic:
    1. Initialize PORT = '' (empty string)
    2. Apply conditions in order:
       - If product == 'TTFIBON' then PORT = 'P1'
       - Else if ACCT_ID_BS contains '_P1_' then PORT = 'P1'
       - Else if ACCT_ID_BS contains '_P2_' then PORT = 'P2'
       - Else PORT = '' (default)
    3. Return PORT
    """,

    '_ceo1': """
    Add ceo1 column based on product1.
    
    Pseudo-code logic:
    1. Check if 'product1' column exists in dataframe (must be created by _product1 first)
    2. Initialize ceo1 column (default empty string)
    3. Apply conditional mappings (independent if statements):
       - if Product_1 in ('Loans', 'Off-balance', 'Other Account') then CEO1 = 'Loan'
       - if Product_1 in ('Bonds_P1', 'Bonds_P2', 'Placement') then CEO1 = 'Treasury'
    4. Return dataframe with ceo1 column added
    
    Note: Product_1 = product1 (already prepared in _product1 function)
    """,

    '_ceo2': """
    Add ceo2 column based on ceo1, coa_entity, bu1, entity1, and coa_prod_gp1.
    
    Pseudo-code logic:
    1. Check if 'ceo1' column exists in dataframe (must be created by _ceo1 first)
    2. Initialize ceo2 column (default empty string)
    
    3. Path 1: CEO1 + COA_ENTITY + BU1 -> CEO2
       - if CEO1 = 'Treasury' then do:
         * if COA_ENTITY in ('LA Branch') then CEO2 = '     LA'
         * if COA_ENTITY in ('NY Branch') then CEO2 = '     NY'
         * if COA_ENTITY in ('MC Branch') then CEO2 = 'Macau'
         * if COA_ENTITY in ('SG Branch') then CEO2 = 'Singapore'
         * if COA_ENTITY in ('CBI China', 'CBIC_Shenzhen_WBG', 'CBIC_Beijing_WBG', 'CBIC_Shanghai_WBG') then CEO2 = 'CBIC'
         * if COA_ENTITY in ('CNCBI', 'HKCBF', 'Viewcon') then CEO2 = 'CNCBI'
       
       - if CEO1 = 'Loan' then do:
         * if COA_ENTITY in ('LA Branch') then CEO2 = '     LA'
         * if COA_ENTITY in ('NY Branch') then CEO2 = '     NY'
         * if COA_ENTITY in ('MC Branch') then CEO2 = 'Macau'
         * if COA_ENTITY in ('SG Branch') then CEO2 = 'Singapore'
         * if COA_ENTITY in ('CBI China') then CEO2 = 'CBIC'
         * if COA_ENTITY in ('CNCBI', 'CNCBI_RAM', 'CNCBI_WBG') then CEO2 = 'HK_WBG'
         * if COA_ENTITY in ('HKCBF') then CEO2 = 'HK_PBG_nonBB'
         * if COA_ENTITY in ('CBIC_Beijing_PBG', 'CBIC_Shanghai_PBG', 'CBIC_Shenzhen_PBG') then CEO2 = 'CBI China_PBD'
         * if COA_ENTITY in ('CBIC_Beijing_WBG', 'CBIC_Shanghai_WBG', 'CBIC_Shenzhen_WBG') then CEO2 = 'CBI China_WBD'
         * if COA_ENTITY in ('CNCBI_PBG') and BU1 = 'PBG-BB' then CEO2 = 'HK_PBG_BB'
         * if COA_ENTITY in ('CNCBI_PBG') and BU1 = 'PBG-Non-BB' then CEO2 = 'HK_PBG_nonBB'
         * if COA_PROD_GP = 'LOA-Card' then CEO2 = 'HK_PBG_nonBB'
    
    4. Path 2: ENTITY1 -> CEO2 (overrides path 1)
       - if ENTITY1 = 'CBI China' then CEO2 = 'CBI China_WBD'
       - if ENTITY1 = 'CBI China' and BU1 = 'PBG-BB' then CEO2 = 'CBI China_PBD'
       - if ENTITY1 = 'CNCBI' and BU1 in ('WBG', 'RAM') then CEO2 = 'HK_WBG'
       - if ENTITY1 = 'CNCBI' and BU1 = 'PBG-BB' then CEO2 = 'HK_PBG_BB'
       - if ENTITY1 = 'CNCBI' and BU1 = 'PBG-Non-BB' then CEO2 = 'HK_PBG_nonBB'
       - if ENTITY1 = 'LA Branch' then CEO2 = '     LA'
       - if ENTITY1 = 'NY Branch' then CEO2 = '     NY'
       - if ENTITY1 = 'SG Branch' then CEO2 = 'Singapore'
       - if ENTITY1 = 'MC Branch' then CEO2 = 'Macau'
       - if ENTITY1 = 'HKCBF' then CEO2 = 'HK_PBG_nonBB'
    
    5. Return dataframe with ceo2 column added
    
    Note: COA_PROD_GP = coa_prod_gp1 (already prepared in _coa_prod_gp1 function)
    """,

    '_bu4': """
    Add bu4 column based on bu1, bus_unit, coa_entity, c800, and deal_subtype.
    
    Pseudo-code logic:
    1. Set default value: bu4 = bu1
    
    2. Apply conditional overrides (independent if statements, order matters):
       All conditions require: BU4 in ('PBG-BB', 'PBG-Non-BB')
       
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and COA_ENTITY_F = 'HKCBF' then BU4 = 'HKCBF'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'AUTO' then BU4 = 'Auto Finance'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'BAS' and C800 != 'Instalment Loans' then BU4 = 'BB - BAS'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'BAS' and C800 = 'Instalment Loans' then BU4 = 'Shared BAS'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'CUCL' and C800 != 'Advance to Cardholders' then BU4 = 'UCL'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'CUCL' and C800 = 'Advance to Cardholders' then BU4 = 'Credit Card'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'M&E' then BU4 = 'M&E Finance'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'MB' then BU4 = 'Mortgage'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'PB' then BU4 = 'Private Banking'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'SME' then BU4 = 'BB - SME'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'STAFF' then BU4 = 'Staff Loans - Own Fund'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BUS_UNIT = 'WM' then BU4 = 'Wealth Mgt'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and C800 = 'Advance to Cardholders' then BU4 = 'Credit Card'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and C800 = 'Personal Instalment Loan' then BU4 = 'UCL'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and COA_ENTITY in ('LA Branch', 'NY Branch', 'MC Branch', 'SG Branch', 'CBI China') then BU4 = 'WBG'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and deal_subtype starts with '018:IM CORE' then BU4 = 'Wealth Mgt'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and BU2 = 'Private Banking' then BU4 = 'Private Banking'
       - if BU4 in ('PBG-BB', 'PBG-Non-BB') and deal_subtype = '018:ALS:MSI' then BU4 = 'Private Banking'
    
    3. Final override:
       - if BU4 = 'PBG-BB' then BU4 = 'BB - SME'
    
    4. Return dataframe with bu4 column added
    
    Note: COA_ENTITY_F = COA_ENTITY (already prepared in _coa_entity function)
    """
}
