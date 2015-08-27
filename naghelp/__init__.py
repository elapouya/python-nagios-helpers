# -*- coding: utf-8 -*-
#
# python-nagios-helpers - Python Nagios plug-in and configuration environment
# Copyright (C) 2015 Eric Lapouyade
#

from plugin import *
from host import *
from response import *
from collect import *
from perf import *

import logging
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())

__version__ = '0.0.5'