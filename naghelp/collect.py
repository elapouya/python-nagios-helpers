# -*- coding: utf-8 -*-
'''
Création : July 7th, 2015

@author: Eric Lapouyade
'''

import re
import socket
import signal
from addicted import NoAttr
import textops
import naghelp

__all__ = ['search_invalid_port', 'runsh', 'mrunsh', 'Expect', 'Telnet', 'Ssh', 'Snmp', 'SnmpError', 'Timeout', 'TimeoutError']

class NotConnected(Exception):
    pass

class ConnectionError(Exception):
    pass

class CollectError(Exception):
    pass

class TimeoutError(Exception):
    pass

class Timeout:
    """ usage exemple :

    with timeout(seconds=3):
        time.sleep(4)
    """
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)

def search_invalid_port(ip,ports):
    """Returns the first invalid port encountered or None if all are reachable"""
    if isinstance(ports, basestring):
        ports = [ int(n) for n in ports.split(',') ]
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((ip, port))
            s.close()
        except:
            return port
    return None

def runsh(cmd,timeout = 30):
    with Timeout(seconds=timeout, error_message='Timeout (%ss) for command : %s' % (timeout,cmd)):
        return textops.run(cmd).l

def mrunsh(cmds,cmd_timeout = 30, total_timeout = 60):
    with Timeout(seconds=total_timeout, error_message='Timeout (%ss) for mrunsh commands : %s' % (total_timeout,cmds)):
        dct = textops.DictExt()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            dct[k] = runsh(cmd,cmd_timeout)
        return dct

class Expect(object):
    KILL = 1
    BREAK = 2
    RESPONSE = 3

    def __init__(self,spawn,login_steps,prompt,logout_steps=None,context={},timeout = 30,*args,**kwargs):
        global pexpect

        #import is done only on demand, because it takes some little time
        import pexpect
        self.in_with = False
        self.is_connected = False
        self.spawn = spawn
        self.prompt = prompt
        self.logout_steps = logout_steps
        self.context = context
        self.timeout = timeout
        with Timeout(seconds = timeout, error_message='Timeout (%ss) for pexpect : %s' % (timeout,spawn)):
            self.child = pexpect.spawn(spawn)
            naghelp.logger.debug('==== Login steps up to the prompt =====')
            error_msg = self._expect_steps( login_steps + ((prompt,None),) )
            if error_msg:
                raise ConnectionError(error_msg)
            self.is_connected = True

    def _expect_pattern_rewrite(self,pat):
        pat = re.sub(r'^\^',r'[\r\n]',pat)
        return pat

    def _expect_steps(self,steps):
        step = 0
        nb_steps = len(steps)
        infinite_loop_detect = 0
        while step < nb_steps:
            naghelp.logger.debug('--------- STEP #%s--------------------------',step)
            expects = steps[step]
            # normalizing : transform tuple of string into tuple of tuples of string
            if isinstance(expects[0],basestring):
                expects = (expects,)
            nb_base_expects = len(expects)
            if nb_base_expects == 1 and expects[0][0] is None:
                found = 0
                patterns = []
            else:
                if step+1 < nb_steps:
                    next_expects = steps[step+1]
                    if isinstance(next_expects[0],basestring):
                        next_expects = (next_expects,)
                    expects += next_expects
                patterns = [ self._expect_pattern_rewrite(e[0]) for e in expects ]
                naghelp.logger.debug('<-- expect(%s) ...',patterns)
                try:
                    found = self.child.expect(patterns)
                except pexpect.EOF:
                    naghelp.logger.debug('CollectError : No more data (EOF) from %s' % self.spawn)
                    raise CollectError('No more data (EOF) from %s' % self.spawn)
                naghelp.logger.debug('  --> found : "%s"',patterns[found])
            to_send = expects[found][1]
            if to_send is not None:
                if isinstance(to_send,basestring):
                    to_send = to_send.format(**self.context)
                    if to_send and to_send[-1] == '\n':
                        naghelp.logger.debug('  ==> sendline : %s',to_send[:-1])
                        self.child.sendline(to_send[:-1])
                    else:
                        naghelp.logger.debug('  ==> send : %s',to_send)
                        self.child.send(to_send)
                elif to_send == Expect.KILL:
                    return_msg = self.child.before+'.'
                    self.child.kill(0)
                    return return_msg
                elif to_send == Expect.BREAK:
                    break
                elif to_send == Expect.RESPONSE:
                    return_msg = self.child.before+'.'
                    return return_msg
            if found >= nb_base_expects:
                step += 1
                infinite_loop_detect = 0
                if step == nb_steps - 1:
                    break
            infinite_loop_detect += 1
            if infinite_loop_detect > 10:
                naghelp.logger.debug('Too many expect for %s',patterns)
                raise CollectError('Too many expect for %s' % patterns)

        naghelp.logger.debug('FINISHED steps')
        return ''

    def __enter__(self):
        self.in_with = True
        return self

    def __exit__(self, type, value, traceback):
        self.in_with = False
        self.close()

    def close(self):
        if not self.in_with:
            self.is_connected = False
            if self.logout_steps:
                self._expect_steps(self.logout_steps)
            self.child.kill(0)

    def _run_cmd(self,cmd):
        naghelp.logger.debug('  ==> sendline : %s',cmd)
        self.child.sendline('%s' % cmd)
        naghelp.logger.debug('<-- expect prompt ...')
        try:
            self.child.expect(self._expect_pattern_rewrite(self.prompt))
        except pexpect.EOF:
            naghelp.logger.debug('CollectError : No more data (EOF) from %s' % self.spawn)
            raise CollectError('No more data (EOF) from %s' % self.spawn)
        out = self.child.before
        out = re.sub(r'%s[\r\n]*' % cmd, '', out)
        out = re.sub(r'[\r\n]*$', '', out)
        out = out.replace('\r','')
        return out

    def run(self, cmd, timeout=30, auto_close=True, **kwargs):
        if not self.is_connected:
            raise NotConnected('No expect connection to run your command.')
        out = None
        try:
            with Timeout(seconds = timeout):
                out = self._run_cmd(cmd)
        except TimeoutError:
            pass
        if auto_close:
            self.close()
        return out

    def mrun(self, cmds, timeout=30, auto_close=True, **kwargs):
        if not self.is_connected:
            raise NotConnected('No expect connection to run your command.')
        dct = textops.DictExt()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            try:
                with Timeout(seconds = timeout):
                    output = self._run_cmd(cmd)
                    if k:
                        dct[k] = output
            except TimeoutError:
                dct[k] = None
        if auto_close:
            self.close()
        return dct

