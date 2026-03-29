import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List

sys_path_added = False
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))
    sys_path_added = True


class JSONLogger:
    def __init__(self, log_file: str, level: str = "INFO"):
        self.log_file = log_file
        self.logger = logging.getLogger("diffused_lemon")
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)

    def _log(self, level: str, message: str, **kwargs):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message
        }
        log_entry.update(kwargs)
        self.logger.log(getattr(logging, level.upper()), json.dumps(log_entry))

    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)

    def debug(self, message: str, **kwargs):
        self._log("DEBUG", message, **kwargs)


logger = None


def get_logger():
    global logger
    if logger is None:
        from config import config
        logger = JSONLogger(config.log_file, config.log_level)
    return logger
