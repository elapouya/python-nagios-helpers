# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

import os

class Host(object):

    def __init__(self, plugin):
        self._plugin = plugin
        _params_from_env = self._get_params_from_env()
        _params_from_cmd_options = self._get_params_from_cmd_options()
        _hostname = _params_from_cmd_options.get('host__name') or _params_from_env.get('name')
        self._params = _params_from_env
        if _hostname:
            self._params.update(self._get_params_from_db(_hostname))
        self._params.update(self._get_params_from_cmd_options())

    def __getattr__(self, name):
        return self._params.get(name)

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            object.__setattr__(self, name, value)
        else:
            self._params[name] = value

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
        return {}

    def _get_params_from_cmd_options(self):
        return dict([(k[6:],v) for k,v in vars(self._plugin.options).items() if k.startswith('host__')])

    def __repr__(self):
        return '\n'.join([ '%-12s : %s' % (k,v) for k,v in self._params.items() ])