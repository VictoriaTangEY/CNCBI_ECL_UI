import sys
from datetime import datetime
from ecl_calc.modules.validation.post_run_sanity_check import PostDataHealthCheck
from utils.loggers import createLogHandler


def run_post_sanity_chk(context):
    """
    Run post-processing data health check

    Args:
        context: run_setting instance with configuration
    """
    # Initialize logger
    logger = createLogHandler(
        'post_data_sanity_check',
        context.outLogPath/'Log_file_post_data_sanity_check.log'
    )

    logger.info("="*60)
    logger.info("POST DATA SANITY CHECK - STARTED")
    logger.info("="*60)

    start_time = datetime.now()

    try:
        # Load raw data files
        logger.info("Loading post-check data files")

        # Create health check instance
        health_check = PostDataHealthCheck(context=context)

        logger.info("Running post data health checks")
        report_path = health_check.run()

        # Summary
        execution_time = (datetime.now() - start_time).total_seconds()
        passed = sum(
            1 for r in health_check.results if r['check_flg'] == 'Pass')
        failed = sum(
            1 for r in health_check.results if r['check_flg'] == 'Fail')

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

        if failed > 0:
            logger.warning(
                f"Data sanity check completed with {failed} failures")
        else:
            logger.info("Data sanity check completed successfully")

    except Exception as e:
        logger.exception("Post sanity check execution failed")
        raise
    finally:
        logger.info("="*60)
        logger.info("POST DATA SANITY CHECK - COMPLETED")
        logger.info("="*60)
