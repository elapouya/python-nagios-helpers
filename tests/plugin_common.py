# -*- coding: utf-8 -*-
'''
Création : 7 Jan 2016

@author: Eric Lapouyade
'''

from naghelp import *
from textops import *
import json
import os
import sys
import logging
from datetime import datetime, timedelta
from optparse import OptionGroup

PLUGINS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_JSON_FILE = os.path.join(PLUGINS_DIR,'db.json')
HOSTS_PERSISTENT_DIR = os.path.join(PLUGINS_DIR,'hosts')

class MyProjectHost(Host):
    """:class:`naghelp.Host` class has been derived in order to manage a database :
    monitored equipment parameters (IP, login, passwd etc...) are stored in a json file.
    One just have to give the equipment name (``--name=xxx`` in command line), naghelp will get
    all other parameters in json file.
    These parameters are cached into persistent data, so at next plugin execution, the database
    does not need to be read anymore.
    """
    persistent_filename_pattern = os.path.join(HOSTS_PERSISTENT_DIR,'%s','plugin_persistent_data.json')

    def _get_params_from_db(self,hostname):
        params = self._plugin.load_data(self._get_persistent_filename()) or DictExt()
        db_json_file = self._plugin.options.db_json_file or DB_JSON_FILE
        db_file_modif_time = int(os.path.getmtime(db_json_file))
        if db_file_modif_time == params['db_file_modif_time']:
            return params

        db = json.load(open(DB_JSON_FILE))
        db_host = db.get(hostname)
        if db_host:
            params.update(db_host)
            params['db_file_modif_time'] = db_file_modif_time
        return params

class MyProjectPlugin(ActivePlugin):
    """Base class for the project plugins

    All plugins developped for the project must inherit from this class
    """
    abstract = True
    plugin_type = 'my_plugin_active'
    plugins_basedir = PLUGINS_DIR
    plugins_basemodule = 'tests.'
    host_class = MyProjectHost
    collected_data_filename_pattern = '/tmp/naghelp/%s_collected_data.json'
    tcp_ports = ''
    forced_params = 'name,ip,subtype'

    def init_cmd_options(self):
        super(MyProjectPlugin,self).init_cmd_options()

        group = OptionGroup(self._cmd_parser, 'Specific to my project')
        group.add_option('-c', action='store', dest='db_json_file', metavar="FILE",
                                   help='override default path to the db.json file')
        self._cmd_parser.add_option_group(group)

    def handle_cmd_options(self):
        super(MyProjectPlugin,self).handle_cmd_options()