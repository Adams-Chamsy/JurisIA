"""
JurisIA — Configuration du Logging Structuré
Utilise structlog pour des logs JSON en production, pretty-print en développement.
En mode TEST (APP_ENV=development et pytest en cours), ne reconfigure pas structlog
pour ne pas écraser la config de test.
"""
import logging
import os
import sys

import structlog


def configure_logging() -> None:
    """
    Configure structlog + logging standard Python.
    No-op si pytest est en cours d'exécution (pour ne pas écraser la config de test).
    """
    # Détecter si on est dans pytest
    _in_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
    if _in_pytest:
        return  # Laisser conftest.py gérer la config

    from app.core.config import settings

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.APP_DEBUG else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    )
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.APP_DEBUG else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
