"""
SMMA Bot System — Package Initializer
Initial entry point: validates config, sets up logging.
"""

import sys
from utils.logger import setup_logging
from validation.auth_validator import AuthValidator

logger = setup_logging()


def initialize() -> bool:
    """Boot the system — logging + config validation."""
    logger.info("Initializing SMMA Bot System…")
    if not AuthValidator.validate_config():
        logger.critical("Config validation failed — check your .env file.")
        return False
    logger.info("System initialized successfully.")
    return True


def shutdown(code: int = 0):
    logger.info("Shutting down SMMA Bot System.")
    sys.exit(code)
