# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

import os
import sys
import re
from optparse import OptionParser
import traceback
import logging
import pprint
from .host import Host
from .response import PluginResponse, OK, WARNING, CRITICAL, UNKNOWN

pprint = pprint.PrettyPrinter(indent=4).pprint
pformat = pprint.PrettyPrinter(indent=4).pformat

class Plugin(object):
    plugin_type = 'abstract'
    logger_name = 'naghelp'
    logger_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logger_logsize = 1000000
    logger_logbackup = 5

    def get_cmd_usage(self):
        return self.usage

    def get_plugin_desc(self):
        return ''

    def get_plugin_params_desc(self):
        return {}

    def init_cmd_options(self):
        self._cmd_parser = OptionParser(usage = self.get_cmd_usage())
        self._cmd_parser.add_option('-v', action='store_true', dest='verbose',
                                   default=False, help='Verbose : display informational messages')
        self._cmd_parser.add_option('-d', action='store_true', dest='debug',
                                   default=False, help='Debug : display debug messages')
        self._cmd_parser.add_option('-l', action='store', dest='logfile', metavar="LOG_FILE",
                                   help='Redirect logs into a file')
        self._cmd_parser.add_option('-i', action='store_true', dest='show_description',
                                   default=False, help='Display plugin description')
        for param,desc in self.host.get_plugin_params_desc().items():
            self._cmd_parser.add_option('--%s' % param, action='store', type='string', dest=param, help=desc)

    def add_custom_cmd_options(self):
        pass

    def handle_custom_cmd_options(self):
        pass

    def get_logger_name(self):
        return self.get_logger_name

    def get_logger_format(self):
        return self.get_logger_format

    def get_logger_file_level():
        if self.options.debug:
            return logging.DEBUG
        elif self.options.verbose:
            return logging.INFO
        return logging.CRITICAL

    def get_logger_console_level():
        return self.get_logger_file_level()

    def get_logger_file_logfile():
        return self.options.logfile

    def add_logger_file_handler():
        logfile = self.get_logger_file_logfile()
        if logfile:
            fh = logging.handlers.RotatingFileHandler(logfile, maxBytes=self.logger_logsize,
                                                           backupCount=self.logger_logbackup)
            fh.setLevel(self.get_logger_file_level())
            formatter = logging.Formatter(self.logger_format)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

    def add_logger_console_handler():
        ch = logging.StreamHandler()
        ch.setLevel(self.get_logger_console_level())
        formatter = logging.Formatter(self.logger_format)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def init_logger(self):
        self.logger = logging.getLogger(self.get_logger_name())
        self.logger.setLevel(logging.DEBUG)
        self.add_logger_file_handler()
        self.add_logger_console_handler()

    def handle_cmd_options(self):
        (options, args) = self._cmd_parser.parse_args()
        self.options = options
        self.args = args
        self.init_logger()

    def manage_cmd_options(self):
        self.init_cmd_options()
        self.add_cmd_options()
        self.handle_cmd_options()
        self.handle_custom_cmd_options()

    def error(self,msg):
        self.logger.error(msg)

    def warning(self,msg):
        self.logger.warning(msg)

    def info(self,msg):
        self.logger.info(msg)

    def debug(self,msg):
        self.logger.debug(msg)

class ActivePlugin(Plugin):
    plugin_type = 'active'
    host_class = Host
    response_class = PluginResponse
    usage = 'usage: \n%prog [options]'

    def __init__(self, hostname):
        self.response = response_class()

    def handle_cmd_options(self):
        super(ActivePlugin,self).handle_cmd_options()
        if self.options.show_description:
            print self.get_plugin_desc()
            UNKNOWN.exit()

    def error(self,msg):
        self.logger.error(msg)
        print 'Plugin Error :',msg
        UNKNOWN.exit()

    def warning(self,msg):
        self.logger.warning(msg)
        self.response.add(msg,WARNING)

    def run(self):
        self.manage_cmd_options()
        self.host = host_class(self.options)
        self.collect_data()
        self.parse_data()
        self.build_response()
        self.response.send()