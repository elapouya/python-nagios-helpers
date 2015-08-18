# -*- coding: utf-8 -*-
'''
Création : July 7th, 2015

@author: Eric Lapouyade
'''

import telnetlib
import re
import socket
import signal
from addicted import NoAttrDict

__all__ = ['search_invalid_port', 'telnet', 'ssh', 'Timeout', 'TimeoutError']

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

class NotConnected(Exception):
    pass

class telnet(object):
    def __init__(self,host, user, password=None, timeout=10, port=0, prompt_regex_list=None,*args,**kwargs):
        self.in_with = False
        self.is_connected = False
        with Timeout(timeout):
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
            with Timeout(timeout):
                out = self._run_cmd(cmd)
        except TimeoutError:
            pass
        self.close()
        return out

    def mrun(self, cmds, timeout=30, **kwargs):
        dct = NoAttrDict()
        for k,cmd in cmds.items():
            try:
                with Timeout(timeout):
                    dct[k] = self._run_cmd(cmd)
            except TimeoutError:
                dct[k] = None
        self.close()
        return dct

class ssh(object):
    def __init__(self,host, user, password=None, timeout=10, *args,**kwargs):
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
        for k,cmd in cmds.items():
            try:
                stdin, stdout, stderr = self.client.exec_command(cmd,timeout=timeout)
                dct[k] = stdout.read()
                dct['%s_err' % k] = stderr.read()
            except socket.timeout:
                dct[k] = None
                dct['%s_err' % k] = None
        self.close()
        return dct