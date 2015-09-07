# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

import os
from textops import DictExt,NoAttr
import dateutil.parser

__all__ = ['Host']

class Host(object):
    persistent_filename_pattern = '/tmp/naghelp/%s_persistent_data.json'

    def __init__(self, plugin):
        self._plugin = plugin
        self._params = {}

        self._params_from_env = self._get_params_from_env()
        self._params_from_cmd_options = self._get_params_from_cmd_options()
        self.set('name', ( self._params_from_cmd_options.get('name') or
                    self._params_from_env.get('name') or
                    self._params_from_cmd_options.get('ip') or
                    self._params_from_env.get('ip') ) )
        self._params_from_db = self._get_params_from_db(self.name)

        self._merge(self._params_from_db)
        self._merge(self._params_from_env)
        self._merge(self._params_from_cmd_options)
        
    def get_fields(self):
        return self._params

    def debug(self):
        import pprint
        pp = pprint.PrettyPrinter(indent=4)

        self._plugin.debug('Host informations :')
        self._plugin.debug('_params_from_db = %s', pp.pformat(self._params_from_db))
        self._plugin.debug('_params_from_env = %s',pp.pformat(self._params_from_env))
        self._plugin.debug('_params_from_cmd_options = %s', pp.pformat(self._params_from_cmd_options))
        self._plugin.debug('\n' + '-'*60 + '\n%r\n' + '-'*60, self)

    def __getattr__(self, name):
        return self._params.get(name,NoAttr)

    def get(self, name, default=NoAttr):
        return self._params.get(name,default)

    def get_datetime(self, name, default):
        val = self._params.get(name)
        if not val:
            return default
        if isinstance(val,basestring):
            return dateutil.parser.parse(val)
        return val

    def set(self, name, value):
        self._params[name] = value

    def delete(self, name):
        if name in self._params:
            del self._params[name]
            return True
        return False

    def _merge(self,dct):
        self._params.update([ (k,v) for k,v in dct.items() if v not in [None,NoAttr] ])

    def _get_env_to_param(self):
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
        return self._plugin.load_data(self._get_persistent_filename()) or DictExt()

    def _get_params_from_cmd_options(self):
        return dict([(k[6:],v) for k,v in vars(self._plugin.options).items() if k.startswith('host__')])

    def __repr__(self):
        return '\n'.join([ '%-12s : %s' % (k,v) for k,v in sorted(self._params.items()) ])

    def _get_persistent_filename(self):
        return self.persistent_filename_pattern % self.name

    def save_persistent_data(self):
        self._plugin.save_data(self._get_persistent_filename(), self._params)
