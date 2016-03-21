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
    """Plugin base class

    This is an abstract class used with :class:`~naghelp.ActivePlugin`, it brings :

        * plugin search in a directory of python files
        * plugin instance generation
        * plugin logging management
        * plugin command line options management
        * plugin persistent data management

    This abstract class should be used later with :class:`naghelp.PassivePlugin` when developed.
    """

    plugin_type = 'plugin'
    """For plugin search, it will search for classes having this attribute in all python files"""

    plugins_basedir = '/path/to/your/plugins/python/modules'
    """For plugin search, it will search recursively from this directory """

    plugins_basemodule = 'plugins.python.'
    """For plugin search, the module prefix to add to have the module accessible from python path.
    Do not forget the ending dot. You can set empty if your plugin modules are in python path.

    .. note::
        Do not forget to put empty ``__init__.py`` file in each directory leading to your plugins.
    """

    logger_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    """The logging format to use """

    logger_logsize = 1000000
    """Log file max size """

    logger_logbackup = 5
    """Log file backup file number"""

    @classmethod
    def get_instance(cls, plugin_name):
        """Generate a plugin instance from its name string

        This method is useful when you only know at execution time the name of
        the plugin to instantiate.

        If you have an active plugin class called ``HpProliant`` in a file located at
        ``/home/me/myplugin_dir/hp/hp_proliant.py`` then you can get the plugin instance this way :

        For all your plugins, you should first subclass the ActivePlugin to override plugins_basedir::

            class MyProjectActivePlugin(ActivePlugin):
                plugins_basedir = '/home/me/myplugin_dir'
                plugin_type = 'myproject_plugin'  # you choose whatever you want but not 'plugin'

            class HpProliant(MyProjectActivePlugin):
                ''' My code '''

        Check that ``/home/me/myplugin_dir`` is in your python path.

        Then you can get an instance by giving only the class name (case insensitive)::

            plugin = MyProjectActivePlugin.get_instance('hpproliant')

        Or with the full doted path (case sensitive this time)::

            plugin = MyProjectActivePlugin.get_instance('hp.hp_proliant.HpProliant')

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
        """find a plugin and return its module and its class name

        To get the class itself, one have to get the corresponding module's attribute::

            module,class_name = MyProjectActivePlugin.get_plugin('hpproliant')
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
        """get the plugin class from its name

        If the dotted notation is used, the string is case sensitive and the corresponding module
        is loaded at once, otherwise the plugin name is case insensitive and a recursive file search
        is done from the directory ``plugin_class.plugins_basedir``

        Args:

            plugin_name(str): the plugin name to find.

        Returns:

            class object or None: plugin's class object or None if not found.

        You can get plugin class object by giving only the class name (case insensitive)::

            plugin_class = MyProjectActivePlugin.get_plugin_class('hpproliant')

        Or with the full dotted path (case sensitive this time)::

            plugin_class = MyProjectActivePlugin.get_plugin_class('hp.hp_proliant.HpProliant')

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
        """Recursively find all plugin classes for all python files present in a directory.

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
                                            'class' : member,
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
        """Find all import errors all python files present in a directory.

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
        """Returns the command line usage """
        return self.usage

    @classmethod
    def get_plugin_desc(cls):
        """Returns the plugin description. By default return the class docstring. """
        return cls.__doc__.strip() or ''

    def init_cmd_options(self):
        """Create OptionParser instance and add some basic options

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
        """This method can be customized to add some OptionParser options for the current plugin

        Example::

            self._cmd_parser.add_option('-z', action='store_true', dest='super_debug',
                                       default=False, help='Activate the super debug mode')

        """
        pass

    def get_logger_format(self):
        """gets logger format, by default the one defined in ``logger_format`` attribute """
        return self.logger_format

    def get_logger_level(self):
        """gets logger level. By default sets to ``logging.ERROR`` to get only errors """
        if self.options.debug:
            return logging.DEBUG
        elif self.options.verbose:
            return logging.INFO
        return logging.ERROR

    def get_logger_file_level(self):
        """gets logger level specific for log file output.

        Note : This is possible to set different logger level between log file and console"""
        return self.get_logger_level()

    def get_logger_console_level(self):
        """gets logger level specific for the console output.

        Note : This is possible to set different logger level between log file and console"""
        return self.get_logger_level()

    def get_logger_file_logfile(self):
        """get log file path """
        return self.options.logfile

    def add_logger_file_handler(self):
        """Activate logging to the log file """
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
        """Activate logging to the console """
        ch = logging.StreamHandler()
        ch.setLevel(self.get_logger_console_level())
        formatter = logging.Formatter(self.logger_format)
        ch.setFormatter(formatter)
        naghelp.logger.addHandler(ch)
        textops.logger.addHandler(ch)

    def init_logger(self):
        """Initialize logging """
        naghelp.logger.setLevel(logging.DEBUG)
        textops.logger.setLevel(logging.DEBUG)
        self.add_logger_console_handler()
        self.add_logger_file_handler()

    def handle_cmd_options(self):
        """Parse command line options

        The parsed options are stored in ``self.options`` and arguments in ``self.args``
        """
        (options, args) = self._cmd_parser.parse_args()
        self.options = options
        self.args = args
        if self.options.show_description:
            print self.get_plugin_desc()
            exit(0)

    def manage_cmd_options(self):
        """Manage commande line options

        OptionParser instance is created, options are added, then command line is parsed.
        """
        self.init_cmd_options()
        self.add_cmd_options()
        self.handle_cmd_options()

    @classmethod
    def error(cls,msg,*args,**kwargs):
        """log an error message

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
        """log a warning message

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
        """log an informational message

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
        """log a debug message

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
        """Serialize and save data into a file

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
        """Load and de-serialize data from a file

        The input file must be a json file.

        Args:

            filename(str): The file path to load.

        Returns:

            :class:`textops.DictExt`: The restored data or ``NoAttr`` on error.

        Examples:

            >>> open('/tmp/mydata','w').write('''{
            ...   "powers": {
            ...     "1": "OK",
            ...     "2": "Degraded",
            ...     "3": "OK",
            ...     "4": "Failed"
            ...   },
            ...   "nb_disks": 36
            ... }''')
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
    """Python base class for active nagios plugins

    This is the base class for developping Active Nagios plugin with the naghelp module
    """

    plugin_type = 'active'
    """Attribute for the plugin type

    This is used during plugin recursive search : should be the same string
    accross all your plugins"""

    host_class = Host
    """Attribute that must contain the host class to use.

    You have to modify this class when you have redefined your own host class """

    response_class = PluginResponse
    """Attribute that must contain the response class to use.

    You have to modify this class when you have redefined your own response class """

    usage = 'usage: \n%prog [options]'
    """Attribute for the command line usage """

    options = NoAttrDict()
    """Attribute that contains the command line options as parsed by :class:`optparse.OptionParser` """

    host = NoAttrDict()
    """This will contain the :class:`~naghelp.Host` object. not that it is devrived from a dict."""

    cmd_params = ''
    """Attribute that must contain a list of all possible :class:`~naghelp.Host`
    parameters for the current plugin

    This will automatically add options to the :class:`optparse.OptionParser` object. This means
    that the given parameters can be set at command line (use '-h' for plugin help to see them
    appear).
    This also ask naghelp to get parameters from environment variable or an optional database if
    available. Once the parameters value found, naghelp will store them into the host object at the
    same index.
    For example, if ``plugin.cmd_params = 'user,passwd'`` then parameters values will be available
    at ``self.host.user`` and ``self.host.passwd`` inside the definition of :meth:`collect_data`.

    It is highly recommended to use the following parameters name as their description has been
    already defined by the method :meth:`get_plugin_host_params_tab` :

    ==================  ==================================================
     NAME                DESCRIPTION
    ==================  ==================================================
     name               Hostname
     ip                 Host IP address
     subtype            Plugin subtype (usually host model)
     user               User
     passwd             Password
     console_ip         Console or controller IP address
     snmpversion        SNMP protocal version (1,2 or 3)
     community          SNMP community
     community_alt      SNMP community for other device
     authpp             SNMP authentification passphrase
     authproto          SNMP authentification protocal (md5 or sha)
     privpp             SNMP privacy passphrase
     privproto          SNMP privacy protocal (des or aes)
     protocol           ssh or telnet
     port               Port number
     maxwarn            Gauge max value for a warning status
     maxcrit            Gauge max value for a critical status
     minwarn            Gauge min value for a warning status
     mincrit            Gauge min value for a critical status
     options            Additionnal options
    ==================  ==================================================

    Note that ``name`` and ``ip`` are hard coded :
    you must use them for Nagios hostname and hostaddress.
    The same for ``subtype``, ``protocol`` and ``port`` that are hard coded for port testing.

    The parameter list can be a python list or a coma separated string.

    You can force all your plugin to have some default parameters (like 'name' and 'ip') :
    to do so, use the plugin attribute :attr:`forced_params`.

    .. note::
        **Do not** include the parameters that are not :class:`~naghelp.Host` related (like plugin
        debug mode flag, verbose mode flag, plugin description flag etc...).
        These parameters are already checked by :class:`optparse.OptionParser` and do not need to
        get their value from environment variables or a database.
    """

    required_params = None
    """Attribute that contains the list of parameters required for the :class:`~naghelp.Host` object

    For example, if your plugin need to connect to a host that requires a password,
    you must add 'passwd' in the list.
    The list of possible Host parameters you can add should be keys of the dictionary returned
    by the method :meth:`get_plugin_host_params_tab`.

    At execution time, ``naghelp`` will automatically check the required parameters presence :
    they could come from command line option, environment variable or a database
    (see :class:`naghelp.Host`).

    The parameter list can be a python list or a coma separated string.
    If the list is ``None`` (by default), this means that all parameters from attribute
    :attr:`cmd_params` are required.
    """

    forced_params = 'name,ip'
    """Attribute you can set to force all your plugins to have some default :class:`~naghelp.Host`
    parameters.
    These parameters are automatically added to the plugin attribute :attr:`cmd_params`.

    Default is ``'name,ip'`` because all the monitored equipments must have a Nagios name and an
    IP.
    """

    tcp_ports = ''
    """Attribute that lists the tcp_ports used by the plugin

    naghelp will check specified ports if a problem is detected while collecting data from host.
    naghelp also use this attribute in plugin summary to help administrator to configure their
    firewall.

    The attribute is ignored if the plugin uses the ``protocol`` or ``port`` parameters.

    The ports list can be a python list or a coma separated string.
    """

    udp_ports = ''
    """Attribute that lists the udp_ports used by the plugin

    naghelp uses this attribute in plugin summary to help administrator to configure their
    firewall.

    The attribute is ignored if the plugin uses the ``protocol`` or ``port`` parameters.

    The ports list can be a python list or a coma separated string.
    """

    nagios_status_on_error = CRITICAL
    """Attribute giving the :class:`ResponseLevel` to return to Nagios on error."""

    collected_data_filename_pattern = '/tmp/naghelp/%s_collected_data.json'
    """Attribute giving the pattern for the persistent data file path. ``%s`` will be replaced
    by the monitored host name (or IP if host name not specified)"""

    data = textops.DictExt()
    """The place to put collected and parsed data

    As data is a :class:`textops.DictExt` object, one can use the dotted notation for reading and for
    writing.
    """

    default_level = OK
    """Attribute giving the response level to return if no level has been set.

    By default, naghelp consider that if no level message has been added to the response, there is
    no errors and return the ``OK`` level to Nagios.

    In some situation, one may prefer to send an ``UKNOWN`` state by default.
    """

    def __init__(self):
        self.starttime = datetime.datetime.now()
        self.response = self.response_class(default_level=self.default_level)

    def get_plugin_host_params_tab(self):
        """Returns a dictionary of Host parameters description

        This dictionary helps naghelp to build the plugin help (``-h`` option in command line).

        It is highly recommended to use, in the attribute :attr:`cmd_params`, only keys from this
        dictionary. If it is not the case, a pseudo-description will be calculated when needed.

        If you want to create specific parameters, add them in the dictionary with their description
        by overriding this method in a subclass.
        """
        return  {   'name'           : 'Hostname',
                    'ip'             : 'Host IP address',
                    'subtype'        : 'Plugin subtype (usually host model)',
                    'user'           : 'User',
                    'passwd'         : 'Password',
                    'console_ip'     : 'Console or controller IP address',
                    'snmpversion'    : 'SNMP protocal version (1,2 or 3)',
                    'community'      : 'SNMP community',
                    'community_alt'  : 'SNMP community for other device',
                    'authpp'         : 'SNMP authentification passphrase',
                    'authproto'      : 'SNMP authentification protocal (md5 or sha)',
                    'privpp'         : 'SNMP privacy passphrase',
                    'privproto'      : 'SNMP privacy protocal (des or aes)',
                    'protocol'       : 'ssh or telnet',
                    'port'           : 'Port number',
                    'maxwarn'        : 'Gauge max value for a warning status',
                    'maxcrit'        : 'Gauge max value for a critical status',
                    'minwarn'        : 'Gauge min value for a warning status',
                    'mincrit'        : 'Gauge min value for a critical status',
                    'options'        : 'Additionnal options',
                }

    def get_plugin_host_params_desc(self):
        """Builds a dictionary giving description of plugin host parameters

        This merges :attr:`cmd_params` and :attr:`forced_params` paramters and returns their description
        """
        params_tab = self.get_plugin_host_params_tab()
        cmd_params = self.cmd_params.split(',') if isinstance(self.cmd_params,basestring) else self.cmd_params
        forced_params = self.forced_params.split(',') if isinstance(self.forced_params,basestring) else self.forced_params
        cmd_params = set(cmd_params).union(forced_params)
        return dict([(k,params_tab.get(k,k.title())) for k in cmd_params if k ])

    def init_cmd_options(self):
        """Initialize command line options

        This create :class:`optparse.OptionParser` instance and add some basic options

        It also add options corresponding to Host parameters. The host parameters will be stored
        first into OptionParse's options object (``plugin.options``) at ``host__<parameter>`` attribute, later it is
        set to host object at attribute ``<parameter>``

        This method is automatically called when the plugin is run.
        Avoid to override this method, prefer to customize :meth:`add_cmd_options`
        """
        super(ActivePlugin,self).init_cmd_options()

        host_params_desc = self.get_plugin_host_params_desc()
        if host_params_desc:
            group = OptionGroup(self._cmd_parser, 'Host attributes','To be used to force host attributes values')
            for param,desc in host_params_desc.items():
                group.add_option('--%s' % param, action='store', type='string', dest="host__%s" % param, metavar=param.upper(), help=desc)
            self._cmd_parser.add_option_group(group)

        self._cmd_parser.add_option('-n', action='store_true', dest='in_nagios_env',
                                   default=False, help='Must be used when the plugin is started by nagios')

        collected_data_file = self.collected_data_filename_pattern % '<hostname>'
        self._cmd_parser.add_option('-s', action='store_true', dest='save_collected',
                                   default=False, help='Save collected data in a file')
        self._cmd_parser.add_option('-r', action='store_true', dest='restore_collected',
                                   default=False, help='Use saved collected data (option -s)')
        self._cmd_parser.add_option('-f', action='store', dest='collectfile', metavar="FILE",
                                   help='Collect file path for -s and -r options (Default : %s)' % collected_data_file)
        self._cmd_parser.add_option('-a', action='store_true', dest='collect_and_print',
                                   default=False, help='Collect data only and print them')
        self._cmd_parser.add_option('-b', action='store_true', dest='parse_and_print',
                                   default=False, help='Collect and parse data only and print them')

    def handle_cmd_options(self):
        """Parse command line options

        The parsed options are stored in ``plugin.options`` and arguments in ``plugin.args``

        If the user requests plugin description, it is displayed and the plugin exited
        with UNKOWN response level.

        You should customize this method if you want to check some options before running the
        plugin main part.
        """
        super(ActivePlugin,self).handle_cmd_options()
        if self.options.show_description:
            print self.get_plugin_desc()
            UNKNOWN.exit()

    def fast_response(self,level, synopsis, msg='', sublevel = 1):
        """Exit the plugin at once by sending a basic message level to Nagios

        This is used mainly on errors : the goal is to avoid the plugin to go any further.

        Args:

            level(:class:`ResponseLevel`): Response level to give to Nagios
            synopsis(str): Response title
            msg(str): Message body. Note that it adds a begin message (not a message level).
            sublevel(int): The message sublevel (displayed into plugin information section)
        """
        self.host.save_data()
        self.response.level = level
        self.response.sublevel = sublevel
        self.response.set_synopsis(synopsis)
        self.response.add_begin(msg)
        self.response.add_end(self.get_plugin_informations())
        self.response.send()

    def fast_response_if(self,test, level, synopsis, msg='', sublevel = 1):
        """If test is True, exit the plugin at once by sending a basic message level to Nagios

        This works like :meth:`fast_response` except that it exits only if test is True.

        Args:

            test(bool): Must be True to send response and exit plugin.
            level(:class:`ResponseLevel`): Response level to give to Nagios
            synopsis(str): Response title
            msg(str): Message body. Note that it adds a begin message (not a message level).
            sublevel(int): The message sublevel (displayed into plugin information section)
        """
        if test:
            self.fast_response(level, synopsis, msg='', sublevel = 1)

    def error(self, msg, sublevel=3, exception=None, *args,**kwargs):
        """Log an error and exit the plugin

        Not only it logs an error to console and/or log file, it also send a fast response that
        will exit the plugin. If the exception that has generated the error is not derived
        from CollectError, A stack and available data are also dumped.

        Args:

            msg(str): Message body. Note that it adds a begin message (not a message level).
            sublevel(int): The message sublevel (displayed into plugin information section)
            exception(Exception): The exception that is the error's origin (Optional).
        """
        msg_lines = msg.splitlines()
        synopsis = ''.join(msg_lines[:1])
        body = '\n'.join(msg_lines[1:])
        if exception is None or not isinstance(exception, naghelp.CollectError):
            import traceback
            body += 'traceback : ' + traceback.format_exc() + '\n'
            if self.data:
                body += 'Data = \n%s\n\n' % pp.pformat(self.data).replace('\\n','\n')
        naghelp.logger.error(msg,*args,**kwargs)
        self.fast_response(self.nagios_status_on_error,synopsis,body,sublevel)

    def warning(self,msg,*args,**kwargs):
        """Log a warning and add a warning message level

        Not only it logs a warning to console and/or log file,
        it also add a warning in response's message level section

        Args:

            msg(str): The message to log and add.
        """
        naghelp.logger.warning(msg,*args,**kwargs)
        self.response.add(msg % args,WARNING)

    def save_collected_data(self):
        """Save collected data

        During development and testing, it may boring to wait the data to be collected : The idea
        is to save them once, and then use them many times : This is useful when developing
        :meth:`parse_data` and :meth:`build_response`

        This method is called when using ``-s`` option on command line.
        """
        self.save_data(self.options.collectfile or self.collected_data_filename_pattern % self.host.name, self.data|textops.multilinestring_to_list())

    def restore_collected_data(self):
        """Restore collected data

        During development and testing, it may boring to wait the data to be collected : The idea
        is to save them once, and then use them many times : This is useful when developing
        :meth:`parse_data` and :meth:`build_response`

        This method is called when using ``-r`` option on command line.
        """
        self.data = self.load_data(self.options.collectfile or self.collected_data_filename_pattern % self.host.name) | textops.list_to_multilinestring(in_place=True)

    def get_udp_ports(self):
        """Returns udp ports

        Manages ``port`` host parameter if defined
        """
        if self.host.port:
            if not self.tcp_ports:
                return [self.host.port]
        return self.udp_ports

    def get_tcp_ports(self):
        """Returns tcp ports

        Manages ``port`` and ``protocol`` host parameters if defined
        """
        if self.host.port:
            if not self.udp_ports:
                return [self.host.port]
        if self.host.protocol and 'protocol' in self.cmd_params:
            return [socket.getservbyname(self.host.protocol)]
        return self.tcp_ports

    def check_ports(self):
        """Checks port

        This method is called when an error occurs while collecting data from host : It will check
        whether the tcp ports are reachable or not. If not, the plugin exits with a fast response.
        """
        invalid_port = search_invalid_port(self.host.ip,self.get_tcp_ports())
        if invalid_port:
            self.fast_response(CRITICAL,
                               'Port %s is unreachable' % invalid_port,
                               'This plugin uses ports tcp = %s, udp = %s\nplease check your firewall\n\n' % (self.get_tcp_ports() or 'none',self.get_udp_ports() or 'none'),
                               2)

    def collect_data(self,data):
        """Collect data from monitored host

        This method should be overridden when developing a new plugin.
        One should use :mod:`naghelp.collect` module to retrieve raw data from monitored equipment.
        Do not parse raw data in this method : see :meth:`parse_data`.
        Note that no data is returned : one just have to modify ``data`` with a dotted notation.

        Args:

            data(:class:`textops.DictExt`): the data dictionary to write collected raw data to.

        Example:

            Here we execute the command ``dmesg`` on a remote host via SSH to get last logs::

                def collect_data(self,data):
                    data.syslog = Ssh(self.host.ip,self.host.user,self.host.passwd).run('dmesg')

            See :meth:`parse_data` example to see how data has been parsed.
            See :meth:`build_response` example to see how data will be used.
        """
        pass

    def parse_data(self,data):
        r"""Parse data

        This method should be overridden when developing a new plugin.
        When raw data are not usable at once, one should parse them to structure the informations.
        :meth:`parse_data` will get the data dictionary updated by :meth:`collect_data`.
        One should then use `python-textops <http://python-textops.readthedocs.org>`_ to parse the data.
        There is no data to return : one just have to modify ``data`` with a dotted notation.

        Args:

            data(:class:`textops.DictExt`): the data dictionary to read collected raw data and write
                parsed data.

        Example:

            After getting a raw syslog output, we extract warnings and critical errors::

                def parse_data(self,data):
                    data.warnings  = data.syslog.grepi('EMS Event Notification').grep('MAJORWARNING|SERIOUS')
                    data.criticals = data.syslog.grepi('EMS Event Notification').grep('CRITICAL')

            See :meth:`collect_data` example to see how data has been updated.
            See :meth:`build_response` example to see how data will be used.

        Note:

            The data dictionary is the same for collected data and parsed data, so do not use
            already existing keys for collected data to store new parsed data.
        """
        pass

    def build_response(self,data):
        r"""Build a response

        This method should be overridden when developing a new plugin.
        You must use data dictionary to decide what alerts and/or informations to send to Nagios.
        To do so, a :class:`~naghelp.PluginResponse` object has already been initialized by
        the framework and is available at ``self.response`` : you just have to use `add*` methods.
        It is highly recommended to call the super/parent ``build_response()`` at the end to easily
        take advantage of optional mixins like :class:`naghelp.GaugeMixin`.

        Args:

            data(:class:`textops.DictExt`): the data dictionary where are collected and parsed data

        Example:

            After getting a raw syslog output, we extract warnings and critical errors::

                def build_response(self,data):
                    self.response.add_list(WARNING,data.warnings)
                    self.response.add_list(CRITICAL,data.criticals)
                    ...
                    super(MyPluginClass,self).build_response(data)

            See :meth:`parse_data` and :meth:`collect_data` examples to see how data has been updated.
        """
        pass

    def get_plugin_informations(self):
        r"""Get plugin informations

        This method builds a text giving some informations about the plugin, it will be placed at the
        end of the plugin response.

        Example:

            Here an output::

                >>> p = ActivePlugin()
                >>> print p.get_plugin_informations() #doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
                <BLANKLINE>
                ============================[ Plugin Informations ]=============================
                Plugin name : naghelp.plugin.ActivePlugin
                Description : Python base class for active nagios plugins
                Ports used : tcp = none, udp = none
                Execution time :...
                Exit code : 0 (OK), __sublevel__=0
        """
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
        """Checks host required fields

        This checks the presence of values for host parameters specified in attribute
        :attr:`required_params`. If this attribute is empty, all parameters specified in attribute
        :attr:`cmd_params` will  be considerated as required. The method will also check that either
        `name` or `ip` parameter value is present.
        """
        req_fields = self.required_params if self.required_params is not None else self.cmd_params
        if isinstance(req_fields, basestring):
            req_fields = req_fields.split(',') if req_fields else []
        # either 'name' or 'ip' must be in required params, by default 'ip' is automatically added as required except when 'name' is present
        if 'name' not in req_fields:
            req_fields = set(req_fields + ['ip'])
        for f in req_fields:
            if not self.host.get(f):
                self.fast_response(CRITICAL, 'Missing "%s" parameter' % f, 'Required fields are : %s' % ','.join(req_fields), 3)
                break

    def doctest_begin(self):
        """For doctest usage only"""
        self.host = self.host_class(self)
        self.host.name = 'doctest'
        self.host.load_data()

    def doctest_end(self):
        """For doctest usage only"""
        self.host.save_data()

    def run(self):
        """Run the plugin

        This is the only method to call in your plugin script once you have define your own plugin class.
        It will take care of everything in that order :

            #. Manage command line options (uses :attr:`cmd_params`)
            #. Create the :class:`~naghelp.Host` object (store it in attribute :attr:`host`)
            #. Activate logging (if asked in command line options with ``-v`` or ``-d``)
            #. Load persistent data into :attr:`host`
            #. Collect monitoring informations with :meth:`collect_data`
            #. Check ports if an error occured while collecting data
            #. Parse collected data with :meth:`parse_data`
            #. Build a response with :meth:`build_response`
            #. Save persistent data (save the :attr:`host` object to a json file)
            #. Add plugin information at the response ending
            #. Send the response (render the response to stdout and exit the plugin
               with appropriate exit code)

        """
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
                    msg = 'Failed to collect data : %s\n' % e
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
