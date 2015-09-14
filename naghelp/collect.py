# -*- coding: utf-8 -*-
'''
Création : July 7th, 2015

@author: Eric Lapouyade
'''

import re
import socket
import signal
from addicted import NoAttrDict, NoAttr
import textops

__all__ = ['search_invalid_port', 'runsh', 'TelnetSh', 'Ssh', 'Snmp', 'SnmpError', 'Timeout', 'TimeoutError']

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

class NotConnected(Exception):
    pass

class TelnetSh(object):
    def __init__(self,host, user, password=None, timeout=10, port=0, prompt_regex_list=None,*args,**kwargs):
        #import is done only on demand, because it takes some little time
        import telnetlib
        self.in_with = False
        self.is_connected = False
        with Timeout(seconds = timeout, error_message='Timeout (%ss) for telnet to %s' % (timeout,host)):
            self.tn = telnetlib.Telnet(host,port,timeout,**kwargs)
            self.tn.expect([re.compile(r'login\s*:\s+',re.I),])
            self.tn.write(user + "\n")
            self.tn.expect([re.compile(r'Password\s*:\s+',re.I),])
            self.tn.write(password + "\n")
            self.tn.expect([re.compile(r'[\$#>\]:]'),])
            if prompt_regex_list is None:
                prompt_regex_list = [re.compile(r'[\$#>\]:]'),]
            self.tn.expect(prompt_regex_list)
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
        self.tn.write("echo; echo '____BEGIN_TELNETLIB____'; %s; echo '____END_TELNETLIB____'\n" % cmd)
        #self.tn.write("exit\n")
        buffer = self.tn.read_until('____END_TELNETLIB____')

        out = ''
        flag = False
        for l in buffer.splitlines():
            ls = l.strip()
            if ls == '____BEGIN_TELNETLIB____':
                flag = True
            elif ls == '____END_TELNETLIB____':
                flag = False
            elif flag:
                out += l + '\n'

        return out[:-1]

    def run(self, cmd, timeout=30, **kwargs):
        if not self.is_connected:
            raise NotConnected('No telnet connection to run your command.')
        out = None
        try:
            with Timeout(seconds = timeout):
                out = self._run_cmd(cmd)
        except TimeoutError:
            pass
        self.close()
        return out

    def mrun(self, cmds, timeout=30, **kwargs):
        dct = NoAttrDict()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            try:
                with Timeout(seconds = timeout):
                    dct[k] = self._run_cmd(cmd)
            except TimeoutError:
                dct[k] = None
        self.close()
        return dct

class Ssh(object):
    def __init__(self,host, user, password=None, timeout=10, *args,**kwargs):
        #import is done only on demand, because it takes some little time
        import paramiko
        self.in_with = False
        self.is_connected = False
        self.client = paramiko.SSHClient()
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

    def run(self, cmd, timeout=30, **kwargs):
        if not self.is_connected:
            raise NotConnected('No ssh connection to run your command.')
        out = None
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd,timeout=timeout)
            out = stdout.read()
        except socket.timeout:
            pass
        self.close()
        return out

    def mrun(self, cmds, timeout=30, **kwargs):
        if not self.is_connected:
            raise NotConnected('No ssh connection to run your command.')
        dct = NoAttrDict()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd,timeout=timeout)
                dct[k] = stdout.read()
                dct['%s_err' % k] = stderr.read()
            except socket.timeout:
                dct[k] = None
                dct['%s_err' % k] = None
        self.close()
        return dct

class SnmpError(Exception):
    pass

class Snmp(object):
    def __init__(self,host, community='public', version=2, timeout=30, port=161, user=None,
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

        if version == 1:
            self.cmd_args.append(cmdgen.CommunityData(community, mpModel=0))
        elif version in  [2,'2c']:
            self.cmd_args.append(cmdgen.CommunityData(community))
        elif version == 3:
            if priv_protocol.lower() == 'aes':
                if not user or not auth_passwd or not priv_passwd:
                    raise SnmpError('user, auth_passwd and priv_passwd must be not empty')
                self.cmd_args.append(cmdgen.UsmUserData(user, auth_passwd, priv_passwd,
                    authProtocol=cmdgen.usmHMACSHAAuthProtocol,
                    privProtocol=cmdgen.usmAesCfb128Protocol ) )
            elif auth_protocol.lower() == 'sha':
                if not user or not auth_passwd:
                    raise SnmpError('user and auth_passwd must be not empty')
                self.cmd_args.append(cmdgen.UsmUserData(user, auth_passwd,
                           authProtocol=cmdgen.usmHMACSHAAuthProtocol))
            else:
                if not user:
                    raise SnmpError('user must be not empty')
                self.cmd_args.append(cmdgen.UsmUserData(user))
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

    def get_oid_range(self,oid_range):
        oids = []
        if oid_range.count('-') == 1:
            begin,end = oid_range.split('-')
            oid_begin = begin.split('.')[:-1]
            id_begin = int(begin.split('.')[-1])
            oid_end = end.split('.')[1:]
            id_end = int(end.split('.')[0])
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
