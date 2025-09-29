"""
Logging configuration for UHRR Backend
"""

import logging
import logging.config
from pathlib import Path
import json


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/uhrr.log",
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
):
    """Setup structured logging configuration"""

    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'json': {
                'format': json.dumps({
                    'timestamp': '%(asctime)s',
                    'level': '%(levelname)s',
                    'logger': '%(name)s',
                    'message': '%(message)s',
                    'module': '%(module)s',
                    'function': '%(funcName)s',
                    'line': '%(lineno)d'
                })
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'detailed',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'json',
                'filename': log_file,
                'maxBytes': max_file_size,
                'backupCount': backup_count
            }
        },
        'loggers': {
            'app': {
                'level': 'DEBUG',
                'handlers': ['console', 'file'],
                'propagate': False
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'uvicorn.access': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            }
        },
        'root': {
            'level': log_level,
            'handlers': ['console', 'file']
        }
    }

    # Apply configuration
    logging.config.dictConfig(config)

    # Set specific log levels
    logging.getLogger('socketio').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)

    return logging.getLogger('app')
