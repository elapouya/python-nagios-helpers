# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

import os
import sys
import re
import json
from optparse import OptionParser, OptionGroup
import traceback
import logging
import logging.handlers
import pprint
from .host import Host
from .response import PluginResponse, OK, WARNING, CRITICAL, UNKNOWN
import tempfile
from addicted import NoAttr
import textops
from collect import search_invalid_port
import datetime
import naghelp

#
pp = pprint.PrettyPrinter(indent=4)

__all__ = [ 'ActivePlugin' ]

class Plugin(object):
    plugin_type = 'plugin'
    plugins_basedir = os.path.dirname(__file__)
    plugins_basemodule = ''
    logger_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logger_logsize = 1000000
    logger_logbackup = 5

    @classmethod
    def get_instance(cls, plugin_name):
        plugin_class = cls.get_plugin_class(plugin_name)
        if not plugin_class:
            return None
        return plugin_class()

    @classmethod
    def get_plugin(cls,plugin_name):
        plugin_name = plugin_name.lower()
        plugins = cls.find_plugins()
        if plugin_name in plugins:
            return plugins[plugin_name]['module'],plugins[plugin_name]['name']
        return None,None

    @classmethod
    def get_plugin_class(cls,plugin_name):
        module_and_class = plugin_name.rsplit('.',1)
        if len(module_and_class) == 1:
            module_name,class_name = cls.get_plugin(module_and_class[0])
        else:
            module_name,class_name = module_and_class
        try:
            module = __import__(module_name, fromlist=[''])
            plugin_class = getattr(module,class_name,None)
            if hasattr(plugin_class,'plugin_type') and  not plugin_class.__dict__.get('abstract',False):
                return plugin_class
        except Exception,e:
            pass
        return None

    @classmethod
    def find_plugins(cls):
        plugins = {}
        basedir = os.path.normpath(cls.plugins_basedir)
        for root,dirs,files in os.walk(basedir):
            if '/.' not in root:
                for f in files:
                    if f.endswith('.py') and not f.startswith('__'):
                        path = os.path.join(root,f)
                        try:
                            module_name = path[len(basedir)+1:-3].replace(os.sep,'.')
                            module = __import__(cls.plugins_basemodule + module_name,fromlist=[''])
                            for name,member in module.__dict__.items():
                                try:
                                    if hasattr(member,'plugin_type') and getattr(member,'plugin_type') == cls.plugin_type and  not member.__dict__.get('abstract',False):
                                        doc = member.__doc__ or ''
                                        plugins[member.__name__.lower()] = {
                                            'name'  : member.__name__,
                                            'module': cls.plugins_basemodule + module_name,
                                            'path'  : os.sep.join(module_name.split('.'))+'.py',
                                            'desc'  : doc.splitlines()[0]
                                        }
                                except Exception,e:
                                    #print e
                                    pass
                        except Exception,e:
                            #print e
                            pass
        return plugins

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
        self._cmd_parser.add_option('-l', action='store', dest='logfile', metavar="FILE",
                                   help='Redirect logs into a file')
        self._cmd_parser.add_option('-i', action='store_true', dest='show_description',
                                   default=False, help='Display plugin description')

    def add_cmd_options(self):
        pass

    def get_logger_format(self):
        return self.logger_format

    def get_logger_level(self):
        if self.options.debug:
            return logging.DEBUG
        elif self.options.verbose:
            return logging.INFO
        return logging.ERROR

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
            naghelp.logger.addHandler(fh)
            textops.logger.addHandler(fh)
            self.debug('Debug log file = %s' % logfile)

    def add_logger_console_handler(self):
        ch = logging.StreamHandler()
        ch.setLevel(self.get_logger_console_level())
        formatter = logging.Formatter(self.logger_format)
        ch.setFormatter(formatter)
        naghelp.logger.addHandler(ch)
        textops.logger.addHandler(ch)

    def init_logger(self):
        naghelp.logger.setLevel(logging.DEBUG)
        textops.logger.setLevel(logging.DEBUG)
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

    @classmethod
    def error(cls,msg,*args,**kwargs):
        naghelp.logger.error(msg,*args,**kwargs)

    @classmethod
    def warning(cls,msg,*args,**kwargs):
        naghelp.logger.warning(msg,*args,**kwargs)

    @classmethod
    def info(cls,msg,*args,**kwargs):
        naghelp.logger.info(msg,*args,**kwargs)

    @classmethod
    def debug(cls,msg,*args,**kwargs):
        naghelp.logger.debug(msg,*args,**kwargs)

    @classmethod
    def save_data(cls,filename,data, ignore_error = True):
        cls.debug('Saving data to %s :\n%s',filename,pp.pformat(data))
        try:
            filedir = os.path.dirname(filename)
            if not os.path.exists(filedir):
                os.makedirs(filedir)
            with open(filename,'w') as fh:
                json.dump(data,fh,indent=4,default=datetime_handler)
            os.chmod(filename, 0o666)
        except Exception,e:
            cls.debug('Exception : %s',e)
            if not ignore_error:
                raise

    @classmethod
    def load_data(cls,filename):
        cls.debug('Loading data from %s :',filename)
        try:
            with open(filename) as fh:
                data = textops.DictExt(json.load(fh))
                cls.debug(pp.pformat(data))
                return data
        except (IOError, OSError, ValueError),e:
            cls.debug('Exception : %s',e)
        cls.debug('No data found')
        return textops.NoAttr

    @classmethod
    def load_data_fast(cls,filename):
        try:
            with open(filename) as fh:
                data = json.load(fh)
                return data
        except (IOError, OSError, ValueError),e:
            cls.debug('Exception : %s',e)
        return None

