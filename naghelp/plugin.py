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
import pprint
from .host import Host
from .response import PluginResponse, OK, WARNING, CRITICAL, UNKNOWN 

logger = logging.getLogger('naghelp')
pprint = pprint.PrettyPrinter(indent=4).pprint

class Plugin(object):
    plugin_type = 'abstract'
        
class ActivePlugin(Plugin):
    plugin_type = 'active'
    host_class = Host
    response_class = PluginResponse
    usage = 'usage: \n%prog <hostname> [options]'

    def __init__(self, hostname):
        self.host = host_class(hostname)
        self.response = response_class()
        
    def get_cmd_usage(self):
        return self.usage

    def add_cmd_options(self, parser):
        pass
        
    def manage_cmd_options(self, parser, options, args):
        pass        

    def run(self):
        pass