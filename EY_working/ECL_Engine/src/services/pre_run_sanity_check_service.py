import sys
from datetime import datetime
from modules.validation.pre_run_sanity_check import DataHealthCheck
from utils.loggers import createLogHandler


def run_sanity_chk(context):
    # Initialize logger
    logger = createLogHandler(
        'data_sanity_check', context.outLogPath/'Log_file_data_sanity_check.log')

    logger.info("="*60)
    logger.info("DATA SANITY CHECK - STARTED")
    logger.info("="*60)

    start_time = datetime.now()

    try:
        # Initialize environment settings

        # Load raw data files
        logger.info("Loading data files")

        # Create health check instance with raw data
        health_check = DataHealthCheck(context=context)

        logger.info("Running data health checks")
        report_path = health_check.run()

        # Summary
        execution_time = (datetime.now() - start_time).total_seconds()
        passed = sum(1 for r in health_check.results if r['Status'] == 'Pass')
        failed = sum(1 for r in health_check.results if r['Status'] == 'Fail')

        summary = {
            'Status': 'SUCCESS',
            'Total Checks': len(health_check.results),
            'Passed': passed,
            'Failed': failed,
            'Report Path': report_path,
            'Execution Time': f"{execution_time:.2f} seconds"
        }

        # Log summary
        logger.info("="*60)
        logger.info("EXECUTION SUMMARY")
        logger.info("="*60)
        for key, value in summary.items():
            logger.info(f"{key}: {value}")
        logger.info("="*60)

        sys.exit(0 if failed == 0 else 1)

    except Exception as e:
        logger.exception("Execution failed")
        sys.exit(1)

    finally:
        logger.info("="*60)
        logger.info("DATA SANITY CHECK - COMPLETED")
        logger.info("="*60)
