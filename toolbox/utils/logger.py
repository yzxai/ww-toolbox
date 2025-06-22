from pathlib import Path
from .generic import get_project_root, get_timestamp

import logging
import os
import asyncio
import aiohttp
import queue
import threading

FILE_FMT    = '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
HTTP_FMT    = '[%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'
CONSOLE_FMT = '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)s] %(message)s'

DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
LOG_DIR = get_project_root() / 'logs'

class ColoredFormatter(logging.Formatter):
    """A custom log formatter that adds color to log levels."""

    COLORS = {
        'WARNING': '\033[93m',  # Yellow
        'INFO': '\033[92m',     # Green
        'DEBUG': '\033[96m',    # Cyan
        'CRITICAL': '\033[91m', # Bright Red
        'ERROR': '\033[91m',    # Red
    }
    RESET = '\033[0m'

    def __init__(self, fmt, *args, **kwargs):
        super().__init__(fmt, *args, **kwargs)

    def format(self, record):
        record_copy = logging.makeLogRecord(record.__dict__)
        log_level_color = self.COLORS.get(record_copy.levelname, self.RESET)
        record_copy.levelname = f"{log_level_color}{record_copy.levelname}{self.RESET}"
        return super().format(record_copy)

class HTTPLogHandler(logging.Handler):
    def __init__(self, port: int = 2590):
        super().__init__()
        self.port = port
        self.log_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.is_running = True
        self.worker_thread.start()

    def _log_worker(self):
        asyncio.run(self._async_log_sender())

    async def _async_log_sender(self):
        async with aiohttp.ClientSession() as session:
            while True:
                record = self.log_queue.get()
                if record is None:  # Sentinel to stop the worker
                    break

                log_entry = self.format(record)
                try:
                    async with session.post(f'http://localhost:{self.port}',
                                            json={'content': log_entry, 'type': record.levelname}) as response:
                        response.raise_for_status()
                except Exception as e:
                    print(f'Failed to send log to http handler: {e}. Disabling http handler.')
                    self.is_running = False
                    break
                finally:
                    self.log_queue.task_done()

    def emit(self, record: logging.LogRecord):
        if not self.is_running:
            return
        self.log_queue.put(record)

    def close(self):
        if not self.is_running:
            return
        self.log_queue.put(None)
        self.worker_thread.join()
        super().close()
        
def setup_console_handler(level: int = logging.INFO) -> logging.StreamHandler:
    """Setup a console handler with a specific log level """
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = ColoredFormatter(CONSOLE_FMT)
    handler.setFormatter(formatter)
    return handler

def setup_file_handler(log_dir: Path, level: int = logging.INFO) -> logging.FileHandler:
    """Setup a file handler with a specific log level """
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = get_timestamp()
    log_file = log_dir / f"ww_{timestamp}.log"
    handler = logging.FileHandler(log_file)
    handler.setLevel(level)
    formatter = logging.Formatter(FILE_FMT)
    handler.setFormatter(formatter)
    return handler

def setup_http_handler(port: int = 2590) -> HTTPLogHandler:
    """Setup a http handler with a specific port """
    handler = HTTPLogHandler(port)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(HTTP_FMT)
    handler.setFormatter(formatter)
    return handler

logger = logging.getLogger('ww')
log_level = logging.DEBUG if DEBUG else logging.INFO

# setup console handler
console_handler = setup_console_handler(log_level)
logger.addHandler(console_handler)

# setup file handler
file_handler = setup_file_handler(LOG_DIR, log_level)
logger.addHandler(file_handler)

# setup http handler
http_handler = setup_http_handler(port=2590)
logger.addHandler(http_handler)

logger.setLevel(log_level)
logger.propagate = False
logger.info('Logger initialized')



