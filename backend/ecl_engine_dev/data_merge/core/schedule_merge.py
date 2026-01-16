import os
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime
from utils.loggers import createLogHandler
from data_merge.core.merge_checking import check_required_files


class BSDataMergeFramework:
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
        self.logger = createLogHandler("ScheduleMerge", str(log_file))
        self.data_dir = self.config["merge_input_dir"]
        self.output_dir = self.config["merge_output_dir"]
        os.makedirs(self.output_dir, exist_ok=True)
        self.required_columns = self.config["output_columns_schedule"]
        self.calculated_columns = self.config["calculation_columns_schedule"]
        self.regions = self.config["regions"]
        self.files = {}
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

    def run(self):
        self.logger.info("=== Starting BS data merge process ===")

        # Step 1: Data checking and loading
        self.files, _ = check_required_files(
            self.logger, self.data_dir, self.config, merge_type="bs")

        # Step 2: Process bill schedule files by region
        self.process_bill_schedule_files()

        # Step 3: Save output
        self.save_output()

        self.logger.info("=== BS data merge process completed ===")

    def process_bill_schedule_files(self):
        """Process bill schedule files by adding REGION_BRCH column and concatenating"""
        self.logger.info("=== Processing bill schedule files ===")
        bill_sched_dfs = []
        for region in self.regions:
            key = f"{region}_bill_sched"
            if key in self.files:
                df = self.files[key].copy()
                # Add REGION_BRCH column with the region value
                df["REGION_BRCH"] = region
                bill_sched_dfs.append(df)

                self.logger.info(
                    f"Processed bill schedule for {region} with {len(df)} rows")

        if bill_sched_dfs:
            # Concatenate all bill schedule files
            self.merged_df = pd.concat(bill_sched_dfs, ignore_index=True)
            self.logger.info(
                f"=== Created merged bill schedule dataset with {len(self.merged_df)} rows ===")
        else:
            self.logger.error("No bill schedule dataset found to process")

    def save_output(self):
        """Save the final output"""
        self.logger.info("=== Saving output ===")

        if self.merged_df is None:
            self.logger.error("Merged dataset not initialized")
            return

        # Add PRODUCT_TYPE_BRCH column
        self.merged_df["PRODUCT_TYPE_BRCH"] = "BILL_SCHEDULE"

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
        output_path = os.path.join(self.output_dir, "schedule_table.csv")
        output_df.to_csv(output_path, index=False)

        self.logger.info(f"=== Saved output to {output_path} ")
        self.logger.info(
            f"Output has {len(output_df)} rows and {len(output_columns)} columns")

        # Generate a detailed column report
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