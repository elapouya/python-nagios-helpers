# -*- coding: utf-8 -*-
'''
Création : July 8th, 2015

@author: Eric Lapouyade
'''

import sys
import naghelp
from types import NoneType
import re

__all__ = [ 'ResponseLevel', 'PluginResponse', 'OK', 'WARNING', 'CRITICAL', 'UNKNOWN' ]

class ResponseLevel(object):
    def __init__(self, name, exit_code):
        self.name = name
        self.exit_code = exit_code

    def __repr__(self):
        return self.name

    def info(self):
        return '%s (exit_code=%s)' % (self.name,self.exit_code)

    def exit(self):
        sys.exit(self.exit_code)

OK       = ResponseLevel('OK',0)
WARNING  = ResponseLevel('WARNING',1)
CRITICAL = ResponseLevel('CRITICAL',2)
UNKNOWN  = ResponseLevel('UNKNOWN',3)

class PluginResponse(object):
    def __init__(self):
        self.level = None
        self.sublevel = 0
        self.synopsis = None
        self.level_msgs = { OK:[], WARNING:[], CRITICAL:[], UNKNOWN:[] }
        self.begin_msgs = []
        self.end_msgs = []
        self.perf_items = []

    def set_level(self, level):
        if not isinstance(level,ResponseLevel):
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))
        if self.level in [ None, UNKNOWN ] or level == CRITICAL or self.level == OK and level == WARNING:
            self.level = level

    def set_sublevel(self, sublevel):
        if not isinstance(level,int):
            raise Exception('A response sublevel must be an integer')
        self.sublevel = sublevel

    def add_begin(self,msg):
        if not isinstance(msg,basestring):
            msg = str(msg)
        self.begin_msgs.append(msg)

    def add(self,level,msg):
        if not isinstance(msg,basestring):
            msg = str(msg)
        if isinstance(level,ResponseLevel):
            self.level_msgs[level].append(msg)
            self.set_level(level)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_if(self,test,level,msg):
        if not isinstance(msg,basestring):
            msg = str(msg)
        if isinstance(level,ResponseLevel):
            if test:
                self.add(level,msg)
                self.set_level(level)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_elif(self,*add_ifs):
        for test,level,msg in add_ifs:
            if not isinstance(msg,basestring):
                msg = str(msg)
            if isinstance(level,ResponseLevel):
                if test:
                    self.add(level,msg)
                    self.set_level(level)
                    break
            else:
                raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_end(self,msg):
        if not isinstance(msg,basestring):
            msg = str(msg)
        self.end_msgs.append(msg)


    def add_perf_data(self,data):
        if not isinstance(data,basestring):
            data = str(data)
        self.perf_items.append(data)

    def set_synopsis(self,msg):
        if not isinstance(msg,basestring):
            msg = str(msg)
        self.synopsis = msg

    def get_default_synopsis(self):
        nb_ok = len(self.level_msgs[OK])
        nb_nok = len(self.level_msgs[WARNING]) + len(self.level_msgs[CRITICAL]) + len(self.level_msgs[UNKNOWN])
        if nb_ok + nb_nok == 0:
            return str(self.level)
        if nb_ok and not nb_nok:
            return str(OK)
        if nb_nok == 1:
            return re.sub(r'^(.{75}).*$', '\g<1>...',(self.level_msgs[WARNING] + self.level_msgs[CRITICAL] + self.level_msgs[UNKNOWN])[0])
        return 'STATUS : ' + ', '.join([ '%s:%s' % (level,len(self.level_msgs[level])) for level in [CRITICAL, WARNING, UNKNOWN, OK ] if self.level_msgs[level] ])

    def section_format(self,title):
        return '{:=^80}'.format('[ {:^8} ]'.format(title))

    def subsection_format(self,title):
        return '----' + '{:-<76}'.format('( %s )' % title)

    def level_msgs_render(self):
        out = self.section_format('STATUS') + '\n'
        for level in [CRITICAL, WARNING, UNKNOWN, OK ]:
            msgs = self.level_msgs[level]
            if msgs:
                out += '\n'
                out += self.subsection_format(level) + '\n'
                out += '\n'.join(msgs)
                out += '\n'
        else:
            out += '\nNo error detected\n'
        out += '\n'
        return out

    def sublevel_render(self):
        out = self.section_format('Exit code') + '\n'
        out += 'The plugin returned : %s, __sublevel__=%s\n\n' % (self.level.info(),self.sublevel)
        return out

    def escape_msg(self,msg):
        return msg.replace('|','!')

    def get_output(self):
        if self.synopsis is None:
            synopsis = self.get_default_synopsis()

        out = self.escape_msg(synopsis)
        out +=  '|%s' % self.perf_items[0] if self.perf_items else '\n'

        body = '\n'.join(self.begin_msgs)
        body += self.level_msgs_render()
        body += self.sublevel_render()
        body += '\n'.join(self.end_msgs)

        out += self.escape_msg(body)
        out +=  '|%s' % '\n'.join(self.perf_items[1:]) if len(self.perf_items)>1 else ''
        return out

    def __str__(self):
        return self.get_output()

    def send(self, level=None, synopsis='', msg='', default_level = None, sublevel = None):
        if isinstance(level,ResponseLevel):
            if synopsis:
                self.synopsis = synopsis
                if level:
                    self.set_level(level)
            if msg:
                self.add(level,msg)

        if self.level is None:
            self.level = default_level or UNKNOWN

        if sublevel is not None:
            self.set_sublevel(sublevel)

        naghelp.logger.info('Plugin output summary : %s' % self.synopsis)

        out = self.get_output()

        naghelp.logger.debug('Plugin output :\n' + '#' * 80 + '\n' + out + '\n'+ '#' * 80)

        print out

        naghelp.logger.info('Exiting plugin with response level : %s' % self.level.info())
        self.level.exit()