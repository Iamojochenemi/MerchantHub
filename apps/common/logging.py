"""
Logging configuration for MerchantHub.

Logs are written to stdout in a structured format suitable for
containerized environments (Docker, cloud platforms).

Usage
-----
In any module:

.. code:: python

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Sale created", extra={"sale_id": sale.pk, "amount": total})


Configuration
-------------
Add this to ``config/settings.py``:

.. code:: python

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {name} {message}",
                "style": "{",
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "verbose",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "apps": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": False,
            },
        },
    }
"""

import logging

# Default logger for MerchantHub application code.
logger = logging.getLogger("merchanthub")


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module *name*.

    Usage::

        logger = get_logger(__name__)
        logger.info("Operation completed")
    """
    return logging.getLogger(name)
