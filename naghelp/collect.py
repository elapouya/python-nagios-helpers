# -*- coding: utf-8 -*-
#
# Création : July 7th, 2015
#
# @author: Eric Lapouyade
#
""" This module provides many funcions and classes to collect data remotely and locally"""

import re
import socket
import signal
from addicted import NoAttr
import textops
import naghelp
import time

__all__ = ['search_invalid_port', 'runsh', 'mrunsh', 'Expect', 'Telnet', 'Ssh', 'Snmp', 'SnmpError',
           'Timeout', 'TimeoutError', 'CollectError', 'ConnectionError', 'NotConnected']

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

def runsh(cmd, context = {}, timeout = 30):
    with Timeout(seconds=timeout, error_message='Timeout (%ss) for command : %s' % (timeout,cmd)):
        return textops.run(cmd, context).l

def mrunsh(cmds, context = {},cmd_timeout = 30, total_timeout = 60):
    with Timeout(seconds=total_timeout, error_message='Timeout (%ss) for mrunsh commands : %s' % (total_timeout,cmds)):
        dct = textops.DictExt()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            dct[k] = runsh(cmd, context, cmd_timeout)
        return dct

def debug_pattern_list(pat_list):
    return [ (pat if isinstance(pat,basestring) else pat.pattern) for pat in pat_list ]

