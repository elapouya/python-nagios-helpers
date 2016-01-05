# -*- coding: utf-8 -*-
#
# Création : July 8th, 2015
#
# @author: Eric Lapouyade
#

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
from addicted import NoAttr, NoAttrDict
import textops
from collect import search_invalid_port
import datetime
import naghelp
import socket
#
pp = pprint.PrettyPrinter(indent=4)

__all__ = [ 'ActivePlugin' ]

class Plugin(object):
    """ Plugin base class

    This is an abstract class used with :class:`naghelp.ActivePlugin`, it brings :

        * plugin search in a directory of python files
        * plugin instance generation
        * plugin logging management
        * plugin command line options management
        * plugin persistent data management

    This abstract class should be used later with :class:`naghelp.PassivePlugin` when developed.
    """

    plugin_type = 'plugin'
    """ For plugin search, it will search for classes having this attribute in all python files"""

    plugins_basedir = os.path.dirname(__file__)
    """ For plugin search, it will search recursively from this directory """

    plugins_basemodule = ''
    """ For plugin search, the module prefix to add to have the module accessible from python path"""

    logger_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    """ The logging format to use """

    logger_logsize = 1000000
    """ Log file max size """

    logger_logbackup = 5
    """ Log file backup file number"""

    @classmethod
    def get_instance(cls, plugin_name):
        """ Generate a plugin instance from its name string

        This method is useful when you only know at execution time the name of
        the plugin to instantiate.

        If you have an active plugin class called ``HpProliant`` in a file located at
        ``/home/me/myplugin_dir/hp/hp_proliant.py`` then you can get the plugin instance this way :

        For all your plugins, you should first subclass the ActivePlugin to override plugins_basedir::

            class MyActivePlugin(ActivePlugin):
                plugins_basedir = '/home/me/myplugin_dir'

            class HpProliant(MyActivePlugin):
                ''' My code '''

        Check that ``/home/me/myplugin_dir`` is in your python path.

        Then you can get an instance by giving only the class name (case insensitive)::

            plugin = MyActivePlugin.get_instance('hpproliant')

        Or with the full doted path (case sensitive this time)::

            plugin = MyActivePlugin.get_instance('hp.hp_proliant.HpProliant')

        In first case, it is shorter but a recursive search will occur to find the class
        in all python files located in ``/home/me/myplugin_dir/``. It is mainly useful in
        python interactive console.

        In second case, as you specified the full path, the class is found at once : it is faster
        and should be used in production.

        Once the class is found, an instance is created and returned.

        Of course, if you do not need to get an instance from a string :
        it is more pythonic to do like this::

            from hp.hp_proliant import HpProliant
            plugin = HpProliant()
        """
        plugin_class = cls.get_plugin_class(plugin_name)
        if not plugin_class:
            return None
        return plugin_class()

    @classmethod
    def get_plugin(cls,plugin_name):
        """ find a plugin and return its module and its class name

        To get the class itself, one have to get the corresponding module's attribute::

            module,class_name = MyActivePlugin.get_plugin('hpproliant')
            plugin_class = getattr(module,class_name,None)

        Args:

            plugin_name(str): the plugin name to find (case insensitive)

        Returns:

            module, str: A tuple containing the plugin's module and plugin's class name
        """
        plugin_name = plugin_name.lower()
        plugins = cls.find_plugins()
        if plugin_name in plugins:
            return plugins[plugin_name]['module'],plugins[plugin_name]['name']
        return None,None

    @classmethod
    def get_plugin_class(cls,plugin_name):
        """ get the plugin class from its name

        If the dotted notation is used, the string is case sensitive and the corresponding module
        is loaded at once, otherwise the plugin name is case insensitive and a recursive file search
        is done from the directory ``plugin_class.plugins_basedir``

        Args:

            plugin_name(str): the plugin name to find.

        Returns:

            class object or None: plugin's class object or None if not found.

        You can get plugin class object by giving only the class name (case insensitive)::

            plugin_class = MyActivePlugin.get_plugin_class('hpproliant')

        Or with the full dotted path (case sensitive this time)::

            plugin_class = MyActivePlugin.get_plugin_class('hp.hp_proliant.HpProliant')

        If you need a plugin instance, prefer using :meth:`get_instance`
        """
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
        """ Recursively find all plugin classes for all python files present in a directory.

        It finds all python files inside ``YourPluginsBaseClass.plugins_basedir`` then look for
        all classes having the attribute ``plugin_type`` with the value
        ``YourPluginsBaseClass.plugin_type``

        It returns a dictionary where keys are plugin class name in lower case and the values
        are a dictionary containing :

            =======  ==============================================
            Keys     Values
            =======  ==============================================
            name     the class name (case sensitive)
            module   the plugin module name with a full dotted path
            path     the module file path
            desc     the plugin description (first docstring line)
            =======  ==============================================
        """
        plugins = {}
        basedir = os.path.normpath(cls.plugins_basedir)
        for root,dirs,files in os.walk(basedir):
            if '/.' not in root and '__init__.py' in files:
                for f in files:
                    if f.endswith('.py') and not f.startswith('__'):
                        path = os.path.join(root,f)
                        try:
                            module_name = path[len(basedir)+1:-3].replace(os.sep,'.')
                            module = __import__(cls.plugins_basemodule + module_name,fromlist=[''])
                            for name,member in module.__dict__.items():
                                try:
                                    if hasattr(member,'plugin_type') and getattr(member,'plugin_type') == cls.plugin_type and  not member.__dict__.get('abstract',False):
                                        doc = member.get_plugin_desc()
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

    @classmethod
    def find_plugins_import_errors(cls):
        """ Find all import errors all python files present in a directory.

        It finds all python files inside ``YourPluginsBaseClass.plugins_basedir`` and try to import
        them. If an error occurs, the file path and linked exception is memorized.

        It returns a list of tuples containing the file path and the exception.
        """
        plugin_files = []
        basedir = os.path.normpath(cls.plugins_basedir)
        for root,dirs,files in os.walk(basedir):
            if '/.' not in root and '__init__.py' in files:
                for f in files:
                    if f.endswith('.py') and not f.startswith('__'):
                        path = os.path.join(root,f)
                        try:
                            module_name = path[len(basedir)+1:-3].replace(os.sep,'.')
                            module = __import__(cls.plugins_basemodule + module_name,fromlist=[''])
                        except Exception,e:
                            plugin_files.append((os.sep.join(module_name.split('.'))+'.py',e))
                            pass
        return plugin_files

    def get_cmd_usage(self):
        """ Returns the command line usage """
        return self.usage

    @classmethod
    def get_plugin_desc(cls):
        """ Returns the plugin description. By default return the class docstring. """
        return cls.__doc__.strip() or ''

    def init_cmd_options(self):
        """ Create OptionParser instance and add some basic options

        This is automatically called when the plugin is run.
        Avoid to override this method, prefer to customize :meth:`add_cmd_options`
        """
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
        """ This method can be customized to add some OptionParser options for the current plugin

        Example::

            self._cmd_parser.add_option('-z', action='store_true', dest='super_debug',
                                       default=False, help='Activate the super debug mode')

        """
        pass

    def get_logger_format(self):
        """ gets logger format, by default the one defined in ``logger_format`` attribute """
        return self.logger_format

    def get_logger_level(self):
        """ gets logger level. By default sets to ``logging.ERROR`` to get only errors """
        if self.options.debug:
            return logging.DEBUG
        elif self.options.verbose:
            return logging.INFO
        return logging.ERROR

    def get_logger_file_level(self):
        """ gets logger level specific for log file output.

        Note : This is possible to set different logger level between log file and console"""
        return self.get_logger_level()

    def get_logger_console_level(self):
        """ gets logger level specific for the console output.

        Note : This is possible to set different logger level between log file and console"""
        return self.get_logger_level()

    def get_logger_file_logfile(self):
        """ get log file path """
        return self.options.logfile

    def add_logger_file_handler(self):
        """ Activate logging to the log file """
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
        """ Activate logging to the console """
        ch = logging.StreamHandler()
        ch.setLevel(self.get_logger_console_level())
        formatter = logging.Formatter(self.logger_format)
        ch.setFormatter(formatter)
        naghelp.logger.addHandler(ch)
        textops.logger.addHandler(ch)

    def init_logger(self):
        """ Initialize logging """
        naghelp.logger.setLevel(logging.DEBUG)
        textops.logger.setLevel(logging.DEBUG)
        self.add_logger_console_handler()
        self.add_logger_file_handler()

    def handle_cmd_options(self):
        """ Parse command line options

        The parsed options are stored in ``self.options`` and arguments in ``self.args``"""
        (options, args) = self._cmd_parser.parse_args()
        self.options = options
        self.args = args
        if self.options.show_description:
            print self.get_plugin_desc()
            exit(0)

    def manage_cmd_options(self):
        """ Manage commande line options

        OptionParser instance is created, options are added, then command line is parsed.
        """
        self.init_cmd_options()
        self.add_cmd_options()
        self.handle_cmd_options()

    @classmethod
    def error(cls,msg,*args,**kwargs):
        """ log an error message

        Args:

            msg(str): the message to log
            args(list): if additional arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)

        Examples:

            This logs an error message in log file and/or console::

                p = Plugin()
                p.error('Syntax error in line %s',36)
        """
        naghelp.logger.error(msg,*args,**kwargs)

    @classmethod
    def warning(cls,msg,*args,**kwargs):
        """ log a warning message

        Args:

            msg(str): the message to log
            args(list): if additional arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)

        Examples:

            This logs an warning message in log file and/or console::

                p = Plugin()
                p.warning('This variable is not used in line %s',36)
        """
        naghelp.logger.warning(msg,*args,**kwargs)

    @classmethod
    def info(cls,msg,*args,**kwargs):
        """ log an informational message

        Args:

            msg(str): the message to log
            args(list): if additional arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)

        Examples:

            This logs an informational message in log file and/or console::

                p = Plugin()
                p.info('Date : %s',datetime.now())
        """
        naghelp.logger.info(msg,*args,**kwargs)

    @classmethod
    def debug(cls,msg,*args,**kwargs):
        """ log a debug message

        Args:

            msg(str): the message to log
            args(list): if additional arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)

        Examples:

            This logs a debug message in log file and/or console::

                p = Plugin()
                p.debug('my_variable = %s',my_variable)
        """
        naghelp.logger.debug(msg,*args,**kwargs)

    @classmethod
    def save_data(cls,filename, data, ignore_error = True):
        """ Serialize and save data into a file

        The data must be a dictionary where values must be simple types :
        str, int, float, date, list and/or dict. The data are serialized into json format.

        Args:

            filename(str): The file path to store the data.
                The directories are created if not present.
            data(dict): The dictionary to save.
            ignore_error(bool): ignore errors if True (Default: True)

        Notes:

            The data dictionary keys must be strings. If you specify integers, they will be replaced
            by a string.

        Examples:

            >>> data={'powers': {1:'OK', 2:'Degraded',3:'OK', 4:'Failed'}, 'nb_disks': 36 }
            >>> ActivePlugin.save_data('/tmp/mydata',data)
            >>> print open('/tmp/mydata').read()  #doctest: +NORMALIZE_WHITESPACE
            {
                "powers": {
                    "1": "OK",
                    "2": "Degraded",
                    "3": "OK",
                    "4": "Failed"
                },
                "nb_disks": 36
            }
        """
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
        """ Load and de-serialize data from a file

        The input file must be a json file.

        Args:

            filename(str): The file path to load.

        Returns:

            :class:`textops.DictExt`: The restored data or ``NoAttr`` on error.

        Examples:

            >>> data = ActivePlugin.load_data('/tmp/mydata')
            >>> print data
            {u'powers': {u'1': u'OK', u'3': u'OK', u'2': u'Degraded', u'4': u'Failed'}, u'nb_disks': 36}
            >>> print type(data)
            <class 'textops.base.DictExt'>

        See :meth:`save_data` to know how ``/tmp/mydata`` has been generated.
        """
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

