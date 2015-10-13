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
    def __init__(self,default_level):
        self.level = None
        self.default_level = default_level
        self.sublevel = 0
        self.synopsis = None
        self.level_msgs = { OK:[], WARNING:[], CRITICAL:[], UNKNOWN:[] }
        self.begin_msgs = []
        self.more_msgs = []
        self.end_msgs = []
        self.perf_items = []

    def set_level(self, level):
        if not isinstance(level,ResponseLevel):
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))
        if self.level in [ None, UNKNOWN ] or level == CRITICAL or self.level == OK and level == WARNING:
            self.level = level

    def get_current_level(self):
        return self.default_level if self.level is None else self.level

    def set_sublevel(self, sublevel):
        if not isinstance(sublevel,int):
            raise Exception('A response sublevel must be an integer')
        self.sublevel = sublevel

    def _reformat_msg(self,msg,*args,**kwargs):
        if isinstance(msg,(list,tuple)):
            msg = '\n'.join(msg)
        elif not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
        return msg

    def add_begin(self,msg,*args,**kwargs):
        self.begin_msgs.append(self._reformat_msg(msg,*args,**kwargs))

    def add(self,level,msg,*args,**kwargs):
        if isinstance(level,ResponseLevel):
            self.level_msgs[level].append(self._reformat_msg(msg,*args,**kwargs))
            self.set_level(level)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_list(self,level,msg_list,*args,**kwargs):
        for msg in msg_list:
            if msg:
                self.add(level, msg,*args,**kwargs)

    def add_many(self,lst,*args,**kwargs):
        for level,msg in lst:
            self.add(level, msg,*args,**kwargs)

    def add_if(self, test, level, msg=None, *args,**kwargs):
        if msg is None:
            msg = test
        if isinstance(level,ResponseLevel):
            if test:
                self.add(level,msg,*args,**kwargs)
                self.set_level(level)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_elif(self,*add_ifs,**kwargs):
        for test,level,msg in add_ifs:
            if msg is None:
                msg = test
            if isinstance(level,ResponseLevel):
                if test:
                    self.add(level,msg,**kwargs)
                    self.set_level(level)
                    break
            else:
                raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_more(self,msg,*args,**kwargs):
        if isinstance(msg,(list,tuple)):
            msg = '\n'.join(msg)
        elif not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
        self.more_msgs.append(msg)

    def add_end(self,msg,*args,**kwargs):
        if isinstance(msg,(list,tuple)):
            msg = '\n'.join(msg)
        elif not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
        self.end_msgs.append(msg)


    def add_perf_data(self,data):
        if not isinstance(data,basestring):
            data = str(data)
        self.perf_items.append(data)

    def set_synopsis(self,msg,*args,**kwargs):
        if not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
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
        return '{0:=^80}'.format('[ {0:^8} ]'.format(title))

    def subsection_format(self,title):
        return '----' + '{0:-<76}'.format('( %s )' % title)

    def level_msgs_render(self):
        out = self.section_format('STATUS') + '\n'
        have_status = False
        for level in [CRITICAL, WARNING, UNKNOWN, OK ]:
            msgs = self.level_msgs[level]
            if msgs:
                have_status = True
                out += '\n'
                out += self.subsection_format(level) + '\n'
                out += '\n'.join(msgs)
                out += '\n'

        if not have_status:
            return ''
        out += '\n'
        return out

    def escape_msg(self,msg):
        return msg.replace('|','!')

    def get_output(self):
        synopsis = self.synopsis or self.get_default_synopsis()
        synopsis = synopsis.splitlines()[0]
        synopsis = synopsis[:75] + ( synopsis[75:] and '...' )

        out = self.escape_msg(synopsis)
        out +=  '|%s' % self.perf_items[0] if self.perf_items else '\n'

        body = '\n'.join(self.begin_msgs)
        body += self.level_msgs_render()
        if self.more_msgs:
            body += self.section_format('Additionnal informations') + '\n'
            body += '\n'.join(self.more_msgs)
        body += '\n'.join(self.end_msgs)

        out += self.escape_msg(body)
        out +=  '|%s' % '\n'.join(self.perf_items[1:]) if len(self.perf_items)>1 else ''
        return out

    def __str__(self):
        return self.get_output()

    def send(self, level=None, synopsis='', msg='', sublevel = None):
        if isinstance(level,ResponseLevel):
            self.set_level(level)
        if self.level is None:
            self.level = self.default_level or UNKNOWN
        if synopsis:
            self.synopsis = synopsis
        if msg:
            self.add(level,msg)
        if sublevel is not None:
            self.set_sublevel(sublevel)

        naghelp.logger.info('Plugin output summary : %s' % self.synopsis)

        out = self.get_output()

        naghelp.logger.debug('Plugin output :\n' + '#' * 80 + '\n' + out + '\n'+ '#' * 80)

        print out

        naghelp.logger.info('Exiting plugin with response level : %s, __sublevel__=%s', self.level.info(), self.sublevel )
        self.level.exit()