class Expect(object):
    r""" Interact with a spawn command

    :class:`Expect` is a class that "talks" to other interactive programs.
    It is based on `pexpect <https://pexpect.readthedocs.org>`_ and is
    focused on running one or many commands. :class:`Expect` is to be used when :class:`Telnet` and
    :class:`Ssh` are not applicable.

    Args:

        spawn (str): The command to start and to communicate with
        login_steps(list or tuple): steps to execute to reach a prompt
        prompt (str): A pattern that matches the prompt
        logout_cmd(str): command to execute before closing communication (Default : None)
        logout_steps(list or tuple): steps to execute before closing communication (Default : None)
        context (dict): Dictionary that will be used in steps to .format() strings (Default : None)
        timeout (int): Maximum execution time (Default : 30)

    On object creation, :class:`Expect` will :

        * spawn the specified command (``spawn``)
        * follow ``login_steps``
        * and wait for the specified ``prompt``.

    on object :meth:`run` or :meth:`mrun`, it will :

        * execute the specified command(s)
        * wait the specified prompt between each command
        * return command(s) output wihout prompt string
        * then close the interaction (see just below)

    on close, :class:`Expect` will :

        * execute the ``logout_cmd``
        * follow ``logout_steps``
        * finally terminate the spawned command

    **What are Steps ?**

        During login and logout, one can specify steps. A step is one or more pattern/answer tuples.
        The main tuple syntax is::

            (
                (
                    ( step1_pattern1, step1_answer1),
                    ( step1_pattern2, step1_answer2),
                    ...
                ),
                (
                    ( step2_pattern1, step2_answer1),
                    ( step2_pattern2, step2_answer2),
                    ...
                ),
                ...
            )

        For a same step, :class:`Expect` will search for any of the specified patterns, then will respond
        the corresponding answer. It will go to the next step only when one of the next step's patterns
        is found. If not, will stay at the same step looking again for any of the patterns.
        In order to simplify tuple expression, if there is only one tuple in a level,
        the parenthesis can be removed. For answer, you have to specify a string : do not forget
        the newline otherwise you will get stuck.
        One can also use ``Expect.BREAK`` to stop following the steps, ``Expect.RESPONSE``
        to raise an error with the found pattern as message. ``Expect.KILL`` does the same but also
        kills the spawned command.

        Here are some ``login_steps`` examples :

        The spawned command is just waiting a password::

            (r'(?i)Password[^:]*: ','wwwpw\n')

        The spawned command is waiting a login then a password::

            (
                (r'(?i)Login[^:]*: ','www\n'),
                (r'(?i)Password[^:]*: ','wwwpassword\n')
            )

        The spawned command is waiting a login then a password, but may ask a question at login prompt::

            (
                (
                    (r'(?i)Are you sure to connect \?','yes'),
                    (r'(?i)Login[^:]*: ','www\n')
                ),
                ('(?i)Password[^:]*: ','wwwpassword\n')
            )

        You can specify a context dictionary to :class:`Expect` to format answers strings.
        With ``context = { 'user':'www','passwd':'wwwpassword' }`` login_steps becomes::

            (
                (
                    (r'(?i)Are you sure to connect \?','yes'),
                    (r'(?i)Login[^:]*: ','{user}\n')
                ),
                ('(?i)Password[^:]*: ','{passwd}\n')
            )
    """
    KILL = 1
    BREAK = 2
    RESPONSE = 3

    def __init__(self,spawn,login_steps=None,prompt=None,logout_cmd=None,logout_steps=None,context={},timeout = 30,*args,**kwargs):
        # normalizing : transform tuple of string into tuple of tuples of string
        if login_steps and isinstance(login_steps[0],basestring):
            login_steps = (login_steps,)
        if logout_steps and isinstance(logout_steps[0],basestring):
            logout_steps = (logout_steps,)

        # Copy all params as object attributes
        self.__dict__.update(locals())

        #import is done only on demand, because it takes some little time
        global pexpect
        import pexpect
        self.in_with = False
        self.is_connected = False
        naghelp.logger.debug('#### Expect( %s ) ###############',spawn)
        with Timeout(seconds = timeout, error_message='Timeout (%ss) for pexpect : %s' % (timeout,spawn)):
            self.child = pexpect.spawn(spawn)
            if login_steps or prompt:
                naghelp.logger.debug('==== Login steps up to the prompt =====')
                error_msg = self._expect_steps( (login_steps or ()) + ( ((prompt,None),) if prompt else () ) )
                if error_msg:
                    raise ConnectionError(error_msg)
            self.is_connected = True

    def _expect_pattern_rewrite(self,pat):
        if pat is None:
            return pexpect.EOF
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
            if self.logout_cmd:
                self.child.sendline(self.logout_cmd)
            if self.logout_steps:
                self._expect_steps(self.logout_steps)
            try:
                self.child.kill(0)
            except OSError:
                pass
            naghelp.logger.debug('#### Expect : Connection closed ###############')

    def _run_cmd(self,cmd):
        if cmd:
            naghelp.logger.debug('  ==> sendline : %s',cmd)
            self.child.sendline('%s' % cmd)

        prompt = self._expect_pattern_rewrite(self.prompt)
        naghelp.logger.debug('<-- expect prompt : %s',prompt)
        try:
            self.child.expect(prompt)
        except pexpect.EOF:
            naghelp.logger.debug('CollectError : No more data (EOF) from %s' % self.spawn)
            raise CollectError('No more data (EOF) from %s' % self.spawn)
        out = self.child.before
        # use re.compile to be compatible with python 2.6 (flags in re.sub only for python 2.7+)
        rmcmd = re.compile(r'^.*?%s\n*' % cmd, re.DOTALL)
        out = rmcmd.sub('', out)
        out = re.sub(r'[\r\n]*$', '', out)
        out = out.replace('\r','')
        return out

    def run(self, cmd=None, timeout=30, auto_close=True, **kwargs):
        r""" Execute one command

        Runs a single command at the specified prompt and then close the interaction. Timeout
        will not raise any error but will return None.
        If you want to execute many commands without closing the interation, use ``with`` syntax.

        Args:

            cmd (str): The command to be executed by the spawned command
            timeout (int): A timeout after which the result will be None
            auto_close (bool): Automatically close the interaction.

        Return:

            str : The command output or None on timeout

        Examples:

            SSH::

                e = Expect('ssh www@localhost',
                            login_steps=('(?i)Password[^:]*: ','wwwpassword\n'),
                            prompt=r'www@[^\$]*\$ ',
                            logout_cmd='exit')
                print e.run('ls -la')

            SSH with multiple commands::

                with Expect('ssh www@localhost',
                            login_steps=('(?i)Password[^:]*: ','wwwpassword\n'),
                            prompt=r'www@[^\$]*\$ ',
                            logout_cmd='exit') as e:
                    cur_dir = e.run('pwd').strip()
                    big_files_full_path = e.run('find %s -type f -size +10000' % cur_dir)
                print big_files_full_path


        """
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
        r""" Execute many commands at the same time

        Runs a dictionary of commands at the specified prompt and then close the interaction.
        Timeout will not raise any error but will return None for the running command.
        It returns a dictionary where keys are the same as the ``cmds`` dict and the values are
        the commmands output.

        Args:

            cmds (dict or list of items): The commands to be executed by the spawned command
            timeout (int): A timeout after which the result will be None
            auto_close (bool): Automatically close the interaction.

        Return:

            dict : The commands output

        Example:

            SSH with multiple commands::

                e = Expect('ssh www@localhost',
                            login_steps=('(?i)Password[^:]*: ','wwwpassword\n'),
                            prompt=r'www@[^\$]*\$ ',
                            logout_cmd='exit')
                print e.mrun({'cur_dir':'pwd','big_files':'find . -type f -size +10000'})

            Will return something like::

                {
                    'cur_dir' : '/home/www',
                    'big_files' : 'bigfile1\nbigfile2\nbigfile3\n...'
                }
        """
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
    r""" Telnet class helper

    This class create a telnet connection in order to run one or many commands.

    Args:

        host (str): IP address or hostname to connect to
        user (str): The username to use for login
        password (str): The password
        timeout (int): Time in seconds before raising an error or a None value
        port (int): port number to use (Default : 0 = 23)
        login_pattern (str or list): The pattern to recognize the login prompt
            (Default : ``login\s*:``). One can specify a string, a re.RegexObject,
            a list of string or a list of re.RegexObject
        passwd_pattern (str or list): The pattern to recognize the password prompt
            (Default : ``Password\s*:``). One can specify a string, a re.RegexObject,
            a list of string or a list of re.RegexObject
        prompt_pattern (str): The pattern to recognize the usual prompt
            (Default : ``[\r\n][^\s\$#<>:]*\s?[\$#>:]+\s``). One can specify a string or a re.RegexObject.
    """
    def __init__(self,host, user, password=None, timeout=30, port=0, login_pattern=None, passwd_pattern=None, prompt_pattern=None,*args,**kwargs):
        #import is done only on demand, because it takes some little time
        import telnetlib
        self.in_with = False
        self.is_connected = False
        self.prompt = None
        login_pattern = Telnet._normalize_pattern(login_pattern, r'login\s*:')
        passwd_pattern = Telnet._normalize_pattern(passwd_pattern, r'Password\s*:')
        prompt_pattern = Telnet._normalize_pattern(prompt_pattern, r'[\r\n][^\s\$#<>:]*\s?[\$#>:]+\s')
        self.prompt_pattern = prompt_pattern
        naghelp.logger.debug('#### Telnet( %s@%s ) ###############',user, host)
        with Timeout(seconds = timeout, error_message='Timeout (%ss) for telnet to %s' % (timeout,host)):
            self.tn = telnetlib.Telnet(host,port,timeout,**kwargs)
            naghelp.logger.debug('<-- expect(%s) ...',debug_pattern_list(login_pattern))
            self.tn.expect(login_pattern)
            naghelp.logger.debug('  ==> %s',user)
            self.tn.write(user + "\n")
            naghelp.logger.debug('<-- expect(%s) ...',debug_pattern_list(passwd_pattern))
            self.tn.expect(passwd_pattern)
            naghelp.logger.debug('  ==> (hidden password)')
            self.tn.write(password + "\n")
            naghelp.logger.debug('<-- expect(%s) ...',debug_pattern_list(prompt_pattern))
            pat_id,m,buffer = self.tn.expect(prompt_pattern)
            if pat_id < 0:
                raise ConnectionError('No regular prompt found.')
            naghelp.logger.debug('Prompt found : is_connected = True')
            self.is_connected = True

    @staticmethod
    def _normalize_pattern(pattern,default):
        if pattern is None:
            pattern = [re.compile(default,re.I)]
        elif isinstance(pattern,basestring):
            pattern = [re.sub(r'^\^',r'[\r\n]',pattern)]
        elif not isinstance(pattern,list):
            pattern = [pattern]
        return pattern

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
            naghelp.logger.debug('#### Telnet : Connection closed ###############')

    def _run_cmd(self,cmd):
        naghelp.logger.debug('  ==> %s',cmd)
        self.tn.write('%s\n' % cmd)
        naghelp.logger.debug('<-- expect(%s) ...',debug_pattern_list(self.prompt_pattern))
        pat_id,m,buffer = self.tn.expect(self.prompt_pattern)
        out = buffer.replace('\r','')
        # use re.compile to be compatible with python 2.6 (flags in re.sub only for python 2.7+)
        rmcmd = re.compile(r'^.*?%s\n*' % cmd, re.DOTALL)
        out = rmcmd.sub('', out)
        # remove cmd and prompt (first and last line)
        out = out.splitlines()[:-1]
        return '\n'.join(out)

    def run(self, cmd, timeout=30, auto_close=True, **kwargs):
        r""" Execute one command

        Runs a single command at the usual prompt and then close the connection. Timeout
        will not raise any error but will return None.
        If you want to execute many commands without closing the interation, use ``with`` syntax.

        Args:

            cmd (str): The command to be executed
            timeout (int): A timeout after which the result will be None
            auto_close (bool): Automatically close the connection.

        Return:

            str : The command output or None on timeout

        Examples:

            Telnet with default login/password/prompt::

                tn = Telnet('localhost','www','wwwpassword')
                print tn.run('ls -la')

            Telnet with custom password prompt (password in french), note the ``(?i)`` for the case insensitive::

                tn = Telnet('localhost','www','wwwpassword',password_pattern=r'(?i)Mot de passe\s*:')
                print tn.run('ls -la')

            Telnet with multiple commands::

                with Expect('ssh www@localhost',
                            login_steps=('(?i)Password[^:]*: ','wwwpw\n'),
                            prompt=r'www@[^\$]*\$ ',
                            logout_cmd='exit') as e:
                    cur_dir = e.run('pwd').strip()
                    big_files_full_path = e.run('find %s -type f -size +10000' % cur_dir)
                print big_files_full_path


        """
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
    """ Ssh class helper """
    def __init__(self,host, user, password=None, timeout=30, auto_accept_new_host=True, prompt_pattern=None, *args,**kwargs):
        #import is done only on demand, because it takes some little time
        import paramiko
        self.in_with = False
        self.is_connected = False
        self.prompt_pattern = prompt_pattern
        self.client = paramiko.SSHClient()
        if auto_accept_new_host:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.load_system_host_keys()
        naghelp.logger.debug('#### Ssh( %s@%s ) ###############',user, host)
        self.client.connect(host,username=user,password=password, timeout=timeout, **kwargs)
        if self.prompt_pattern:
            self.prompt_pattern = re.compile(re.sub(r'^\^',r'[\r\n]',prompt_pattern))
            self.chan = self.client.invoke_shell(width=160,height=48)
            self.chan.settimeout(timeout)
            self._read_to_prompt()
        naghelp.logger.debug('is_connected = True')
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
            naghelp.logger.debug('#### Ssh : Connection closed ###############')

    def _read_to_prompt(self):
        buff = ''
        while not self.prompt_pattern.search(buff):
            buff += self.chan.recv(8192)
        return buff

    def _run_cmd(self,cmd,timeout):
        naghelp.logger.debug('  ==> %s',cmd)
        if self.prompt_pattern is None:
            stdin, stdout, stderr = self.client.exec_command(cmd,timeout=timeout)
            out = stdout.read()
            return out
        else:
            self.chan.send('%s\n' % cmd)
            out = self._read_to_prompt()
            out = out.replace('\r','')
            # use re.compile to be compatible with python 2.6 (flags in re.sub only for python 2.7+)
            rmcmd = re.compile(r'^.*?%s\n*' % cmd, re.DOTALL)
            out = rmcmd.sub('', out)
            # remove cmd and prompt (first and last line)
            out = out.splitlines()[:-1]
            return '\n'.join(out)

    def run(self, cmd, timeout=30, auto_close=True, **kwargs):
        if not self.is_connected:
            raise NotConnected('No ssh connection to run your command.')
        out = None
        try:
            out = self._run_cmd(cmd,timeout=timeout)
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
                out = self._run_cmd(cmd,timeout=timeout)
                if k:
                    dct[k] = out
            except socket.timeout:
                if k:
                    dct[k] = None
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
                try:
                    err_at = errorIndex and varBinds[int(errorIndex)-1] or '?'
                except:
                    err_at = '?'
                raise SnmpError('%s at %s' % (errorStatus.prettyPrint(),err_at) )
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
                try:
                    err_at = errorIndex and varBindTable[-1][int(errorIndex)-1] or '?'
                except:
                    err_at = '?'
                raise SnmpError('%s at %s' % (errorStatus.prettyPrint(),err_at) )
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
                try:
                    err_at = errorIndex and varBinds[int(errorIndex)-1] or '?'
                except:
                    err_at = '?'
                raise SnmpError('%s at %s' % (errorStatus.prettyPrint(),err_at) )
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
