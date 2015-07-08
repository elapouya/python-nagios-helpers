# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

import logging
logger = logging.getLogger('naghelp')
import pprint
pprint = pprint.PrettyPrinter(indent=4).pprint

class Host(object):
    def __init__(self, hostname):
        self._hostname = hostname
        self._params = self._get_params_from_db()
             
    def __getattr__(self, name):
        return self._params.get(name)    
     
    def __setattr__(self, name, value):
        if not hasattr(self, name):
            object.__setattr__(self, name, value)
        else:
            self._params[name] = value
            
    def _get_params_from_db(self):
        return {}