# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

class Host(object):
    def __init__(self, cmd_options):
        self._params = dict([(k[7:],v) for k,v in os.environ.items() if k.startswith('NAGIOS_') and v ])
        self._params['hostname'] = self._params.get('HOSTNAME')
        self._params['ip'] = self._params.get('HOSTADDRESS')
        self._params.update(self._get_params_from_db())
        self._params.update(vars(cmd_options))

    def __getattr__(self, name):
        return self._params.get(name)

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            object.__setattr__(self, name, value)
        else:
            self._params[name] = value

    def _get_params_from_db(self):
        return {}

    def __repr__(self):
        return '\n'.join([ '%s : %s' % (k,v) for k,v in self._params.items() ])