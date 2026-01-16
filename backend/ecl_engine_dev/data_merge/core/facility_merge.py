import os
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime
from utils.loggers import createLogHandler
from data_merge.core.merge_checking import check_required_files


class FacDataMergeFramework:
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
        self.logger = createLogHandler("FacilityMerge", str(log_file))
        
        self.data_dir = self.config["merge_input_dir"]
        self.output_dir = self.config["merge_output_dir"]
        os.makedirs(self.output_dir, exist_ok=True)
        self.required_columns = self.config["output_columns_facility"]
        self.calculated_columns = self.config["calculation_columns_facility"]
        self.regions = self.config["regions"]
        self.files = {}
        self.fac_df = None
        self.fac_seg_df = None
        self.merged_df = None

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
            left_df[key_column] = left_df[key_column].astype(str)
            right_df[key_column] = right_df[key_column].astype(str)
        return left_df, right_df

    def run(self):
        """Run facility data merge process"""
        self.logger.info("=== Starting facility data merge process ===")

        # Step 1: Find and load all files
        self.files, _ = check_required_files(
            self.logger, self.data_dir, self.config, merge_type="fac")

        # Step 2: Concatenate fac files by region
        self.concatenate_fac_files()

        # Step 3: Concatenate fac_seg files by region
        self.concatenate_fac_seg_files()

        # Step 4: Merge fac_seg with fac by region
        self.merge_fac_seg_with_fac()

        # Step 5: Merge exchange rate
        self.merge_exchange_rate()

        # Step 6: Save output
        self.save_output()

        self.logger.info("=== Facility data merge process completed ===")

    def concatenate_fac_files(self):
        """Concatenate fac files from all regions"""
        self.logger.info("=== Concatenating fac files ===")

        fac_dfs = []

        for region in self.regions:
            key = f"{region}_fac"

            if key in self.files:
                df = self.files[key].copy()
                df["REGION_BRCH"] = region
                fac_dfs.append(df)
                self.logger.info(
                    f"Added fac data for {region} with {len(df)} rows")

        if fac_dfs:
            self.fac_df = pd.concat(fac_dfs, ignore_index=True)
            self.logger.info(
                f"=== Created fac table with {len(self.fac_df)} rows ===")
        else:
            self.logger.error("No fac files found to concatenate")

    def concatenate_fac_seg_files(self):
        """Concatenate fac_seg files from all regions"""
        self.logger.info("=== Concatenating fac_seg files ===")

        fac_seg_dfs = []

        for region in self.regions:
            key = f"{region}_fac_seg"

            if key in self.files:
                df = self.files[key].copy()
                df["REGION_BRCH"] = region
                fac_seg_dfs.append(df)
                self.logger.info(
                    f"Added fac_seg data for {region} with {len(df)} rows")

        if fac_seg_dfs:
            self.fac_seg_df = pd.concat(fac_seg_dfs, ignore_index=True)
            self.logger.info(
                f"=== Created fac_seg table with {len(self.fac_seg_df)} rows ===")
        else:
            self.logger.warning("No fac_seg files found to concatenate")

    def merge_fac_seg_with_fac(self):
        """Merge fac_seg with fac by region using left join"""
        self.logger.info("=== Merging fac_seg with fac ===")

        if self.fac_seg_df is None and self.fac_df is None:
            self.logger.error("Neither fac_seg nor fac tables initialized")
            return

        # If no fac_seg data, use fac data as the result
        if self.fac_seg_df is None:
            self.merged_df = self.fac_df.copy()
            self.merged_df["PRODUCT_TYPE_BRCH"] = "FACILITY"
            self.logger.info("No fac_seg data, using fac data only")
            return

        # If no fac data, use fac_seg data as the result
        if self.fac_df is None:
            self.merged_df = self.fac_seg_df.copy()
            self.merged_df["PRODUCT_TYPE_BRCH"] = "FACILITY"
            self.logger.info("No fac data, using fac_seg data only")
            return

        # Get join key from config
        join_key = self.config["merge_join_key"]["facility"]

        merged_dfs = []

        # Process by region
        for region in self.regions:
            # Get region-specific data
            region_fac_seg = self.fac_seg_df[self.fac_seg_df["REGION_BRCH"] == region].copy(
            )
            region_fac = self.fac_df[self.fac_df["REGION_BRCH"]
                                     == region].copy()

            if region_fac_seg.empty and region_fac.empty:
                continue

            if region_fac_seg.empty:
                # Only fac data for this region
                region_fac["PRODUCT_TYPE_BRCH"] = "FACILITY"
                merged_dfs.append(region_fac)
                continue

            if region_fac.empty:
                # Only fac_seg data for this region
                region_fac_seg["PRODUCT_TYPE_BRCH"] = "FACILITY"
                merged_dfs.append(region_fac_seg)
                continue

            # Both exist, perform left join
            region_fac_seg, region_fac = self.ensure_key_type_match(
                region_fac_seg, region_fac, join_key)

            # Get original columns
            left_columns_before = set(region_fac_seg.columns)

            # Left join fac_seg with fac
            merged = pd.merge(
                region_fac_seg,
                region_fac,
                on=[join_key, "REGION_BRCH"],
                how="left",
                suffixes=("", "_right")
            )

            # Remove duplicate columns
            cols_to_drop = []
            for col in merged.columns:
                if col.endswith("_right"):
                    base_col = col[:-6]
                    if base_col not in left_columns_before or region_fac_seg[base_col].isna().all():
                        merged[base_col] = merged[col]
                    cols_to_drop.append(col)

            merged = merged.drop(columns=cols_to_drop)
            merged["PRODUCT_TYPE_BRCH"] = "FACILITY"

            merged_dfs.append(merged)
            self.logger.info(f"Merged fac_seg with fac for {region}")

        if merged_dfs:
            self.merged_df = pd.concat(merged_dfs, ignore_index=True)
            self.logger.info(
                f"=== Created merged facility data with {len(self.merged_df)} rows ===")
        else:
            self.logger.error("No data after merging")

    def merge_exchange_rate(self):
        """Merge exchange rate files"""
        self.logger.info("=== Merging exchange rate files ===")

        if self.merged_df is None:
            self.logger.error("=== Merged table not initialized ===")
            return

        # Get exchange rate join configuration
        exchange_rate_config = self.config["merge_join_key"]["exchange_rate"]
        left_key = exchange_rate_config["left_key"]      # CURRENCY
        right_key = exchange_rate_config["right_key"]    # FROM_CURRENCY
        # Use direct product name for exchange rate
        exchange_rate_file_id = "exch_rate"

        # Load HK exchange rate table for LCY_TO_HKD calculation
        hk_exch_df = None
        hk_exch_key = f"hk_{exchange_rate_file_id}"  # Use lowercase hk

        if hk_exch_key in self.files:
            hk_exch_df = self.files[hk_exch_key].copy()
            self.logger.info(
                f"Found HK exchange rate table with key: {hk_exch_key}, {len(hk_exch_df)} rows")
            if right_key in hk_exch_df.columns:
                hk_exch_df[right_key] = hk_exch_df[right_key].astype(str)
            hk_exch_df = hk_exch_df.drop_duplicates(subset=[right_key])
        else:
            self.logger.warning(
                f"HK exchange rate table not found: {hk_exch_key}")

        merged_dfs = []

        # Process by region
        for region in self.regions:
            region_df = self.merged_df[self.merged_df["REGION_BRCH"] == region].copy(
            )

            if region_df.empty:
                continue

            # Create key using product name
            key = f"{region}_{exchange_rate_file_id}"

            if key in self.files:
                # Get the right table
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

                    # Add LCY_TO_HKD from HK exchange rate table using TO_CURRENCY
                    if hk_exch_df is not None and "TO_CURRENCY" in merged.columns:
                        # Ensure TO_CURRENCY has matching data type
                        merged["TO_CURRENCY"] = merged["TO_CURRENCY"].astype(
                            str)
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
            self.merged_df = pd.concat(merged_dfs, ignore_index=True)
            self.logger.info("=== Completed exchange rate merge ===")

    def save_output(self):
        """Save the final output"""
        self.logger.info("=== Saving output ===")

        if self.merged_df is None:
            self.logger.error("Merged table not initialized")
            return

        # Create a list of all expected output columns
        output_columns = ["REGION_BRCH", "PRODUCT_TYPE_BRCH"]

        # Add all required columns from config
        for col in self.required_columns:
            if col not in output_columns:
                output_columns.append(col)

        # Ensure all required columns exist in the output
        columns_to_use = [
            col for col in output_columns if col in self.merged_df.columns]
        missing_columns = [
            col for col in output_columns if col not in self.merged_df.columns]

        # Create a copy of the dataframe for output
        output_df = self.merged_df[columns_to_use].copy()

        # Add missing columns with NA values
        for col in missing_columns:
            output_df[col] = pd.NA

        # Reorder columns to match output_columns order
        output_df = output_df[output_columns]

        # Save to output file
        output_path = os.path.join(self.output_dir, "facility_table.csv")
        output_df.to_csv(output_path, index=False)
        self.logger.info(f"=== Saved output to {output_path} ===")
        self.logger.info(
            f"Output has {len(output_df)} rows and {len(output_columns)} columns")

        # Generate column statistics
        column_stats = []
        for col in output_columns:
            non_null_count = output_df[col].count()
            total_count = len(output_df)
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