class Telnet(object):
    def __init__(self,host, user, password=None, timeout=30, port=0, login_pattern_list=None, passwd_pattern_list=None, prompt_pattern=None,*args,**kwargs):
        #import is done only on demand, because it takes some little time
        import telnetlib
        self.in_with = False
        self.is_connected = False
        self.prompt = None
        if login_pattern_list is None:
            login_pattern_list = [re.compile(r'login\s*:',re.I),]
        if passwd_pattern_list is None:
            passwd_pattern_list = [re.compile(r'Password\s*:',re.I),]
        if prompt_pattern is None:
            prompt_pattern_list = [re.compile(r'[\r\n][^\$#<>:]*[\$#>:]'),]
        else:
            prompt_pattern_list = [re.compile(prompt_pattern,re.M)]
        self.prompt_pattern_list = prompt_pattern_list
        with Timeout(seconds = timeout, error_message='Timeout (%ss) for telnet to %s' % (timeout,host)):
            self.tn = telnetlib.Telnet(host,port,timeout,**kwargs)
            self.tn.expect(login_pattern_list)
            self.tn.write(user + "\n")
            self.tn.expect(passwd_pattern_list)
            self.tn.write(password + "\n")
            pat_id,m,buffer = self.tn.expect(prompt_pattern_list)
            if pat_id < 0:
                raise ConnectionError('No regular prompt found.')
            self.is_connected = True

    def __enter__(self):
        self.in_with = True
        return self

    def __exit__(self, type, value, traceback):
        self.in_with = False
        self.close()

    def close(self):
        if not self.in_with:
            self.tn.close()
            self.is_connected = False

    def _run_cmd(self,cmd):
        self.tn.write('%s\n' % cmd)
        pat_id,m,buffer = self.tn.expect(self.prompt_pattern_list)
        out = buffer.splitlines()[1:-1]
        return '\n'.join(out)

    def run(self, cmd, timeout=30, auto_close=True, **kwargs):
        if not self.is_connected:
            raise NotConnected('No telnet connection to run your command.')
        out = None
        try:
            with Timeout(seconds = timeout):
                out = self._run_cmd(cmd)
        except TimeoutError:
            pass
        if auto_close:
            self.close()
        return out

    def mrun(self, cmds, timeout=30, auto_close=True, **kwargs):
        if not self.is_connected:
            raise NotConnected('No telnet connection to run your command.')
        dct = textops.DictExt()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            try:
                with Timeout(seconds = timeout):
                    output = self._run_cmd(cmd)
                    if k:
                        dct[k] = output
            except TimeoutError:
                dct[k] = None
        if auto_close:
            self.close()
        return dct

