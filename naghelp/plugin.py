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
logger = logging.getLogger('naghelp')
import pprint
pprint = pprint.PrettyPrinter(indent=4).pprint


class PluginLevel(object):
    def __init__(self, name, exit_code):
        self.name = name
        self.exit_code = exit_code
    
    def __repr__(self):
        return self.name
    
    def exit(self):
        sys.exit(self.exit_code)

OK       = PluginLevel('OK',0)
WARNING  = PluginLevel('WARNING',1)
CRITICAL = PluginLevel('CRITICAL',2)
UNKNOWN  = PluginLevel('UNKNOWN',3)

class PluginResponse(object):
    def __init__(self):
        self.level = None
        
    def set_level(self, level):
        if not isinstance(level,PluginLevel):
            raise Exception('A plugin level must an instance of PluginLevel, Found level=%s (%s).' % (level,type(level)))
        if self.level in [ None, UNKNOWN ] or level == CRITICAL or self.level == OK and level == WARNING:
            self.level = level
            
    def send(self):
        if self.level is None:
            self.level = UNKNOWN
        
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

class Plugin(object):
    plugin_type = 'abstract'
        
class ActivePlugin(Plugin):
    plugin_type = 'active'
    host_class = Host
    usage = 'usage: \n%prog <hostname> [options]'

    def __init__(self, hostname):
        self.host = host_class(hostname)
        self.response = PluginResponse()
        
    def get_cmd_usage(self):
        return self.usage

    def add_cmd_options(self, parser):
        pass
        
    def manage_cmd_options(self, parser, options, args):
        pass        

    def run(self):
        pass