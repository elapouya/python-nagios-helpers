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
import logging.handlers
import pprint
from .host import Host
from .response import PluginResponse, OK, WARNING, CRITICAL, UNKNOWN
import tempfile
from addicted import *
#
pp = pprint.PrettyPrinter(indent=4)

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

    def add_cmd_options(self):
        pass

    def get_logger_name(self):
        return self.logger_name

    def get_logger_format(self):
        return self.logger_format

    def get_logger_level(self):
        if self.options.debug:
            return logging.DEBUG
        elif self.options.verbose:
            return logging.INFO
        return logging.CRITICAL

    def get_logger_file_level(self):
        return self.get_logger_level()

    def get_logger_console_level(self):
        return self.get_logger_level()

    def get_logger_file_logfile(self):
        return self.options.logfile

    def add_logger_file_handler(self):
        logfile = self.get_logger_file_logfile()
        if logfile:
            fh = logging.handlers.RotatingFileHandler(logfile, maxBytes=self.logger_logsize,
                                                           backupCount=self.logger_logbackup)
            fh.setLevel(self.get_logger_file_level())
            formatter = logging.Formatter(self.logger_format)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.debug('Debug log file = %s' % logfile)

    def add_logger_console_handler(self):
        ch = logging.StreamHandler()
        ch.setLevel(self.get_logger_console_level())
        formatter = logging.Formatter(self.logger_format)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def init_logger(self):
        self.logger = logging.getLogger(self.get_logger_name())
        self.logger.setLevel(logging.DEBUG)
        self.add_logger_console_handler()
        self.add_logger_file_handler()

    def handle_cmd_options(self):
        (options, args) = self._cmd_parser.parse_args()
        self.options = options
        self.args = args
        if self.options.show_description:
            print self.__class__.__doc__
            exit(0)

    def manage_cmd_options(self):
        self.init_cmd_options()
        self.add_cmd_options()
        self.handle_cmd_options()

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
    usage = 'usage: \n%prog <module.plugin_class> [options]'
    collected_data_basedir = '/tmp'
    cmd_params = ''
    required_params = ''


    def __init__(self):
        self.response = self.response_class(self)

    def get_plugin_host_params_tab(self):
        return {    'name'  : 'Hostname',
                    'ip'    : 'Host IP address',
                }

    def get_plugin_host_params_desc(self):
        params_tab = self.get_plugin_host_params_tab()
        cmd_params = self.cmd_params.split(',') if isinstance(self.cmd_params,basestring) else self.cmd_params
        cmd_params = set(cmd_params).union(['name','ip'])
        return dict([(k,params_tab.get(k,k.title())) for k in cmd_params ])

    def get_plugin_required_params(self):
        required_params = self.required_params.split(',') if isinstance(self.required_params,basestring) else self.required_params
        return set(required_params).union(['ip'])


    def init_cmd_options(self):
        super(ActivePlugin,self).init_cmd_options()
        for param,desc in self.get_plugin_host_params_desc().items():
            self._cmd_parser.add_option('--%s' % param, action='store', type='string', dest="host__%s" % param, metavar=param.upper(), help=desc)
        self._cmd_parser.add_option('-s', action='store_true', dest='save_collected',
                                   default=False, help='Save collected data in a temporary file')
        self._cmd_parser.add_option('-r', action='store_true', dest='restore_collected',
                                   default=False, help='Use saved collected data (option -s)')

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

    def get_collected_data_filename(self):
        hostname = self.host.name or 'unknown_host'

    def save_collected_data(self):
        pass

    def restore_collected_data(self):
        pass

    def collect_data(self):
        self.cdata = NoAttrDict()

    def parse_data(self):
        self.pdata = NoAttrDict()

    def build_response(self):
        pass

    def run(self):
        self.manage_cmd_options()
        self.init_logger()
        self.host = self.host_class(self)

        self.info('Start plugin %s.%s for %s' % (self.__module__,self.__class__.__name__,self.host.name))
        self.debug('Host informations:\n\n%r\n' % self.host)

        if self.options.restore_collected:
            self.restore_collected_data()
            self.info('Collected data are restored')
        else:
            self.collect_data()
            self.info('Data are collected')
        self.debug('Collected Data = %s' % pp.pformat(self.cdata))

        if self.options.save_collected:
            self.save_collected_data()
            self.info('Collected data are saved')

        self.parse_data()
        self.info('Data are parsed')
        self.debug('Parsed Data = %s' % pp.pformat(self.pdata))

        self.build_response()
        self.response.send()

        self.error('Should never reach this point')