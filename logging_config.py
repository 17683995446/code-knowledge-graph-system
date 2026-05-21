"""
Logging Configuration Module
Provides centralized logging setup for the code knowledge graph system.
"""

import logging
import sys


def setup_logging():
    """Set up the root 'code_kg' logger with a StreamHandler."""
    logger = logging.getLogger('code_kg')
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if setup is called multiple times
    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] %(funcName)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'code_kg' hierarchy.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A ``logging.Logger`` instance named ``code_kg.<name>``.
    """
    setup_logging()
    return logging.getLogger(f'code_kg.{name}')


# Auto-initialize on module import
setup_logging()