class ActivePlugin(Plugin):
    """ Python base class for active nagios plugins

    This is the base class for developping Active Nagios plugin with the naghelp module
    """
    plugin_type = 'active'
    host_class = Host
    response_class = PluginResponse
    usage = 'usage: \n%prog <plugin name or module.plugin_class> [options]'
    cmd_params = ''
    required_params = ''
    tcp_ports = ''
    udp_ports = ''
    nagios_status_on_error = CRITICAL
    collected_data_filename_pattern = '/tmp/naghelp/%s_collected_data.json'
    data = textops.DictExt()
    default_level = OK

    def __init__(self):
        self.starttime = datetime.datetime.now()
        self.response = self.response_class(default_level=self.default_level)

    def get_plugin_host_params_tab(self):
        return {    'name'  : 'Hostname',
                    'ip'    : 'Host IP address',
                }

    def get_plugin_host_params_desc(self):
        params_tab = self.get_plugin_host_params_tab()
        cmd_params = self.cmd_params.split(',') if isinstance(self.cmd_params,basestring) else self.cmd_params
        cmd_params = set(cmd_params).union(['name','ip'])
        return dict([(k,params_tab.get(k,k.title())) for k in cmd_params if k ])

    def get_plugin_required_params(self):
        required_params = self.required_params.split(',') if isinstance(self.required_params,basestring) else self.required_params
        return set(required_params).union(['ip'])


    def init_cmd_options(self):
        super(ActivePlugin,self).init_cmd_options()

        host_params_desc = self.get_plugin_host_params_desc()
        if host_params_desc:
            group = OptionGroup(self._cmd_parser, 'Host attributes','To be used to force host attributes values')
            for param,desc in host_params_desc.items():
                group.add_option('--%s' % param, action='store', type='string', dest="host__%s" % param, metavar=param.upper(), help=desc)
            self._cmd_parser.add_option_group(group)

        self._cmd_parser.add_option('-n', action='store_true', dest='in_nagios_env',
                                   default=False, help='Must be used when the plugin is started by nagios')
        self._cmd_parser.add_option('-s', action='store_true', dest='save_collected',
                                   default=False, help='Save collected data in a temporary file')
        self._cmd_parser.add_option('-r', action='store_true', dest='restore_collected',
                                   default=False, help='Use saved collected data (option -s)')
        self._cmd_parser.add_option('-a', action='store_true', dest='collect_and_print',
                                   default=False, help='Collect data only and print them')
        self._cmd_parser.add_option('-b', action='store_true', dest='parse_and_print',
                                   default=False, help='Collect and parse data only and print them')

    def handle_plugin_name(self):
        if not self.args:
            self._cmd_parser.error('*** You must specify the plugin name ***')

    def handle_cmd_options(self):
        super(ActivePlugin,self).handle_cmd_options()
        self.handle_plugin_name()
        if self.options.show_description:
            print self.get_plugin_desc()
            UNKNOWN.exit()

    def fast_response(self,level, synopsis, msg='', sublevel = 1):
        self.response.level = level
        self.response.sublevel = sublevel
        self.response.set_synopsis(synopsis)
        self.response.add_begin(msg)
        self.response.add_end(self.get_plugin_informations())
        self.response.send()

    def fast_responsei_if(self,test, level, synopsis, msg='', sublevel = 1):
        if test:
            self.fast_response(level, synopsis, msg='', sublevel = 1)

    def error(self, msg, sublevel=3,*args,**kwargs):
        import traceback
        body = traceback.format_exc() + '\n'
        if self.data:
            body += 'Data = \n%s\n\n' % pp.pformat(self.data)
        naghelp.logger.error(msg,*args,**kwargs)
        self.fast_response(self.nagios_status_on_error,msg,body,sublevel)

    def warning(self,msg,*args,**kwargs):
        naghelp.logger.warning(msg,*args,**kwargs)
        self.response.add(msg % args,WARNING)

    def get_collected_data_filename(self):
        hostname = self.host.name or 'unknown_host'

    def save_collected_data(self):
        self.save_data(self.collected_data_filename_pattern % self.host.name, self.data)

    def restore_collected_data(self):
        self.data = self.load_data(self.collected_data_filename_pattern % self.host.name)

    def check_ports(self):
        invalid_port = search_invalid_port(self.host.ip,self.tcp_ports)
        if invalid_port:
            self.fast_response(CRITICAL,
                               'Port %s is unreachable' % invalid_port,
                               'please check your firewall\n\n',
                               2)

    def collect_data(self,data):
        pass

    def parse_data(self,data):
        pass

    def build_response(self,data):
        pass

    def get_plugin_informations(self):
        out = self.response.section_format('Plugin Informations') + '\n'
        out += 'Plugin name : %s.%s\n' % (self.__class__.__module__,self.__class__.__name__)
        out += 'Description : %s\n' % ( self.__class__.__doc__ or '' ).splitlines()[0].strip()
        out += 'Ports used : tcp = %s, udp = %s\n' % (self.tcp_ports or 'none',self.udp_ports or 'none')
        delta = datetime.datetime.now() - self.starttime
        out += 'Execution time : %s\n' % delta
        out += 'Exit code : %s (%s), __sublevel__=%s' % (self.response.level.exit_code,self.response.level.name,self.response.sublevel)
        return out

    def run(self):
        try:
            self.manage_cmd_options()
            self.host = self.host_class(self)
            self.init_logger()

            self.info('Start plugin %s.%s for %s' % (self.__module__,self.__class__.__name__,self.host.name))

            self.host.debug()

            if self.options.restore_collected:
                self.restore_collected_data()
                self.info('Collected data are restored')
            else:
                try:
                    self.collect_data(self.data)
                except Exception,e:
                    if self.tcp_ports:
                        self.info('Checking TCP ports %s ...' % self.tcp_ports)
                        self.check_ports()
                        self.info('All TCP ports are reachable')
                    else:
                        self.info('No port to check')
                    msg = 'Failed to collect equipment status : %s\n' % e
                    self.error(msg, sublevel=1)

                self.info('Data are collected')
            self.debug('Collected Data = \n%s' % pp.pformat(self.data))
            collected_keys = self.data.keys()

            if self.options.save_collected:
                self.save_collected_data()
                self.info('Collected data are saved')

            if self.options.collect_and_print or self.options.parse_and_print:
                print 'Collected Data ='
                pp.pprint(self.data)
                if not self.options.parse_and_print:
                    exit(0)

            self.parse_data(self.data)
            self.info('Data are parsed')
            self.debug('Parsed Data = \n%s' % pp.pformat(self.data.exclude_keys(collected_keys)))

            if self.options.parse_and_print:
                print 'Parsed Data ='
                pp.pprint(self.data.exclude_keys(collected_keys))
                exit(0)

            self.build_response(self.data)
            self.host.save_persistent_data()
            self.response.add_end(self.get_plugin_informations())
            self.response.send()
        except Exception,e:
            self.error('Plugin internal error : %s' % e)

        self.error('Should never reach this point')

def datetime_handler(obj):
    if isinstance(obj, (datetime.datetime,datetime.date)):
        return obj.isoformat()
    return None
