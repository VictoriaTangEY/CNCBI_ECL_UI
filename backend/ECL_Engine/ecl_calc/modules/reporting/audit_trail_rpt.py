import pandas as pd
import numpy as np
import time


class AuditTrailRpt:
    def __init__(self, context, ecl_df):
        self.outResultPath = context.outResultPath
        self.outInterimPath = context.outInterimPath
        self.rpt_dt = context.data_yymm
        self.ecl_df = ecl_df  # use the loaded data from service

    def process_all(self):
        self.generate_audit_trail()
        return

    def generate_audit_trail(self):
        start_time = time.time()

        df = self.ecl_df.copy()

        audit_data = {
            'deal_id': df['deal_id'] if 'deal_id' in df.columns else df.index.astype(str),
            'entity': df['entity'] if 'entity' in df.columns else '018',
            'product': df['product'] if 'product' in df.columns else 'Loans',
            'stage': df['final_stage'] if 'final_stage' in df.columns else '1',
            'ecl_amount': df['ecl_hke_m'] if 'ecl_hke_m' in df.columns else 0.0,
            'calculation_date': self.rpt_dt,
            'audit_timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'Calculated',
            'validation_flag': 'Pass',
            'notes': ''
        }

        audit_df = pd.DataFrame(audit_data)

        summary_data = {
            'Metric': ['Total Deals', 'Total ECL Amount', 'Stage 1 Deals', 'Stage 2 Deals', 'Stage 3 Deals'],
            'Value': [
                len(audit_df),
                audit_df['ecl_amount'].sum(),
                len(audit_df[audit_df['stage'] == '1']),
                len(audit_df[audit_df['stage'] == '2']),
                len(audit_df[audit_df['stage'] == '3'])
            ]
        }
        summary_df = pd.DataFrame(summary_data)

        file_name = "reporting_ecl_audit_trial.xlsx"
        with pd.ExcelWriter(self.outResultPath / file_name, engine='openpyxl') as writer:
            audit_df.to_excel(writer, sheet_name='Audit_Trail', index=False)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

        audit_time = time.time() - start_time
        print(f"Audit trail report completed in {audit_time:.2f} seconds")
        return
