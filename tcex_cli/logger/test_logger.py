"""TcEx Framework Module"""

# standard library
import logging
import os

from .rotating_file_handler_custom import RotatingFileHandlerCustom
from .trace_logger import TraceLogger


class TestLogger(TraceLogger):
    """Custom logger for test Case"""

    def setup_logger(self):
        """Configure the logger."""
        # set logger level to TRACE
        self.setLevel(5)

        # set the appropriate log file name (must be tests.log)
        filename = os.path.join(os.getcwd(), 'log', 'tests.log')

        # clear previous logfile
        if os.path.exists(filename):
            os.remove(filename)

        # add rotating log handler for entire test suite
        lfh = RotatingFileHandlerCustom(filename=filename)

        # create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # if logging_level < 10:
        #     formatter = logging.Formatter(
        #         '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        #         '(%(filename)s:%(funcName)s:%(lineno)d:%(threadName)s)'
        #     )

        # set formatter
        lfh.setFormatter(formatter)

        # add handler
        self.addHandler(lfh)

    def title(self, title: str, separator: str = '-'):
        """Log validation data.

        Args:
            title: The title for the section of data to be written using data method.
            separator: The value to use as a separator. Defaults to '-'.
        """
        separator = f'{separator * 3}'
        self.log(logging.INFO, f'{separator} {title} {separator}')
