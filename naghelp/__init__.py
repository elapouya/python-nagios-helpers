# -*- coding: utf-8 -*-
#
# python-nagios-helpers - Python Nagios plug-in and configuration environment
# Copyright (C) 2015 Eric Lapouyade
#

from collect import telnet_cmd, ssh_cmd
from plugin import ActivePlugin, OK, CRITICAL, WARNING, UNKNOWN
from host import Host
from response import PluginResponse

__version__ = '0.0.2'