class ActivePlugin(Plugin):
    """ Python base class for active nagios plugins

    This is the base class for developping Active Nagios plugin with the naghelp module
    """

    plugin_type = 'active'
    """ The plugin type

    This is used during plugin recursive search : should be the same string
    accross all your plugins"""

    host_class = Host
    """ Must contain the host class to use.

    You have to modify this class when you have redefined your own host class """

    response_class = PluginResponse
    """ Must contain the response class to use.

    You have to modify this class when you have redefined your own response class """

    usage = 'usage: \n%prog [options]'
    """ The command line usage """

    options = NoAttrDict()
    """ Contains the command line options as parsed by :class:`optparse.OptionParser` """

    host = NoAttrDict()
    cmd_params = ''
    required_params = None
    forced_params = 'name,ip'
    tcp_ports = ''
    udp_ports = ''
    nagios_status_on_error = CRITICAL
    collected_data_filename_pattern = '/tmp/naghelp/%s_collected_data.json'

    data = textops.DictExt()
    """ The place to put collected and parsed data

    As data is a :class:`textops.DictExt` object, one can use the dotted notation for reading and for
    writing.
    """

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
        forced_params = self.forced_params.split(',') if isinstance(self.forced_params,basestring) else self.forced_params
        cmd_params = set(cmd_params).union(forced_params)
        return dict([(k,params_tab.get(k,k.title())) for k in cmd_params if k ])

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

    def handle_cmd_options(self):
        super(ActivePlugin,self).handle_cmd_options()
        if self.options.show_description:
            print self.get_plugin_desc()
            UNKNOWN.exit()

    def fast_response(self,level, synopsis, msg='', sublevel = 1):
        self.host.save_data()
        self.response.level = level
        self.response.sublevel = sublevel
        self.response.set_synopsis(synopsis)
        self.response.add_begin(msg)
        self.response.add_end(self.get_plugin_informations())
        self.response.send()

    def fast_response_if(self,test, level, synopsis, msg='', sublevel = 1):
        if test:
            self.fast_response(level, synopsis, msg='', sublevel = 1)

    def error(self, msg, sublevel=3, exception=None, *args,**kwargs):
        body = ''
        if exception is None or not isinstance(exception, naghelp.CollectError):
            import traceback
            body += 'traceback : ' + traceback.format_exc() + '\n'
            if self.data:
                body += 'Data = \n%s\n\n' % pp.pformat(self.data).replace('\\n','\n')
        naghelp.logger.error(msg,*args,**kwargs)
        self.fast_response(self.nagios_status_on_error,msg,body,sublevel)

    def warning(self,msg,*args,**kwargs):
        naghelp.logger.warning(msg,*args,**kwargs)
        self.response.add(msg % args,WARNING)

    def save_collected_data(self):
        self.save_data(self.collected_data_filename_pattern % self.host.name, self.data)

    def restore_collected_data(self):
        self.data = self.load_data(self.collected_data_filename_pattern % self.host.name)

    def get_udp_ports(self):
        if self.host.port:
            if not self.tcp_ports:
                return [self.host.port]
        return self.udp_ports

    def get_tcp_ports(self):
        if self.host.port:
            if not self.udp_ports:
                return [self.host.port]
        if self.host.protocol:
            return [socket.getservbyname(self.host.protocol)]
        return self.tcp_ports

    def check_ports(self):
        invalid_port = search_invalid_port(self.host.ip,self.get_tcp_ports())
        if invalid_port:
            self.fast_response(CRITICAL,
                               'Port %s is unreachable' % invalid_port,
                               'This plugin uses ports tcp = %s, udp = %s\nplease check your firewall\n\n' % (self.get_tcp_ports() or 'none',self.get_udp_ports() or 'none'),
                               2)

    def collect_data(self,data):
        pass

    def parse_data(self,data):
        pass

    def build_response(self,data):
        pass

    def get_plugin_informations(self):
        out = '\n' + self.response.section_format('Plugin Informations') + '\n'
        out += 'Plugin name : %s.%s\n' % (self.__class__.__module__,self.__class__.__name__)
        out += 'Description : %s\n' % ( self.__class__.__doc__ or 'no description.' ).splitlines()[0].strip()
        out += 'Ports used : tcp = %s, udp = %s\n' % (self.get_tcp_ports() or 'none',self.get_udp_ports() or 'none')
        delta = datetime.datetime.now() - self.starttime
        out += 'Execution time : %s\n' % delta
        level = self.response.get_current_level()
        out += 'Exit code : %s (%s), __sublevel__=%s' % (level.exit_code,level.name,self.response.sublevel)
        return out

    def check_host_required_fields(self):
        req_fields = self.required_params if self.required_params is not None else self.cmd_params
        if isinstance(req_fields, basestring):
            req_fields = req_fields.split(',')
        # either 'name' or 'ip' must be in required params, by default 'ip' is automatically added as required except when 'name' is present
        if 'name' not in req_fields:
            req_fields = set(req_fields + ['ip'])
        for f in req_fields:
            if not self.host.get(f):
                self.fast_response(CRITICAL, 'Missing "%s" parameter' % f, 'Required fields are : %s' % ','.join(req_fields), 3)
                break

    def run(self):
        """Run the plugin"""
        try:
            self.manage_cmd_options()
            self.host = self.host_class(self)
            self.init_logger()
            self.host.load_data()

            self.info('Start plugin %s.%s for %s' % (self.__module__,self.__class__.__name__,self.host.name))

            self.host.debug()
            self.check_host_required_fields()

            if self.options.restore_collected:
                self.restore_collected_data()
                self.info('Collected data are restored')
            else:
                try:
                    self.collect_data(self.data)
                except Exception,e:
                    if self.get_tcp_ports():
                        self.info('Checking TCP ports %s ...' % self.get_tcp_ports())
                        self.check_ports()
                        self.info('All TCP ports are reachable')
                    else:
                        self.info('No port to check')
                    msg = 'Failed to collect equipment status : %s\n' % e
                    self.error(msg, sublevel=1, exception=e)

                self.info('Data are collected')
            self.debug('Collected Data = \n%s' % pp.pformat(self.data).replace('\\n','\n'))
            collected_keys = self.data.keys()

            if self.options.save_collected:
                self.save_collected_data()
                self.info('Collected data are saved')

            if self.options.collect_and_print or self.options.parse_and_print:
                print 'Collected Data ='
                print pp.pformat(self.data).replace('\\n','\n')
                if not self.options.parse_and_print:
                    exit(0)

            self.parse_data(self.data)
            self.info('Data are parsed')
            self.debug('Parsed Data = \n%s' % pp.pformat(self.data.exclude_keys(collected_keys)).replace('\\n','\n'))

            if self.options.parse_and_print:
                print 'Parsed Data ='
                print pp.pformat(self.data.exclude_keys(collected_keys)).replace('\\n','\n')
                exit(0)

            self.build_response(self.data)
            self.host.save_data()
            self.response.add_end(self.get_plugin_informations())
            self.response.send()
        except Exception,e:
            self.error('Plugin internal error : %s' % e, exception=e)

        self.error('Should never reach this point')

def datetime_handler(obj):
    if isinstance(obj, (datetime.datetime,datetime.date)):
        return obj.isoformat()
    return None