class Ssh(object):
    def __init__(self,host, user, password=None, timeout=30, auto_accept_new_host=True, *args,**kwargs):
        #import is done only on demand, because it takes some little time
        import paramiko
        self.in_with = False
        self.is_connected = False
        self.client = paramiko.SSHClient()
        if auto_accept_new_host:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.load_system_host_keys()
        self.client.connect(host,username=user,password=password, timeout=timeout, **kwargs)
        self.is_connected = True

    def __enter__(self):
        self.in_with = True
        return self

    def __exit__(self, type, value, traceback):
        self.in_with = False
        self.close()

    def close(self):
        if not self.in_with:
            self.client.close()
            self.is_connected = False

    def run(self, cmd, timeout=30, auto_close=True, **kwargs):
        if not self.is_connected:
            raise NotConnected('No ssh connection to run your command.')
        out = None
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd,timeout=timeout)
            out = stdout.read()
        except socket.timeout:
            pass
        if auto_close:
            self.close()
        return out

    def mrun(self, cmds, timeout=30, auto_close=True, **kwargs):
        if not self.is_connected:
            raise NotConnected('No ssh connection to run your command.')
        dct = textops.DictExt()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd,timeout=timeout)
                if k:
                    dct[k] = stdout.read()
                    dct['%s_err' % k] = stderr.read()
            except socket.timeout:
                if k:
                    dct[k] = None
                    dct['%s_err' % k] = None
        if auto_close:
            self.close()
        return dct

class SnmpError(Exception):
    pass

