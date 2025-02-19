"""TcEx Framework Module"""

# standard library
import logging
import os
from pathlib import Path

# first-party
from tcex_cli.__metadata__ import __license__, __version__
from tcex_cli.logger.rotating_file_handler_custom import RotatingFileHandlerCustom
from tcex_cli.logger.trace_logger import TraceLogger


def cli_out_path() -> Path:
    """Return the path to the tcex cli command out directory."""
    _out_path = Path(os.path.expanduser('~/.tcex'))
    _out_path.mkdir(exist_ok=True, parents=True)
    return _out_path


def initialize_logger():
    """Initialize logger."""
    # create logger based on custom TestLogger
    logging.setLoggerClass(TraceLogger)

    # init logger
    logger = logging.getLogger(__name__.split('.', maxsplit=1)[0])

    # set logger level
    logger.setLevel(logging.TRACE)  # type: ignore

    # create rotation filehandler
    lfh = RotatingFileHandlerCustom(
        backupCount=3,
        filename=cli_out_path() / 'tcex.log',
        maxBytes=100_000,
    )

    # get logging level from OS env or default to debug
    logging_level = logging.getLevelName('DEBUG')

    # set handler logging level
    lfh.setLevel(logging_level)

    # create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)'
    )
    if logging_level < 10:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            '(%(filename)s:%(funcName)s:%(lineno)d:%(threadName)s)'
        )

    # set formatter
    lfh.setFormatter(formatter)

    # add handler
    logger.addHandler(lfh)


initialize_logger()
