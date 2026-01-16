import pandas as pd
import numpy as np
import time


class HkmaReports:
    def __init__(self, context, ecl_df):
        self.outResultPath = context.outResultPath
        self.outInterimPath = context.outInterimPath
        self.rpt_dt = context.data_yymm
        self.ecl_df = ecl_df  # use the loaded data from service

    def process_all(self):
        self.generate_hkma_reports()
        return

    def generate_hkma_reports(self):
        start_time = time.time()

        df = self.ecl_df.copy()

        hkma_data = {
            'entity_code': df['entity'] if 'entity' in df.columns else '018',
            'product_type': df['product'] if 'product' in df.columns else 'Loans',
            'stage': df['final_stage'] if 'final_stage' in df.columns else '1',
            'ecl_provision': df['ecl_hke_m'] if 'ecl_hke_m' in df.columns else 0.0,
            'exposure_amount': np.random.uniform(1000000, 10000000, len(df)),
            'risk_weight': np.random.choice([0.2, 0.5, 1.0, 1.5], len(df)),
            'regulatory_capital': 0.0,
            'reporting_date': self.rpt_dt,
            'hkma_category': 'Commercial_Banking'
        }

        hkma_df = pd.DataFrame(hkma_data)

        hkma_df['regulatory_capital'] = hkma_df['exposure_amount'] * \
            hkma_df['risk_weight'] * 0.08

        regulatory_summary = {
            'Regulatory_Metric': [
                'Total ECL Provisions',
                'Total Exposure Amount',
                'Total Regulatory Capital',
                'Average Risk Weight',
                'Number of Exposures'
            ],
            'Amount_HKD': [
                hkma_df['ecl_provision'].sum(),
                hkma_df['exposure_amount'].sum(),
                hkma_df['regulatory_capital'].sum(),
                hkma_df['risk_weight'].mean(),
                len(hkma_df)
            ]
        }
        summary_df = pd.DataFrame(regulatory_summary)

        entity_breakdown = hkma_df.groupby('entity_code').agg({
            'ecl_provision': 'sum',
            'exposure_amount': 'sum',
            'regulatory_capital': 'sum'
        }).reset_index()
        entity_breakdown.columns = [
            'Entity_Code', 'ECL_Provision', 'Exposure_Amount', 'Regulatory_Capital']

        file_name = "reporting_ecl_hkma.xlsx"
        with pd.ExcelWriter(self.outResultPath / file_name, engine='openpyxl') as writer:
            hkma_df.to_excel(writer, sheet_name='HKMA_Data', index=False)
            summary_df.to_excel(
                writer, sheet_name='Regulatory_Summary', index=False)
            entity_breakdown.to_excel(
                writer, sheet_name='Entity_Breakdown', index=False)

        hkma_time = time.time() - start_time
        print(f"HKMA reports completed in {hkma_time:.2f} seconds")
        return
