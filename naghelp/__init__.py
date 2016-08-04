# -*- coding: utf-8 -*-
#
# python-nagios-helpers - Python Nagios plug-in and configuration environment
# Copyright (C) 2015 Eric Lapouyade
#

__version__ = '0.1.8'
__author__ = 'Eric Lapouyade'
__copyright__ = 'Copyright 2015-2016, python-nagios-helpers project'
__credits__ = ['Eric Lapouyade']
__license__ = 'LGPL'
__maintainer__ = 'Eric Lapouyade'
__status__ = 'Beta'


from plugin import *
from host import *
from response import *
from collect import *
from perf import *
from tools import *
from mixins import *
import traceback

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

def debug_caller():
    if logger.getEffectiveLevel() == logging.DEBUG:
        stack = list(reversed(traceback.extract_stack()))
        for file,line,func_name,func_line in stack:
            if '/naghelp/' not in file:
                return '[%s:%s]' % (file,line)
    return ''

def debug_listing(data):
    if isinstance(data, basestring):
        data = data.splitlines()
    for line in data:
        logger.debug('| %s',line)

def debug_or_empty(s):
    if logger.getEffectiveLevel() == logging.DEBUG:
        return s
    return ''