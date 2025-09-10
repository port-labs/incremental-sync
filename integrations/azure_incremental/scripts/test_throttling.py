import asyncio
import os
import sys
from pathlib import Path

from loguru import logger

# Add the parent directory ('src' sibling) to the Python path
# to allow importing from the 'src' module.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.main import main


async def run_throttling_test() -> None:
    """
    Runs the main sync function multiple times concurrently to test Azure throttling.
    """
    required_env_vars = [
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "AZURE_TENANT_ID",
        "PORT_WEBHOOK_INGEST_URL",
        "PORT_WEBHOOK_SECRET",
    ]

    if not all(os.getenv(var) for var in required_env_vars):
        logger.error(
            "Missing required environment variables. Please set them before running the test."
        )
        logger.error(f"Required: {', '.join(required_env_vars)}")
        return

    # Set SYNC_MODE to full to ensure queries are consistently run.
    os.environ["SYNC_MODE"] = "full"
    logger.info("Forcing SYNC_MODE=full for the test.")

    # Azure's throttling is around 15 requests in 5 seconds.
    # 20 concurrent runs should be sufficient to trigger it.
    concurrent_runs = 20

    logger.info(f"Starting {concurrent_runs} concurrent syncs to test throttling...")

    tasks = [main() for _ in range(concurrent_runs)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = 0
    failure_count = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Run {i + 1}/{concurrent_runs} failed: {result}")
            failure_count += 1
        else:
            logger.success(f"Run {i + 1}/{concurrent_runs} completed successfully.")
            success_count += 1

    logger.info("Throttling test finished.")
    logger.info(f"Successful runs: {success_count}")
    logger.info(f"Failed runs: {failure_count}")

    if failure_count > 0:
        logger.warning(
            "Some runs failed. Check logs for exceptions like 'AzureRequestThrottled'."
        )

    logger.success(
        "All runs completed. Check logs for 'Rate limit exceeded' or 'Azure API quota depleted' "
        "messages to confirm throttling was handled correctly."
    )


if __name__ == "__main__":
    # Configure logger for the test script
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    asyncio.run(run_throttling_test())
