import sys
from datetime import datetime
from ecl_calc.modules.validation.pre_run_sanity_check import DataHealthCheck
from utils.loggers import createLogHandler

def run_sanity_chk(context):
    """Run pre-run data sanity check"""
    # Initialize logger
    logger = createLogHandler(
        'data_sanity_check', context.outLogPath/'Log_file_data_sanity_check.log')
    
    logger.info("="*60)
    logger.info("DATA SANITY CHECK - STARTED")
    logger.info("="*60)
    
    start_time = datetime.now()
    
    try:
        logger.info("Loading data files and initializing health check")
        
        # Create health check instance with context
        health_check = DataHealthCheck(context=context)
        
        logger.info("Running data health checks")
        report_path = health_check.run()
        
        # Calculate summary
        execution_time = (datetime.now() - start_time).total_seconds()
        passed = sum(1 for r in health_check.results if r['check_flg'] in ['Pass', 'GREEN'])
        failed = sum(1 for r in health_check.results if r['check_flg'] in ['Fail', 'RED'])
        
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
        
        # Don't exit with error code, just log results
        if failed > 0:
            logger.warning(f"Data sanity check completed with {failed} failures")
        else:
            logger.info("Data sanity check completed successfully")
            
    except Exception as e:
        logger.exception("Data sanity check execution failed")
        raise
    finally:
        logger.info("="*60)
        logger.info("DATA SANITY CHECK - COMPLETED")
        logger.info("="*60)