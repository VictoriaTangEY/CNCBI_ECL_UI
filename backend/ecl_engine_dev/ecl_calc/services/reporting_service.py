import pandas as pd
import time
from utils.loggers import createLogHandler
from ecl_calc.modules.reporting.ecl_monthly_rpt import EclMonthlyRpt
from ecl_calc.modules.reporting.gl_posting_rpt import GlPostingRpt
from ecl_calc.modules.reporting.hkma_reports import HkmaReports
from ecl_calc.modules.reporting.audit_trail_rpt import AuditTrailRpt


def load_ecl_result(context):
    """Load ECL result data from interim output file"""
    start_time = time.time()
    ecl_df = pd.read_csv(
        context.outInterimPath / "interim_output_ecl_by_deal.csv",
        encoding='utf-8-sig'
    )
    load_time = time.time() - start_time
    print(f"Data loading completed in {load_time:.2f} seconds")
    return ecl_df


def run_reporting(context):
    logger = createLogHandler(
        'reporting', context.outLogPath/'Log_file_reporting.log')
    logger.info('='*50)
    logger.info('Starting Reporting Process')
    logger.info('='*50)

    # 1.1 Load Data
    logger.info('1.1. Loading data')
    try:
        # Load ECL data once for all reporting classes
        ecl_df = load_ecl_result(context)

        # Initialize and run reporting classes with loaded data
        logger.info('1.2. Running GL Posting Report')
        gl_posting = GlPostingRpt(context, ecl_df)
        gl_posting.process_all()

        logger.info('1.3. Running ECL Monthly Report')
        ecl_monthly = EclMonthlyRpt(context, ecl_df)
        ecl_monthly.process_all()

        logger.info('1.4. Running HKMA Reports')
        hkma_reports = HkmaReports(context, ecl_df)
        hkma_reports.process_all()

        logger.info('1.5. Running Audit Trail Report')
        audit_trail = AuditTrailRpt(context, ecl_df)
        audit_trail.process_all()

        logger.info('\tAll reporting completed')
    except Exception as e:
        logger.exception("\tReporting failed")
        raise
