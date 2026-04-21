import os
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime
from utils.loggers import createLogHandler
from data_merge.core.merge_checking import check_required_files


class DataMergeFramework:
    def __init__(self, run_config_path, merge_config_path=None):
        # Load run config
        with open(run_config_path, "r", encoding="utf-8") as f:
            self.run_config = json.load(f)
        
        # Default merge config path if not provided
        if merge_config_path is None:
            merge_config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                '..', 'config', 'merge_config.json'
            )
        
        # Load merge config
        with open(merge_config_path, "r", encoding="utf-8") as f:
            merge_config = json.load(f)
        
        # Combine configs
        self.config = self.load_config(merge_config)
        
        # Setup logger
        output_path = Path(self.run_config['RUN_SETTING']['OUTPUT_PATH'])
        data_yymm = self.run_config['RUN_SETTING']['DATA_YYMM']
        timestamp_date = datetime.now().strftime("%Y%m%d")
        log_path = output_path / f"{data_yymm}_{timestamp_date}" / '01_log'
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / 'Log_file_data_merge.log'
        self.logger = createLogHandler("ExposureMerge", str(log_file))
        
        self.data_dir = self.config["merge_input_dir"]
        self.output_dir = self.config["merge_output_dir"]
        os.makedirs(self.output_dir, exist_ok=True)
        self.required_columns = self.config["output_columns_exposure"]
        self.calculated_columns = self.config["calculation_columns_exposure"]
        self.field_processing_rules = self.config["field_processing_rules"]
        self.regions = self.config["regions"]
        self.files = {}
        self.main_df = None

    def load_config(self, merge_config):
        config = merge_config.copy()
        
        # Get settings from run config
        merge_settings = self.run_config.get('MERGE_SETTING', {})
        reporting_date = str(self.run_config['RUN_SETTING']['DATA_YYMM'])
        
        # Add configurations from run_config
        config['parse_input_dir'] = merge_settings.get('PARSE_INPUT_DIR', '')
        config['parse_output_dir'] = merge_settings.get('PARSE_OUTPUT_DIR', '')
        config['merge_input_dir'] = merge_settings.get('MERGE_INPUT_DIR', '')
        config['merge_output_dir'] = self.run_config['RUN_SETTING']['DATA_PATH']
        config['reporting_date'] = reporting_date
        config['field_position_file'] = merge_settings.get('FIELD_POSITION_FILE', '')
        config['regions'] = merge_settings.get('REGIONS', [])
        
        # Replace {reporting_date} placeholder in paths
        for key, value in config.items():
            if isinstance(value, str) and '{reporting_date}' in value:
                config[key] = value.replace('{reporting_date}', reporting_date)

        return config

    def ensure_key_type_match(self, left_df, right_df, key_column):
        if key_column in left_df.columns and key_column in right_df.columns:
            # Convert to string type for matching
            left_df[key_column] = left_df[key_column].astype(str)
            right_df[key_column] = right_df[key_column].astype(str)

        return left_df, right_df

    def run(self):
        """Run data merge process"""
        self.logger.info("=== Starting exposure table merge process ===")

        # Step 1: Find and load all files
        self.files, _ = check_required_files(
            self.logger, self.data_dir, self.config, merge_type="cust")

        # Step 2: Preprocess data
        self.preprocess_data()

        # Step 3: Merge tr_fi_pos and tr_fi_tran files
        self.merge_tr_fi_files()

        # Step 4: Concatenate main tables
        self.concatenate_main_tables()

        # Step 5: Merge segmentation
        self.merge_segmentation()

        # Step 6: Merge customer
        self.merge_customer()

        # Step 8: Merge exchange rate
        self.merge_exchange_rate()

        # Step 9: Merge deal data
        self.merge_deal_data()

        # Step 11: Save output
        self.save_output()

        self.logger.info("=== Data merge process completed ===")

    def preprocess_data(self):
        """Preprocess the data"""
        self.logger.info("=== Preprocessing data ===")

        # Apply field processing rules
        if "set_value" in self.field_processing_rules:
            # For each target field to set values
            for field, values in self.field_processing_rules["set_value"].items():
                # For each product type that needs this field set
                for product, value in values.items():
                    # Apply to all regions for this product
                    for region in self.regions:
                        key = f"{region}_{product.lower()}"
                        if key in self.files and field in self.files[key].columns:
                            # Set the specified value for all rows in this product/region
                            self.files[key][field] = value
                            self.logger.info(
                                f"Set {field} to {value} for {key}")

        if "map_field" in self.field_processing_rules:
            # For each target field that needs to be mapped
            for target_field, mappings in self.field_processing_rules["map_field"].items():
                # For each product type with a mapping rule
                for product, source_field in mappings.items():
                    # Apply to all regions for this product
                    for region in self.regions:
                        key = f"{region}_{product.lower()}"
                        if key in self.files and source_field in self.files[key].columns:
                            # Map the source field to the target field
                            self.files[key][target_field] = self.files[key][source_field]
                            self.logger.info(
                                f"Mapped {source_field} to {target_field} for {key}")

    def merge_tr_fi_files(self):
        """Merge tr_fi_pos and tr_fi_tran files"""
        self.logger.info("=== Merging tr_fi_pos and tr_fi_tran files ===")

        # Get source files from merged_products config
        if "tr_fi" in self.config["exposure_merged_product"]:
            source_files = self.config["exposure_merged_product"]["tr_fi"]["source_files"]
            if len(source_files) != 2:
                self.logger.warning(
                    f"Expected 2 source files, got {len(source_files)}")
                return

            # Get join key from config
            join_key = self.config["merge_join_key"]["tr_fi"]

            # For each region, merge files
            for region in self.regions:
                left_key = f"{region}_{source_files[0]}"
                right_key = f"{region}_{source_files[1]}"

                if left_key in self.files and right_key in self.files:
                    left_df = self.files[left_key].copy()
                    right_df = self.files[right_key].copy()

                    # Get left columns before merge to know which are new
                    left_columns_before = set(left_df.columns)

                    # Ensure key columns have matching data types
                    left_df, right_df = self.ensure_key_type_match(
                        left_df, right_df, join_key)

                    # Deduplicate the right table's key
                    right_df = right_df.drop_duplicates(subset=[join_key])

                    # Merge left and right tables
                    merged_df = pd.merge(
                        left_df,
                        right_df,
                        on=join_key,
                        how="left",
                        suffixes=("", "_right")
                    )

                    # Remove duplicate columns and add new ones
                    cols_to_drop = []
                    for col in merged_df.columns:
                        if col.endswith("_right"):
                            base_col = col[:-6]  # Remove "_right" suffix
                            # Add column if it's new or if left column is all NA
                            if base_col not in left_columns_before or left_df[base_col].isna().all():
                                merged_df[base_col] = merged_df[col]
                            cols_to_drop.append(col)

                    merged_df = merged_df.drop(columns=cols_to_drop)

                    # Store the merged dataframe
                    new_key = f"{region}_tr_fi"
                    self.files[new_key] = merged_df
                    self.logger.info(f"Created merged file {new_key}")
                else:
                    self.logger.warning(
                        f"Could not merge tr_fi files for {region}, missing files")

    def concatenate_main_tables(self):
        """Concatenate main tables"""
        self.logger.info("=== Concatenating main tables ===")

        main_dfs = []

        # Get all product types (base products and merged products)
        all_products = self.config["exposure_product"].copy()
        all_products.extend(self.config["exposure_merged_product"].keys())

        for region in self.regions:
            for product in all_products:
                key = f"{region}_{product}"

                if key in self.files:
                    df = self.files[key].copy()

                    # Add REGION_BRCH and PRODUCT_TYPE_BRCH columns
                    df["REGION_BRCH"] = region
                    df["PRODUCT_TYPE_BRCH"] = product.upper()

                    main_dfs.append(df)
                else:
                    self.logger.warning(f"Main table not found: {key}")

        if main_dfs:
            # Concatenate all main tables
            self.main_df = pd.concat(main_dfs, ignore_index=True)
            self.logger.info(
                f"=== Created main table with {len(self.main_df)} rows ===")
        else:
            self.logger.error("No main tables found to concatenate")

    def merge_segmentation(self):
        """Merge segmentation files"""
        self.logger.info("=== Merging segmentation files ===")

        if self.main_df is None:
            self.logger.error("Main table not initialized")
            return

        # Get join keys from config
        join_config = self.config["merge_join_key"]["segmentation"]
        left_key = join_config["left_key"]
        right_key = join_config["right_key"]

        # Split main dataframe by product type
        product_dfs = {}
        for product, seg_file in self.config["exposure_segmentation_map"].items():
            product_dfs[product] = self.main_df[self.main_df["PRODUCT_TYPE_BRCH"].str.lower(
            ) == product]

        merged_dfs = []

        # Process each product group
        for product, df in product_dfs.items():
            if df.empty:
                continue

            seg_type = self.config["exposure_segmentation_map"][product]

            # Process by region
            for region in self.regions:
                region_df = df[df["REGION_BRCH"] == region].copy()

                if region_df.empty:
                    continue

                key = f"{region}_{seg_type}"

                if key in self.files:
                    # Get the right table and deduplicate the key
                    right_df = self.files[key].copy()

                    # Get original columns in left table
                    left_columns_before = set(region_df.columns)

                    # Ensure key columns have matching data types
                    if left_key in region_df.columns:
                        region_df[left_key] = region_df[left_key].astype(str)
                    if right_key in right_df.columns:
                        right_df[right_key] = right_df[right_key].astype(str)

                    # Deduplicate the right table's key
                    right_df = right_df.drop_duplicates(subset=[right_key])

                    # Merge
                    if left_key in region_df.columns and right_key in right_df.columns:
                        merged = pd.merge(
                            region_df,
                            right_df,
                            left_on=left_key,
                            right_on=right_key,
                            how="left",
                            suffixes=("", "_right")
                        )

                        # Remove duplicate columns and add new ones
                        cols_to_drop = []
                        for col in merged.columns:
                            if col.endswith("_right"):
                                base_col = col[:-6]  # Remove "_right" suffix
                                # Add column if it's new or if left column is all NA
                                if base_col not in left_columns_before or region_df[base_col].isna().all():
                                    merged[base_col] = merged[col]
                                cols_to_drop.append(col)

                        merged = merged.drop(columns=cols_to_drop)

                        merged_dfs.append(merged)
                    else:
                        merged_dfs.append(region_df)
                else:
                    merged_dfs.append(region_df)

        if merged_dfs:
            self.main_df = pd.concat(merged_dfs, ignore_index=True)
            self.logger.info("=== Completed segmentation merge ===")
        else:
            self.logger.warning("No data after segmentation merge")

    def merge_customer(self):
        """Merge customer files"""
        self.logger.info("=== Merging customer files ===")

        if self.main_df is None:
            self.logger.error("Main table not initialized")
            return

        # Get join key from config
        join_key = self.config["merge_join_key"]["customer"]
        # Use direct product name for customer
        customer_file_id = "cust"

        merged_dfs = []

        # Process by region
        for region in self.regions:
            region_df = self.main_df[self.main_df["REGION_BRCH"] == region].copy(
            )

            if region_df.empty:
                continue

            # Create key using product name
            key = f"{region}_{customer_file_id}"

            if key in self.files:
                # Get the right table and deduplicate the key
                right_df = self.files[key].copy()

                # Get original columns in left table
                left_columns_before = set(region_df.columns)

                # Ensure key columns have matching data types
                region_df, right_df = self.ensure_key_type_match(
                    region_df, right_df, join_key)

                # Deduplicate the right table's key
                right_df = right_df.drop_duplicates(subset=[join_key])

                # Merge
                if join_key in region_df.columns and join_key in right_df.columns:
                    merged = pd.merge(
                        region_df,
                        right_df,
                        on=join_key,
                        how="left",
                        suffixes=("", "_right")
                    )

                    # Remove duplicate columns and add new ones
                    cols_to_drop = []
                    for col in merged.columns:
                        if col.endswith("_right"):
                            base_col = col[:-6]  # Remove "_right" suffix
                            # Add column if it's new or if left column is all NA
                            if base_col not in left_columns_before or region_df[base_col].isna().all():
                                merged[base_col] = merged[col]
                            cols_to_drop.append(col)

                    merged = merged.drop(columns=cols_to_drop)

                    merged_dfs.append(merged)
                else:
                    merged_dfs.append(region_df)
            else:
                merged_dfs.append(region_df)

        if merged_dfs:
            self.main_df = pd.concat(merged_dfs, ignore_index=True)
            self.logger.info("=== Completed customer merge ===")
        else:
            self.logger.warning("No data after customer merge")

    def merge_exchange_rate(self):
        """Merge exchange rate files"""
        self.logger.info("=== Merging exchange rate files ===")

        if self.main_df is None:
            self.logger.error("=== Main table not initialized ===")
            return

        # Get exchange rate join configuration
        exchange_rate_config = self.config["merge_join_key"]["exchange_rate"]
        left_key = exchange_rate_config["left_key"]      # CURRENCY
        right_key = exchange_rate_config["right_key"]    # FROM_CURRENCY
        # Use direct product name for exchange rate
        exchange_rate_file_id = "exch_rate"

        merged_dfs = []

        # Load HK exchange rate table for LCY_TO_HKD calculation
        hk_exch_key = f"hk_{exchange_rate_file_id}"
        hk_exch_df = None
        if hk_exch_key in self.files:
            hk_exch_df = self.files[hk_exch_key].copy()
            self.logger.info(
                f"Loaded hk exchange rate table with {len(hk_exch_df)} rows")
            if right_key in hk_exch_df.columns:
                hk_exch_df[right_key] = hk_exch_df[right_key].astype(str)
            hk_exch_df = hk_exch_df.drop_duplicates(subset=[right_key])
        else:
            self.logger.warning(
                f"hk exchange rate table not found: {hk_exch_key}")

        # Process by region
        for region in self.regions:
            region_df = self.main_df[self.main_df["REGION_BRCH"] == region].copy(
            )

            if region_df.empty:
                continue

            # Create key using product name
            key = f"{region}_{exchange_rate_file_id}"

            if key in self.files:
                # Get the right table - no renaming
                right_df = self.files[key].copy()

                # Get original columns in left table
                left_columns_before = set(region_df.columns)

                # Ensure key columns have matching data types
                if left_key in region_df.columns:
                    region_df[left_key] = region_df[left_key].astype(str)
                if right_key in right_df.columns:
                    right_df[right_key] = right_df[right_key].astype(str)

                # Deduplicate the right table's key
                right_df = right_df.drop_duplicates(subset=[right_key])

                # Merge - using different keys for left and right
                if left_key in region_df.columns and right_key in right_df.columns:
                    merged = pd.merge(
                        region_df,
                        right_df,
                        left_on=left_key,
                        right_on=right_key,
                        how="left",
                        suffixes=("", "_right")
                    )

                    # Add LCY_TO_HKD from HK exchange rate table using TO_CURRENCY
                    if hk_exch_df is not None and "TO_CURRENCY" in merged.columns:
                        # Ensure TO_CURRENCY has matching data type
                        merged["TO_CURRENCY"] = merged["TO_CURRENCY"].astype(
                            str)
                        # Select only needed columns from HK table for merging
                        hk_rate_df = hk_exch_df[[right_key, "RATE"]].rename(
                            columns={"RATE": "LCY_TO_HKD"})
                        merged = pd.merge(
                            merged,
                            hk_rate_df,
                            left_on="TO_CURRENCY",
                            right_on=right_key,
                            how="left",
                            suffixes=("", "_hk")
                        )
                        # Remove duplicate FROM_CURRENCY_hk column if exists
                        if f"{right_key}_hk" in merged.columns:
                            merged = merged.drop(columns=[f"{right_key}_hk"])

                    # Remove duplicate columns but keep exchange rate specific columns
                    cols_to_drop = []
                    keep_cols = ["FROM_CURRENCY", "TO_CURRENCY",
                                 "RATE", "MULTIPLY_DIVIDE_IND", "LCY_TO_HKD"]

                    for col in merged.columns:
                        if col.endswith("_right"):
                            base_col = col[:-6]  # Remove "_right" suffix
                            # Keep exchange rate specific columns
                            if base_col not in keep_cols:
                                # Add column if it's new or if left column is all NA
                                if base_col not in left_columns_before or region_df[base_col].isna().all():
                                    merged[base_col] = merged[col]
                                cols_to_drop.append(col)
                            else:
                                # For keep_cols, remove _right suffix if base column doesn't exist
                                if base_col not in merged.columns:
                                    merged[base_col] = merged[col]
                                cols_to_drop.append(col)

                    merged = merged.drop(columns=cols_to_drop)

                    merged_dfs.append(merged)
                else:
                    merged_dfs.append(region_df)
            else:
                merged_dfs.append(region_df)

        if merged_dfs:
            self.main_df = pd.concat(merged_dfs, ignore_index=True)
            self.logger.info("=== Completed exchange rate merge ===")
        else:
            self.logger.warning("No data after exchange rate merge")

    def merge_deal_data(self):
        """Merge deal data files"""
        self.logger.info("=== Merging deal data files ===")

        if self.main_df is None:
            self.logger.error("Main table not initialized")
            return

        # Get join key from config
        join_key = self.config["merge_join_key"]["deal_type"]

        # Process deal_type - this is a global file without region
        key = "deal_type"
        if key in self.files:
            # Get the right table and deduplicate the key
            right_df = self.files[key].copy()

            # Get original columns in left table
            left_columns_before = set(self.main_df.columns)

            # Ensure key columns have matching data types
            self.main_df, right_df = self.ensure_key_type_match(
                self.main_df, right_df, join_key)

            # Deduplicate the right table's key
            right_df = right_df.drop_duplicates(subset=[join_key])

            # Merge with the main dataframe
            if join_key in self.main_df.columns and join_key in right_df.columns:
                merged_df = pd.merge(
                    self.main_df,
                    right_df,
                    on=join_key,
                    how="left",
                    suffixes=("", "_right")
                )

                # Remove duplicate columns and add new ones
                cols_to_drop = []
                for col in merged_df.columns:
                    if col.endswith("_right"):
                        base_col = col[:-6]  # Remove "_right" suffix
                        # Add column if it's new or if left column is all NA
                        if base_col not in left_columns_before or self.main_df[base_col].isna().all():
                            merged_df[base_col] = merged_df[col]
                        cols_to_drop.append(col)

                merged_df = merged_df.drop(columns=cols_to_drop)
                self.main_df = merged_df

    def save_output(self):
        """Save the final output"""
        self.logger.info("=== Saving output ===")

        if self.main_df is None:
            self.logger.error("Main table not initialized")
            return

        # Create a list of all expected output columns
        output_columns = ["REGION_BRCH", "PRODUCT_TYPE_BRCH"]

        # Add all required columns from config
        for col in self.required_columns:
            if col not in output_columns:
                output_columns.append(col)

        # Ensure all output columns are included in the desired order
        final_output_df = self.main_df[output_columns]

        # Save to output file
        output_path = os.path.join(self.output_dir, "exposure_table.csv")
        final_output_df.to_csv(output_path, index=False)
        self.logger.info(f"=== Saved output to {output_path} ===")
        self.logger.info(
            f"Output has {len(final_output_df)} rows and {len(output_columns)} columns")

        # Generate a detailed column report
        column_stats = []
        for col in output_columns:
            non_null_count = final_output_df[col].count()
            total_count = len(final_output_df)
            null_percentage = round(
                (1 - (non_null_count / total_count)) * 100, 2) if total_count > 0 else 0
            column_stats.append({
                "Column": col,
                "Non-null count": non_null_count,
                "Total rows": total_count,
                "Null percentage": f"{null_percentage}%"
            })

        # Log the detailed report
        self.logger.info(
            "========= Detailed column statistics report =========")
        for stats in column_stats:
            self.logger.info(
                f"Column: {stats['Column']} | Non-null: {stats['Non-null count']}/{stats['Total rows']} | Null %: {stats['Null percentage']}")