class Snmp(object):
    def __init__(self,host, community='public', version=None, timeout=30, port=161, user=None,
                 auth_passwd=None, auth_protocol='', priv_passwd=None, priv_protocol='', *args,**kwargs):
        #import is done only on demand, because it takes some little time
        from pysnmp.entity.rfc3413.oneliner import cmdgen
        from pysnmp.proto.api import v2c
        from pysnmp.smi.exval import noSuchInstance
        self.cmdgen = cmdgen
        self.v2c = v2c
        self.noSuchInstance = noSuchInstance
        self.cmdGenerator = cmdgen.CommandGenerator()
        self.version = version
        self.cmd_args = []

        if not version:
            version = user and 3 or 2

        if version == 1:
            self.cmd_args.append(cmdgen.CommunityData(community, mpModel=0))
        elif version in  [2,'2c']:
            self.cmd_args.append(cmdgen.CommunityData(community))
        elif version == 3:
            authProtocol = None
            privProtocol = None
            if auth_passwd and auth_protocol.lower() == 'sha':
                 authProtocol = cmdgen.usmHMACSHAAuthProtocol
            if priv_passwd and auth_protocol.lower() == 'aes':
                 privProtocol = cmdgen.usmAesCfb128Protocol
            if not auth_passwd:
                auth_passwd = None
            if not priv_passwd:
                priv_passwd = None
            if not user:
                raise SnmpError('user must be not empty')
            self.cmd_args.append(cmdgen.UsmUserData(user, auth_passwd, priv_passwd,
                authProtocol=authProtocol,
                privProtocol=privProtocol ) )
        else:
            raise SnmpError('Bad snmp version protocol, given : %s, possible : 1,2,2c,3' % version)

        self.cmd_args.append(cmdgen.UdpTransportTarget((host, port),timeout = timeout))

    def to_native_type(self,oval):
        v2c = self.v2c
        if isinstance(oval, v2c.Integer):
            val = int(oval.prettyPrint())
        elif isinstance(oval, v2c.Integer32):
            val = int(oval.prettyPrint())
        elif isinstance(oval, v2c.Unsigned32):
            val = int(oval.prettyPrint())
        elif isinstance(oval, v2c.Counter32):
            val = int(oval.prettyPrint())
        elif isinstance(oval, v2c.Counter64):
            val = int(oval.prettyPrint())
        elif isinstance(oval, v2c.Gauge32):
            val = int(oval.prettyPrint())
        elif isinstance(oval, v2c.TimeTicks):
            val = int(oval.prettyPrint())
        elif isinstance(oval, v2c.OctetString):
            val = oval.prettyPrint()
        elif isinstance(oval, v2c.IpAddress):
            val = oval.prettyPrint()
        else:
            val = oval
        return val

    def mibvar(self,*arg,**kwargs):
        return self.cmdgen.MibVariable(*arg,**kwargs)

    def get(self,oid_or_mibvar):
        args = list(self.cmd_args)
        args.append(oid_or_mibvar)
        errorIndication, errorStatus, errorIndex, varBinds = self.cmdGenerator.getCmd(*args)
        if errorIndication:
            raise SnmpError(errorIndication)
        else:
            if errorStatus:
                raise SnmpError('%s at %s' % (
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex)-1] or '?'
                    ) )
        return self.to_native_type(varBinds[0][1])

    def get_mibvar(self,*arg,**kwargs):
        oid_or_mibvar = self.mibvar(*arg,**kwargs)
        return self.get(oid_or_mibvar)

    def walk(self,oid_or_mibvar):
        lst = []
        args = list(self.cmd_args)
        args.append(oid_or_mibvar)
        errorIndication, errorStatus, errorIndex, varBindTable = self.cmdGenerator.nextCmd(*args)
        if errorIndication:
            raise SnmpError(errorIndication)
        else:
            if errorStatus:
                raise SnmpError('%s at %s' % (
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex)-1] or '?'
                    ) )
        for varBindTableRow in varBindTable:
            for name, val in varBindTableRow:
                lst.append((str(name),self.to_native_type(val)))
        return lst

    def mwalk(self,vars_oids):
        dct = {}
        for var,oid in vars_oids.items():
            dct[var] = self.walk(oid)
        return dct

    def get_oid_range(self,oid_range):
        oids = []
        if oid_range.count('-') == 1:
            begin,end = oid_range.split('-')
            oid_begin = begin.split('.')[:-1]
            id_begin = int(begin.split('.')[-1])
            oid_end = end.split('.')[1:]
            id_end = int(end.split('.')[0])
            if id_begin > id_end:
                return []
            for id in xrange(id_begin,id_end + 1):
                real_oid = '.'.join(oid_begin + [str(id)] + oid_end)
                oids.append(real_oid)
        else:
            raise SnmpError('An OID range must have one and only one "-"')
        return oids

    def mget(self,vars_oids):
        dct = {}
        oid_to_var = {}
        args = list(self.cmd_args)
        for var,oid in vars_oids.items():
            if '-' in oid:
                for real_oid in self.get_oid_range(oid):
                    args.append(real_oid)
                    oid_to_var[real_oid] = var
            else:
                args.append(oid)
                oid_to_var[oid] = var

        errorIndication, errorStatus, errorIndex, varBinds = self.cmdGenerator.getCmd(*args)
        if errorIndication:
            raise SnmpError(errorIndication)
        else:
            if errorStatus:
                raise SnmpError('%s at %s' % (
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex)-1] or '?'
                    ) )
        for oid,val in varBinds:
            var = oid_to_var[str(oid)]
            val = self.to_native_type(val) if not (val is self.noSuchInstance) else NoAttr
            if var in dct:
                if isinstance(dct[var],list):
                    dct[var].append(val)
                else:
                    dct[var] = [dct[var],val]
            else:
                dct[var] = val
        return dct
