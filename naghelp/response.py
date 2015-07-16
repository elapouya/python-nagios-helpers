# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

import sys

class ResponseLevel(object):
    def __init__(self, name, exit_code):
        self.name = name
        self.exit_code = exit_code

    def __repr__(self):
        return self.name

    def exit(self):
        sys.exit(self.exit_code)

OK       = ResponseLevel('OK',0)
WARNING  = ResponseLevel('WARNING',1)
CRITICAL = ResponseLevel('CRITICAL',2)
UNKNOWN  = ResponseLevel('UNKNOWN',3)

class PluginResponse(object):
    def __init__(self):
        self.level = None
        self.synopsis = None
        self.level_msgs = { OK:[], WARNING:[], CRITICAL:[], UNKNOWN:[] }
        self.begin_msgs = []
        self.end_msgs = []

    def set_level(self, level):
        if not isinstance(level,ResponseLevel):
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))
        if self.level in [ None, UNKNOWN ] or level == CRITICAL or self.level == OK and level == WARNING:
            self.level = level

    def add(self,msg,level=None):
        if level is None:
            self.begin_msgs.append(msg)
        elif isinstance(level,ResponseLevel):
            self.level_msgs[level].append(msg)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_if(self,test,msg,level=None):
            if test:
                self.add(msg,level)

    def add_end(self,msg):
        self.begin_msgs.append(msg)

    def set_synopsis(self,msg):
        self.synopsis = msg

    def get_default_synopsis(self):
        nb_ok = len(self.level_msgs[OK])
        nb_nok = len(self.level_msgs[WARNING]) + len(self.level_msgs[CRITICAL]) + len(self.level_msgs[UNKNOWN])
        if nb_ok + nb_nok == 0:
            return self.level
        if nb_ok and not nb_nok:
            return OK
        return ', '.join([ '%s:%s' % (level,len(msgs)) for level,msgs in self.level_msgs.items() if msgs ])

    def level_msgs_render(self):
        out = '\n'
        for level in [CRITICAL, WARNING, UNKNOWN ]:
            msgs = self.level_msgs[level]
            if msgs:
                out += '%s :\n--------------------------------\n'
                out += '\n'.join(msgs)
                out += '\n'
        return out

    def send(self):
        if self.level is None:
            self.level = UNKNOWN
        if self.synopsis is None:
            self.synopsis = self.get_default_synopsis()

        out = self.synopsis + '\n'
        out += '\n'.join(self.begin_msgs)
        out += self.level_msgs_render()
        out += '\n'.join(self.end_msgs)

        print out
        self.level.exit()