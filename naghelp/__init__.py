# -*- coding: utf-8 -*-
#
# python-nagios-helpers - Python Nagios plug-in and configuration environment
# Copyright (C) 2015 Eric Lapouyade
#

__version__ = '0.1.2'
__author__ = 'Eric Lapouyade'
__copyright__ = 'Copyright 2015, python-nagios-helpers project'
__credits__ = ['Eric Lapouyade']
__license__ = 'LGPL'
__maintainer__ = 'Eric Lapouyade'
__status__ = 'Beta'


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

def activate_debug():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)