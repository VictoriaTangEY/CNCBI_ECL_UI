import pandas as pd
import numpy as np
from pathlib import Path
import time


class EclMonthlyRpt:
    def __init__(self, context, ecl_df):
        self.outResultPath = context.outResultPath
        self.outInterimPath = context.outInterimPath
        self.rpt_dt = context.data_yymm
        self.ecl_df = ecl_df  # use the loaded data from service

    def rpt_to_rmg(self):
        start_time = time.time()

        # Only copy if we need to modify columns, otherwise use original
        # For now, keeping the copy since there's a TODO for column selection
        ecl_to_rmg = self.ecl_df.copy()

        # TODO: to update the cols to keep
        # keep_cols = []
        # ecl_to_rmg = ecl_to_rmg[keep_cols]

        # save to Excel with optimized settings
        ecl_to_rmg.to_excel(
            self.outResultPath / "reporting_ecl_result_to_rmg.xlsx",
            index=False,
            engine='openpyxl'
        )

        rmg_time = time.time() - start_time
        print(f"RMG report completed in {rmg_time:.2f} seconds")
        return

    def rpt_to_imh(self):
        start_time = time.time()

        # Only select needed columns to reduce memory usage
        keep_cols = ['as_of_dt', 'entity', 'tfi_id', 'customer_nr', 'deal_subtype',
                     'elim', 'product', 'currency', 'final_stage', 'ecl_final_hke_m', 'acct_id']
        ecl_to_imh = self.ecl_df[keep_cols].copy()

        # TODO: may update in the output datatype formatting
        # Format entity column to ensure leading zeros (018, 019)
        ecl_to_imh['entity'] = ecl_to_imh['entity'].astype(str).str.zfill(3)

        # Format ECL_HKE to prevent scientific notation and ensure proper decimal places (vectorized for efficiency)
        ecl_to_imh['ecl_final_hke_m'] = pd.to_numeric(
            ecl_to_imh['ecl_final_hke_m'], errors='coerce').fillna(0).round(4).map('{:.4f}'.format)

        # Format ELIM to ensure it's a 2-character field
        ecl_to_imh['elim'] = ecl_to_imh['elim'].astype(str).str.zfill(2)

        # Format DATA_DT from yyyy-mm-dd to yyyymmdd
        ecl_to_imh['as_of_dt'] = pd.to_datetime(
            ecl_to_imh['as_of_dt']).dt.strftime('%Y%m%d')

        # rename cols
        ecl_to_imh.rename(
            columns={
                'as_of_dt': 'DATA_DT',
                'entity': 'ENTITY',
                'tfi_id': 'DEAL_TFI_ID',
                'customer_nr': 'CUSTOMER_NR',
                'deal_subtype': 'DEAL_SUBTYPE',
                'elim': 'ELIM',
                'product': 'PRODUCT_1',
                'currency': 'CURR_CD',
                'final_stage': 'STAGE',
                'ecl_final_hke_m': 'ECL_HKE',
                'acct_id': 'ACCT_ID',
            }, inplace=True)
        # format cols to uppercase
        ecl_to_imh.columns = ecl_to_imh.columns.str.upper()

        # Define fixed widths and types
        col_specs = [
            ("DATA_DT", 15, "CHAR"),
            ("ENTITY", 15, "CHAR"),
            ("DEAL_TFI_ID", 80, "CHAR"),
            ("CUSTOMER_NR", 80, "CHAR"),
            ("DEAL_SUBTYPE", 60, "CHAR"),
            ("ELIM", 2, "CHAR"),
            ("PRODUCT_1", 25, "CHAR"),
            ("CURR_CD", 3, "CHAR"),
            ("STAGE", 10, "CHAR"),
            ("ECL_HKE", 20, "CHAR"),
            ("ACCT_ID", 80, "CHAR"),
        ]
        col_names = [c[0] for c in col_specs]
        col_widths = [c[1] for c in col_specs]
        col_types = [c[2] for c in col_specs]

        # Ensure column order
        ecl_to_imh = ecl_to_imh[col_names]

        def format_fixed_width_row(row, widths):
            return ''.join(str(val)[:w].ljust(w) for val, w in zip(row, widths))

        def generate_dat_file(df, file_name):
            dat_path = self.outResultPath / f"{file_name}.dat"
            rowcount = len(df)

            # Pre-format all rows for better performance
            formatted_rows = []
            for row in df.itertuples(index=False, name=None):
                formatted_rows.append(format_fixed_width_row(row, col_widths))

            with open(dat_path, "w", encoding="utf-8") as f:
                # Header: rpt_dt in yyyymmdd
                f.write(f"{self.rpt_dt};\n")
                # Data rows: write all at once
                f.write('\n'.join(formatted_rows) + '\n')
                # Footer: @rowcount;
                f.write(f"{rowcount};\n")
            return

        def generate_ctl_file(df, file_name, table_name="TARGET_TABLE"):
            ctl_path = self.outResultPath / f"{file_name}.ctl"
            pos = 1
            with open(ctl_path, "w", encoding="utf-8") as f:
                f.write("LOAD DATA\n")
                f.write(f"INFILE '{file_name}.dat'\n")
                f.write(f"INTO TABLE {table_name}\n")
                f.write("APPEND\n")
                f.write("FIELDS\n")
                f.write("(\n")
                for i, (col, width, dtype) in enumerate(col_specs):
                    start = pos
                    end = pos + width - 1
                    comma = "," if i < len(col_specs) - 1 else ""

                    # Simple data type mapping for control file
                    if dtype == "DATE":
                        ctl_dtype = "DATE 'YYYYMMDD'"
                    elif dtype == "CHAR":
                        ctl_dtype = "CHAR"
                    elif dtype.startswith("NUMBER"):
                        ctl_dtype = "DECIMAL EXTERNAL"
                    else:
                        ctl_dtype = "CHAR"

                    f.write(f"  {col} POSITION({start}:{end}) {ctl_dtype}{comma}\n" if i < len(
                        col_specs) - 1 else f"  {col} POSITION({start}:{end}) {ctl_dtype}\n")
                    pos += width
                f.write(")\n")
            return

        file_base = "ecl_imh_basel_rwa_calc"
        generate_dat_file(ecl_to_imh, file_base)
        generate_ctl_file(ecl_to_imh, file_base)

        imh_time = time.time() - start_time
        print(f"IMH report completed in {imh_time:.2f} seconds")
        return

    def rpt_summary(self):
        start_time = time.time()

        # Use the original DataFrame instead of copying
        df = self.ecl_df

        # Optimize string operations by doing them once and storing
        bu_clean = df['bu'].astype(str).str.strip().str.upper()
        product_clean = df['product'].astype(str).str.strip().str.upper()
        stage_clean = df['final_stage'].astype(str).str.strip()

        # Create key more efficiently
        df['key'] = bu_clean + '_' + product_clean + '_' + stage_clean

        # aggregate using key to do sum
        ecl_columns = [
            col for col in df.columns if col.lower().startswith('ecl')]
        ecl_summary = df.groupby('key')[ecl_columns].sum().reset_index()

        # ungroup more efficiently
        key_parts = ecl_summary['key'].str.split('_', expand=True)
        ecl_summary['bu'] = key_parts[0]
        ecl_summary['product'] = key_parts[1]
        ecl_summary['final_stage'] = key_parts[2]

        keep_cols = ['bu', 'product', 'final_stage'] + ecl_columns
        ecl_summary = ecl_summary[keep_cols]

        # save to Excel with optimized settings
        ecl_summary.to_excel(
            self.outResultPath / "reporting_ecl_result_summary.xlsx",
            index=False,
            engine='openpyxl'
        )

        summary_time = time.time() - start_time
        print(f"Summary report completed in {summary_time:.2f} seconds")
        return

    def rpt_by_bu(self):
        start_time = time.time()

        df = self.ecl_df

        if "bu" not in df.columns:
            raise ValueError("Column 'bu' not found in ecl_df.")

        # Clean BU column once
        df['bu'] = df['bu'].astype(str).str.strip().str.upper()
        unique_bu = df["bu"].dropna().unique()
        print(unique_bu)

        # Use groupby to avoid multiple DataFrame copies
        for bu in unique_bu:
            bu_df = df[df["bu"] == bu]
            file_name = f"ecl_result_by_BU_{bu}.xlsx"
            bu_df.to_excel(
                self.outResultPath / file_name,
                index=False,
                engine='openpyxl'
            )

        bu_time = time.time() - start_time
        print(f"BU reports completed in {bu_time:.2f} seconds")
        return

    def process_all(self):
        total_start_time = time.time()

        print("=" * 50)
        print("Starting reporting process...")
        print("=" * 50)

        # self.rpt_summary()
        self.rpt_to_rmg()
        self.rpt_to_imh()
        self.rpt_by_bu()

        total_time = time.time() - total_start_time
        print("=" * 50)
        print(f"Total reporting process completed in {total_time:.2f} seconds")
        print("=" * 50)
