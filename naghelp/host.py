# -*- coding: utf-8 -*-
#
# Création : July 8th, 2015
#
# @author: Eric Lapouyade
"""This module defined the naghelp Host object.

The Host object will store all informations about the equipment to monitor.
It could be for exemple :

    * The hostname
    * Host IP address
    * The user login
    * The user password
    * The snmp community
    * ...

One can add some additional data during the plugin execution, they will be persistent accross
all plugin executions (plugin objects call :meth:`~naghelp.Host.save_data` and
:meth:`~naghelp.Host.load_data` methods). This is useful for :

    * Counters
    * Gauges
    * Timestamps
    * Flags
    * ...

Informations come from 3 sources in this order :

    * From a database ( text file, sqlite, mysql ... )
    * From environment variables
    * From command line

Informations from command line have priority over environment vars which have priority over those
from database.
"""

import os
from textops import DictExt, NoAttr, dformat, pp
import dateutil.parser

__all__ = ['Host']

class Host(dict):
    r"""Contains equipment informations

    Host object is a dict with some additional methods.

    Args:

        plugin (:class:`Plugin`): The plugin object that is used to monitor the equipment


    Informations can be accessed and modified by 2 ways :

        * By attribute
        * By Index

    To save and load custom data, one could do a :meth:`save_data` and :meth:`load_data` but this
    is automatically done by the plugin itself (see :meth:`naghelp.ActivePlugin.run`)

    Examples :

        >>> os.environ['NAGIOS_HOSTNAME']='host_to_be_monitored'
        >>> plugin = ActivePlugin()
        >>> host = Host(plugin)
        >>> print host.name
        host_to_be_monitored
        >>> host.my_custom_data = 'last check time'
        >>> print host.my_custom_data
        last check time
        >>> print host['my_custom_data']
        last check time
        >>> host.save_data()
        >>> host._get_persistent_filename()
        '/tmp/naghelp/host_to_be_monitored_persistent_data.json'
        >>> print open(host._get_persistent_filename()).read() #doctest: +NORMALIZE_WHITESPACE
        {
            "name": "host_to_be_monitored",
            "my_custom_data": "last check time"
        }


        >>> os.environ['NAGIOS_HOSTNAME']='host_to_be_monitored'
        >>> plugin = ActivePlugin()
        >>> host = Host(plugin)
        >>> print host.my_custom_data
        <BLANKLINE>
        >>> host.load_data()
        >>> print host.my_custom_data
        last check time
    """
    persistent_filename_pattern = '/tmp/naghelp/%s_persistent_data.json'
    """Default persistent .json file path pattern (note the %s that will be replaced by the hostname)
    """

    def __init__(self, plugin):
        self._plugin = plugin

        self._params_from_env = self._get_params_from_env()
        self._params_from_cmd_options = self._get_params_from_cmd_options()
        self.set('name', ( self._params_from_cmd_options.get('name') or
                    self._params_from_env.get('name') or
                    self._params_from_cmd_options.get('ip') or
                    self._params_from_env.get('ip') ) )

    def load_data(self):
        """load data to the :class:`Host` object

        That is from database and/or persistent file then from environment variables and then from
        command line.
        """
        self._params_from_db = self._get_params_from_db(self.name)
        self._merge(self._params_from_db)
        self._merge(self._params_from_env)
        self._merge(self._params_from_cmd_options)

    def to_str(self, str, defvalue='-'):
        """Formats a string with Host informations

        Not available data are replaced by a dash

        Args:

            str (str): A format string
            defvalue (str): String to display when a data is not available

        Returns:

            str : the formatted string

        Examples:

            >>> os.environ['NAGIOS_HOSTNAME']='host_to_be_monitored'
            >>> os.environ['NAGIOS_HOSTADDRESS']='192.168.0.33'
            >>> plugin = ActivePlugin()
            >>> host = Host(plugin)
            >>> host.load_data()
            >>> print host.to_str('{name} as got IP={ip} and custom data "{my_custom_data}"')
            host_to_be_monitored as got IP=192.168.0.33 and custom data "last check time"
            >>> print host.to_str('Not available data are replaced by a dash: {other_data}')
            Not available data are replaced by a dash: -
            >>> print host.to_str('Or by whatever you want: {other_data}','N/A')
            Or by whatever you want: N/A

            .. note::

                As you noticed, ``NAGIOS_HOSTNAME`` environment variable is stored as ``name`` in
                Host object and ``NAGIOS_HOSTADDRESS`` as ``ip``.
                ``my_custom_data`` is a persistent data that has been
                automatically loaded because set into a previous example.
        """
        return dformat(str,self,defvalue)

    def to_list(self, lst, defvalue='-'):
        """Formats a list of strings with Host informations

        It works like :meth:`to_str` except that the input is a list of strings : This useful when
        a text has been splitted into lines.

        Args:

            str (str): A format string
            defvalue (str): String to display when a data is not available

        Returns:

            list : The list with formatted string

        Examples:

            >>> os.environ['NAGIOS_HOSTNAME']='host_to_be_monitored'
            >>> os.environ['NAGIOS_HOSTADDRESS']='192.168.0.33'
            >>> plugin = ActivePlugin()
            >>> host = Host(plugin)
            >>> host.load_data()
            >>> lst = ['{name} as got IP={ip} and custom data "{my_custom_data}"',
            ... 'Not available data are replaced by a dash: {other_data}']
            >>> print host.to_list(lst)  # doctest: +NORMALIZE_WHITESPACE
            [u'host_to_be_monitored as got IP=192.168.0.33 and custom data "last check time"',
            'Not available data are replaced by a dash: -']

            .. note::

                As you noticed, ``NAGIOS_HOSTNAME`` environment variable is stored as ``name`` in
                Host object and ``NAGIOS_HOSTADDRESS`` as ``ip``.
                ``my_custom_data`` is a persistent data that has been
                automatically loaded because set into a previous example.
        """
        return [ dformat(l,self) for l in lst ]

    def debug(self):
        """Log Host informations for debug

        Note:

            To see debug on python console, call :func:`naghelp.activate_debug`
        """
        self._plugin.debug('Host informations :')
        self._plugin.debug('_params_from_db = %s', pp.pformat(self._params_from_db))
        self._plugin.debug('_params_from_env = %s',pp.pformat(self._params_from_env))
        self._plugin.debug('_params_from_cmd_options = %s', pp.pformat(self._params_from_cmd_options))
        self._plugin.debug('\n' + '-'*60 + '\n%s\n' + '-'*60, self._pprint())

    def __getattr__(self, name):
        return self.get(name,NoAttr)

    def __setattr__(self, name, value):
        if name[0] != '_':
            self[name] = value
        else:
            super(Host,self).__setattr__(name, value)

    def get(self, name, default=NoAttr):
        return super(Host,self).get(name,default)

    def get_datetime(self, name, default):
        val = self.get(name)
        if not val:
            return default
        if isinstance(val,basestring):
            return dateutil.parser.parse(val)
        return val

    def set(self, name, value):
        self[name] = value

    def delete(self, name):
        if name in self:
            del self[name]
            return True
        return False

    def _merge(self,dct):
        self.update([ (k,v) for k,v in dct.items() if v not in [None,NoAttr] ])

    def _get_env_to_param(self):
        """Returns a dict for the environment variable to extract

        The keys are the environment variables to extract, the values are the attribute name to use
        for the Host object.

        Only a few environment variables are automatically extracted, they are renamed when saved into
        Host object :

            =====================  =========
            Environment Variables  Stored as
            =====================  =========
            NAGIOS_HOSTNAME        name
            NAGIOS_HOSTALIAS       alias
            NAGIOS_HOSTADDRESS     ip
            NAGIOS_HOSTGROUPNAMES  groups
            NAGIOS_HOSTGROUPNAME   group
            =====================  =========
        """
        return {
           'NAGIOS_HOSTNAME'        : 'name',
           'NAGIOS_HOSTALIAS'       : 'alias',
           'NAGIOS_HOSTADDRESS'     : 'ip',
           'NAGIOS_HOSTGROUPNAMES'  : 'groups',
           'NAGIOS_HOSTGROUPNAME'   : 'group',
        }

    def _get_params_from_env(self):
        dct = dict([(k[8:].lower(),v) for k,v in os.environ.items() if k.startswith('NAGIOS__') ])
        for e,p in self._get_env_to_param().items():
            v = os.environ.get(e)
            if v is not None:
                dct[p] = v
        return dct

    def _get_params_from_db(self,hostname):
        """Get host informations from database

        Getting informations from a database is optionnal. If needed, it is the developer
        responsibility to subclass ``Host`` class and redefine the method ``_get_params_from_db(hostname)``
        that returns a dict with informations about ``hostname``. In this method, the developer must
        also load persistent data that may come from a same cache file as the database.
        The default behaviour for this method is only to load persistent data from
        a database flat file (.json).

        Args:

            hostname (str): The name of the equipment as declared in Nagios configuration files.

        Returns:

            dict : A dictionary that contains equipment informations AND persistent data merged.

        Example:

            Here is an example of :meth:`_get_params_from_db` override where informations about a monitored
            host are stored in a json file located at DB_JSON_FILE ::

                class MonitoredHost(Host):
                    def _get_params_from_db(self,hostname):
                        # The first step MUST be to read the persistent data file ( = cache file )
                        params = self._plugin.load_data(self._get_persistent_filename()) or DictExt()

                        # Check whether the database file has changed
                        db_file_modif_time = int(os.path.getmtime(DB_JSON_FILE))
                        if db_file_modif_time == params['db_file_modif_time']:
                            # if not, return the cached data
                            return params

                        # If database file has changed :
                        db = json.load(open(DB_JSON_FILE))
                        # find hostname in db :
                        for h in db.monitored_hosts:
                            if h['datas']['hostname'] == hostname:
                                # merge the new data into the persistent data dict (will be cached)
                                params.update(h.datas)
                                params['db_file_modif_time'] = db_file_modif_time
                                params['name'] = params.get('hostname','noname')
                                return params
                        return params

            .. Note::
                You can do about the same for SQlite or MySQL, do not forget to load persistent
                data file as a first step and merge data from database after. Like the above
                example, you can use the persistent data json file as a cache for your database.
                By this way, persistent data AND database data are saved in the same file within a
                single operation. The dictionary returned by this method will be saved automatically
                by the :meth:`naghelp.ActivePlugin.run` method as persistent data.
        """
        return self._plugin.load_data(self._get_persistent_filename()) or DictExt()

    def _get_params_from_cmd_options(self):
        return dict([(k[6:],v) for k,v in vars(self._plugin.options).items() if k.startswith('host__')])

    def _pprint(self):
        lst = []
        for k,v in sorted(self.items()):
            if isinstance(v,str):
                v = v.decode('utf-8','replace')
                lst.append(u'%-12s : %s' % (k,v))
        return u'\n'.join(lst)

    def _get_persistent_filename(self):
        """Get the full path for the persisten .json file

        It uses :attr:`persistent_filename_pattern` to get the file pattern, and apply the hostname
        to build the full path.
        """
        return self.persistent_filename_pattern % self.name

    def save_data(self):
        """Save data to a persistent place

        It actually saves the whole dict into a .json file.
        This is automatically called by the :meth:naghelp.ActivePlugin.run method.
        """
        self._plugin.save_data(self._get_persistent_filename(), self)
