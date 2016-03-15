# -*- coding: utf-8 -*-
#
# Création : July 7th, 2015
#
# @author: Eric Lapouyade
#
"""This module provides many funcions and classes to collect data remotely and locally"""

import re
import socket
import signal
from addicted import NoAttr
import textops
import naghelp
import time
import subprocess

__all__ = ['search_invalid_port', 'runsh', 'mrunsh', 'Expect', 'Telnet', 'Ssh', 'Snmp',
           'Timeout', 'TimeoutError', 'CollectError', 'ConnectionError', 'NotConnected',
           'UnexpectedResultError']

class CollectError(Exception):
    """Exception raised when a collect is unsuccessful

    It may come from internal error from libraries pexpect/telnetlib/pysnmp. This includes
    some internal timeout exception.
    """
    pass

class NotConnected(CollectError):
    """Exception raised when trying to collect data on an already close connection

    After a run()/mrun() without a ``with:`` clause, the connection is automatically closed.
    Do not do another run()/mrun() in the row otherwise you will have the exception.
    Solution : use ``with:``
    """
    pass

class ConnectionError(CollectError):
    """Exception raised when trying to initialize the connection

    It may come from bad login/password, bad port, inappropriate parameters and so on
    """
    pass

class TimeoutError(CollectError):
    """Exception raised when a connection or a collect it too long to process

    It may come from unreachable remote host, too long lasting commands, bad pattern matching on
    Expect/Telnet/Ssh for connection or prompt search steps.
    """
    pass

class UnexpectedResultError(CollectError):
    """Exception raised when a command gave an unexpected result

    This works with ``expected_pattern`` and ``unexpected_pattern`` available in some
    collecting classes.
    """
    pass

class Timeout:
    """Set an execution timeout for a block of code

    It uses process signals, it should not work on windows platforms.

    Args:

        seconds (int): The time in seconds after which a TimeoutError will be raise if the block
            has not finished its execution.
        error_message(str): The string to pass to the TimeoutError exception.

    Raises:

        TimeoutError: When the block execution has not finished on-time.

    Examples:

        >>> with timeout(seconds=3):
        >>>     time.sleep(4)

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
    """Returns the first invalid port encountered or None if all are reachable

    Args:

        ip (str): ip address to test
        ports (str or list of int): list of ports to test

    Returns:

        first invalid port encountered or None if all are reachable

    Examples:

        >>> search_invalid_port('8.8.8.8','53')
        (None)
        >>> search_invalid_port('8.8.8.8','53,22,80')
        22
    """
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


def _raise_unexpected_result(result, key, cmd, help_str=''):
    if isinstance(result,basestring):
        if result == '':
            result = '<empty result>'
        else:
            result = '\n'.join(result.splitlines()[:10]) + '\n...'
    else:
        result = '%s (%s)' % (result,type(result))
    key_str = 'for command key "%s"' % key if key else ''
    s='Unexpected result %s:\nCommand = %s\n%s\n\n%s\n\nNOTE : Due to nagios restrictions, pipe symbol has been replaced by "!"' % (key_str,cmd,help_str,result)
    raise UnexpectedResultError(s)

def _filter_result(result, key, cmd, expected_pattern=r'\S', unexpected_pattern=None, filter=None):
    if callable(filter):
        filtered = filter(result, key, cmd)
        if filtered is not None:
            result = filtered

    if unexpected_pattern is not None:
        if isinstance(unexpected_pattern,basestring):
            unexpected_pattern = re.compile(unexpected_pattern)
        if unexpected_pattern.search(result):
            help_str = '-> found the pattern "%s" :\n\n' % unexpected_pattern.pattern
            help_str += result | textops.findhighlight(unexpected_pattern,line_nbr=True,nlines=5).tostr()
            _raise_unexpected_result(result, key, cmd, help_str)

    if expected_pattern is not None:
        if isinstance(expected_pattern,basestring):
            expected_pattern = re.compile(expected_pattern)
        if not expected_pattern.search(result):
            if expected_pattern.pattern==r'\S':
                _raise_unexpected_result(result, key, cmd, '-> empty result')
            else:
                _raise_unexpected_result(result, key, cmd, '-> cannot find the pattern "%s"' % expected_pattern.pattern)

    return result

def runsh(cmd, context = {}, timeout = 30, expected_pattern=r'\S', unexpected_pattern=None, filter=None, key='' ):
    r"""Run a local command with a timeout

    | If the command is a string, it will be executed within a shell.
    | If the command is a list (the command and its arguments), the command is executed without a shell.
    | If a context dict is specified, the command is formatted with that context (:meth:`str.format`)

    Args:

        cmd (str or a list): The command to run
        context (dict): The context to format the command to run (Optional)
        timeout (int): The timeout in seconds after with the forked process is killed
            and TimeoutException is raised (Default : 30s).
        expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found.
            if None, there is no test. By default, tests the result is not empty.
        unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
            if None, there is no test. By default, there is no test.
        filter (callable): call a filter function with ``result, key, cmd`` parameters.
            The function should return the modified result (if there is no return statement,
            the original result is used).
            The filter function is also the place to do some other checks : ``cmd`` is the command
            that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
            ``mget`` and ``mwalk``.
            By Default, there is no filter.
        key (str): a key string to appear in UnexpectedResultError if any.

    Returns:

        :class:`textops.ListExt`: Command execution stdout as a list of lines.

    Note:

        It returns **ONLY** stdout. If you want to get stderr, you need to redirect it to stdout.

    Examples:

        >>> for line in runsh('ls -lad /etc/e*'):
        ...     print line
        ...
        -rw-r--r-- 1 root root  392 oct.   8  2013 /etc/eclipse.ini
        -rw-r--r-- 1 root root  350 mai   21  2012 /etc/eclipse.ini_old
        drwxr-xr-x 2 root root 4096 avril 13  2014 /etc/elasticsearch
        drwxr-xr-x 3 root root 4096 avril 25  2012 /etc/emacs
        -rw-r--r-- 1 root root   79 avril 25  2012 /etc/environment
        drwxr-xr-x 2 root root 4096 mai    1  2012 /etc/esound

        >>> print runsh('ls -lad /etc/e*').grep('eclipse').tostr()
        -rw-r--r-- 1 root root  392 oct.   8  2013 /etc/eclipse.ini
        -rw-r--r-- 1 root root  350 mai   21  2012 /etc/eclipse.ini_old

        >>> l=runsh('LANG=C ls -lad /etc/does_not_exist')
        >>> print l
        []
        >>> l=runsh('LANG=C ls -lad /etc/does_not_exist 2>&1')
        >>> print l
        ['ls: cannot access /etc/does_not_exist: No such file or directory']
    """
    if context:
        cmd = cmd.format(**context)
    with Timeout(seconds=timeout, error_message='Timeout (%ss) for command : %s' % (timeout,cmd)):
        try:
            result = subprocess.check_output(['sh','-c',cmd])
        except Exception,e:
            result = ''
        return textops.StrExt(_filter_result(result, key, cmd, expected_pattern, unexpected_pattern, filter))

def mrunsh(cmds, context = {},cmd_timeout = 30, total_timeout = 60, expected_pattern=r'\S', unexpected_pattern=None, filter=None):
    r"""Run multiple local commands with timeouts

    It works like :func:`runsh` except that one must provide a dictionary of commands.
    It will generate the same dictionary where values will be replaced by command execution output.
    It is possible to specify a by-command timeout and a global timeout for the whole dictionary.

    Args:

        cmds (dict): dictionary where values are the commands to execute.

            | If the command is a string, it will be executed within a shell.
            | If the command is a list (the command and its arguments), the command is executed without a shell.
            | If a context dict is specified, the command is formatted with that context (:meth:`str.format`)

        context (dict): The context to format the command to run
        cmd_timeout (int): The timeout in seconds for a single command
        total_timeout (int): The timeout in seconds for the all commands
        expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found.
            if None, there is no test. By default, tests the result is not empty.
        unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
            if None, there is no test. By default, there is no test.
        filter (callable): call a filter function with ``result, key, cmd`` parameters.
            The function should return the modified result (if there is no return statement,
            the original result is used).
            The filter function is also the place to do some other checks : ``cmd`` is the command
            that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
            ``mget`` and ``mwalk``.
            By Default, there is no filter.

    Returns:

        :class:`textops.DictExt`: Dictionary where each value is the Command execution stdout as a list of lines.

    Note:

        Command execution returns **ONLY** stdout. If you want to get stderr, you need to redirect it to stdout.

    Examples:

        >>> mrunsh({'now':'LANG=C date','quisuisje':'whoami'})
        {'now': ['Wed Dec 16 11:50:08 CET 2015'], 'quisuisje': ['elapouya']}

    """
    with Timeout(seconds=total_timeout, error_message='Timeout (%ss) for mrunsh commands : %s' % (total_timeout,cmds)):
        dct = textops.DictExt()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            dct[k] = runsh(cmd, context, cmd_timeout, expected_pattern, unexpected_pattern, filter, k)
        return dct

def debug_pattern_list(pat_list):
    return [ (pat if isinstance(pat,basestring) else pat.pattern) for pat in pat_list ]

class Expect(object):
    r"""Interact with a spawn command

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
        expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
            in methods that collect data (like run,mrun,get,mget,walk,mwalk...)
            if None, there is no test. By default, tests the result is not empty.
        unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
            if None, there is no test. By default, it tests <timeout>.
        filter (callable): call a filter function with ``result, key, cmd`` parameters.
            The function should return the modified result (if there is no return statement,
            the original result is used).
            The filter function is also the place to do some other checks : ``cmd`` is the command
            that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
            ``mget`` and ``mwalk``.
            By Default, there is no filter.

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

    def __init__(self,spawn,login_steps=None,prompt=None,logout_cmd=None,logout_steps=None,context={},
                 timeout = 30, expected_pattern=r'\S', unexpected_pattern=r'<timeout>',
                 filter=None,*args,**kwargs):

        self.expected_pattern = expected_pattern
        self.unexpected_pattern = unexpected_pattern
        self.filter = filter

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

    def run(self, cmd=None, timeout=30, auto_close=True, expected_pattern=None, unexpected_pattern=None, filter=None, **kwargs):
        r"""Execute one command

        Runs a single command at the specified prompt and then close the interaction. Timeout
        will not raise any error but will return None.
        If you want to execute many commands without closing the interation, use ``with`` syntax.

        Args:

            cmd (str): The command to be executed by the spawned command
            timeout (int): A timeout in seconds after which the result will be None
            auto_close (bool): Automatically close the interaction.
            expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
                if None, there is no test. By default, use the value defined at object level.
            unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
                if None, there is no test. By default, use the value defined at object level.
            filter (callable): call a filter function with ``result, key, cmd`` parameters.
                The function should return the modified result (if there is no return statement,
                the original result is used).
                The filter function is also the place to do some other checks : ``cmd`` is the command
                that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
                ``mget`` and ``mwalk``.
                By default, use the filter defined at object level.

        Return:

            :class:`textops.StrExt` : The command output or None on timeout

        Examples:

            Doing a ssh through Expect::

                e = Expect('ssh www@localhost',
                            login_steps=('(?i)Password[^:]*: ','wwwpassword\n'),
                            prompt=r'www@[^\$]*\$ ',
                            logout_cmd='exit')
                print e.run('ls -la')

            Expect/ssh with multiple commands::

                with Expect('ssh www@localhost',
                            login_steps=('(?i)Password[^:]*: ','wwwpassword\n'),
                            prompt=r'www@[^\$]*\$ ',
                            logout_cmd='exit') as e:
                    cur_dir = e.run('pwd').strip()
                    big_files_full_path = e.run('find %s -type f -size +10000' % cur_dir)
                print big_files_full_path

            .. note::

                These examples emulate :class:`~naghelp.Ssh` class. :class:`~naghelp.Expect` is better for non-standard
                commands that requires human interations.


        """
        if not self.is_connected:
            raise NotConnected('No expect connection to run your command.')
        out = None
        try:
            with Timeout(seconds = timeout):
                out = self._run_cmd(cmd)
        except TimeoutError:
            out = '<timeout>'
        if auto_close:
            self.close()
        return textops.StrExt(_filter_result(out,'',cmd, expected_pattern or self.expected_pattern,
                                                         unexpected_pattern or self.unexpected_pattern,
                                                         filter or self.filter))

    def mrun(self, cmds, timeout=30, auto_close=True, expected_pattern=None, unexpected_pattern=None, filter=None, **kwargs):
        r"""Execute many commands at the same time

        Runs a dictionary of commands at the specified prompt and then close the interaction.
        Timeout will not raise any error but will return None for the running command.
        It returns a dictionary where keys are the same as the ``cmds`` dict and the values are
        the commmands output.

        Args:

            cmds (dict or list of items): The commands to be executed by the spawned command
            timeout (int): A timeout in seconds after which the result will be None
            auto_close (bool): Automatically close the interaction.
            expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
                if None, there is no test. By default, use the value defined at object level.
            unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
                if None, there is no test. By default, use the value defined at object level.
            filter (callable): call a filter function with ``result, key, cmd`` parameters.
                The function should return the modified result (if there is no return statement,
                the original result is used).
                The filter function is also the place to do some other checks : ``cmd`` is the command
                that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
                ``mget`` and ``mwalk``.
                By default, use the filter defined at object level.

        Return:

            :class:`textops.DictExt` : The commands output

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

            .. note::

                This example emulate :class:`~naghelp.Ssh` class. :class:`~naghelp.Expect` is better
                for non-standard commands that requires human interations.
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
                        dct[k] = _filter_result(output,k,cmd, expected_pattern or self.expected_pattern,
                                                              unexpected_pattern or self.unexpected_pattern,
                                                              filter or self.filter)
            except TimeoutError:
                if k:
                    dct[k] = _filter_result('<timeout>',k,cmd, expected_pattern or self.expected_pattern,
                                                          unexpected_pattern or self.unexpected_pattern,
                                                          filter or self.filter)
        if auto_close:
            self.close()
        return dct

class Telnet(object):
    r"""Telnet class helper

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
            (Default : ``[\r\n][^\s]*\s?[\$#>:]+\s``). One can specify a string or a re.RegexObject.
        autherr_pattern (str): The pattern to recognize authentication error
            (Default : ``bad password|login incorrect|login failed|authentication error``).
            One can specify a string or a re.RegexObject.
        sleep (int): Add delay in seconds before each write/expect
        sleep_login (int): Add delay in seconds before login
        expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
            in methods that collect data (like run,mrun,get,mget,walk,mwalk...)
            if None, there is no test. By default, tests the result is not empty.
        unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
            if None, there is no test. By default, it tests <timeout>.
        filter (callable): call a filter function with ``result, key, cmd`` parameters.
            The function should return the modified result (if there is no return statement,
            the original result is used).
            The filter function is also the place to do some other checks : ``cmd`` is the command
            that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
            ``mget`` and ``mwalk``.
            By Default, there is no filter.
    """
    def __init__(self,host, user, password=None, timeout=30, port=0,
                 login_pattern=None, passwd_pattern=None, prompt_pattern=None, autherr_pattern=None,
                 sleep=0, sleep_login=0, expected_pattern=r'\S', unexpected_pattern=r'<timeout>',
                 filter=None, *args,**kwargs):
        #import is done only on demand, because it takes some little time
        import telnetlib
        self.in_with = False
        self.is_connected = False
        self.prompt = None
        self.sleep = sleep
        login_pattern = Telnet._normalize_pattern(login_pattern, r'login\s*:')
        passwd_pattern = Telnet._normalize_pattern(passwd_pattern, r'Password\s*:')
        prompt_pattern = Telnet._normalize_pattern(prompt_pattern, r'[\r\n][^\s]*\s?[\$#>:]+\s')
        autherr_pattern = Telnet._normalize_pattern(autherr_pattern, r'bad password|login incorrect|login failed|authentication error')
        self.prompt_pattern = prompt_pattern
        self.expected_pattern = expected_pattern
        self.unexpected_pattern = unexpected_pattern
        self.filter = filter
        if isinstance(user, unicode):
            user = user.encode('utf-8','ignore')
        if isinstance(password, unicode):
            password = password.encode('utf-8','ignore')
        if not host:
            raise ConnectionError('No host specified for Telnet')
        if not user:
            raise ConnectionError('No user specified for Telnet')
        naghelp.logger.debug('#### Telnet( %s@%s ) ###############',user, host)
        with Timeout(seconds = timeout, error_message='Timeout (%ss) for telnet to %s' % (timeout,host)):
            try:
                self.tn = telnetlib.Telnet(host,port,timeout,**kwargs)
                #self.tn.set_debuglevel(1)
            except Exception,e:
                raise ConnectionError(e)
            naghelp.logger.debug('<-- expect(%s) ...',debug_pattern_list(login_pattern))
            time.sleep(sleep_login or sleep)
            self.tn.expect(login_pattern)
            naghelp.logger.debug('  ==> %s',user)
            time.sleep(sleep)
            self.tn.write(user + "\n")
            naghelp.logger.debug('<-- expect(%s) ...',debug_pattern_list(passwd_pattern))
            if password is not None:
                time.sleep(sleep)
                self.tn.expect(passwd_pattern)
                naghelp.logger.debug('  ==> (hidden password)')
                time.sleep(sleep)
                self.tn.write(password + "\n")
            naghelp.logger.debug('<-- expect(%s) ...',debug_pattern_list(prompt_pattern + autherr_pattern))
            time.sleep(sleep)
            pat_id,m,buffer = self.tn.expect(prompt_pattern + autherr_pattern)
            naghelp.logger.debug('pat_id,m,buffer = %s, %s, %s',pat_id,m,buffer)
            if pat_id < 0:
                raise ConnectionError('No regular prompt found.')
            if pat_id >= len(prompt_pattern):
                raise ConnectionError('Authentication error')
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
        if isinstance(cmd, unicode):
            cmd = cmd.encode('utf-8','ignore')
        naghelp.logger.debug('  ==> %s',cmd)
        time.sleep(self.sleep)
        self.tn.write('%s\n' % cmd)
        naghelp.logger.debug('<-- expect(%s) ...',debug_pattern_list(self.prompt_pattern))
        time.sleep(self.sleep)
        pat_id,m,buffer = self.tn.expect(self.prompt_pattern)
        out = buffer.replace('\r','')
        # use re.compile to be compatible with python 2.6 (flags in re.sub only for python 2.7+)
        rmcmd = re.compile(r'^.*?%s\n*' % cmd, re.DOTALL)
        out = rmcmd.sub('', out)
        # remove cmd and prompt (first and last line)
        out = out.splitlines()[:-1]
        return '\n'.join(out)

    def run(self, cmd, timeout=30, auto_close=True, expected_pattern=None, unexpected_pattern=None, filter=None, **kwargs):
        r"""Execute one command

        Runs a single command at the usual prompt and then close the connection. Timeout
        will not raise any error but will return None.
        If you want to execute many commands without closing the connection, use ``with`` syntax.

        Args:

            cmd (str): The command to be executed
            timeout (int): A timeout in seconds after which the result will be None
            auto_close (bool): Automatically close the connection.
            expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
                if None, there is no test. By default, use the value defined at object level.
            unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
                if None, there is no test. By default, use the value defined at object level.
            filter (callable): call a filter function with ``result, key, cmd`` parameters.
                The function should return the modified result (if there is no return statement,
                the original result is used).
                The filter function is also the place to do some other checks : ``cmd`` is the command
                that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
                ``mget`` and ``mwalk``.
                By default, use the filter defined at object level.

        Return:

            :class:`textops.StrExt` : The command output or None on timeout

        Examples:

            Telnet with default login/password/prompt::

                tn = Telnet('localhost','www','wwwpassword')
                print tn.run('ls -la')

            Telnet with custom password prompt (password in french), note the ``(?i)`` for the case insensitive::

                tn = Telnet('localhost','www','wwwpassword',password_pattern=r'(?i)Mot de passe\s*:')
                print tn.run('ls -la')

            Telnet with multiple commands (use ``with`` to keep connection opened). This is
            usefull when one command depend on another one::

                with Telnet('localhost','www','wwwpassword') as tn:
                    cur_dir = tn.run('pwd').strip()
                    big_files_full_path = tn.run('find %s -type f -size +10000' % cur_dir)
                print big_files_full_path


        """
        if not self.is_connected:
            raise NotConnected('No telnet connection to run your command.')
        out = ''
        try:
            with Timeout(seconds = timeout):
                out = self._run_cmd(cmd)
        except TimeoutError:
            out = '<timeout>'
        if auto_close:
            self.close()
        return textops.StrExt(_filter_result(out,'',cmd, expected_pattern or self.expected_pattern,
                                                         unexpected_pattern or self.unexpected_pattern,
                                                         filter or self.filter))

    def mrun(self, cmds, timeout=30, auto_close=True, expected_pattern=None, unexpected_pattern=None, filter=None, **kwargs):
        r"""Execute many commands at the same time

        Runs a dictionary of commands at the specified prompt and then close the connection.
        Timeout will not raise any error but will return None for the running command.
        It returns a dictionary where keys are the same as the ``cmds`` dict and the values are
        the commmands output.

        Args:

            cmds (dict or list of items): The commands to be executed by remote host
            timeout (int): A timeout in seconds after which the result will be None
            auto_close (bool): Automatically close the connection.
            expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
                if None, there is no test. By default, use the value defined at object level.
            unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
                if None, there is no test. By default, use the value defined at object level.
            filter (callable): call a filter function with ``result, key, cmd`` parameters.
                The function should return the modified result (if there is no return statement,
                the original result is used).
                The filter function is also the place to do some other checks : ``cmd`` is the command
                that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
                ``mget`` and ``mwalk``.
                By default, use the filter defined at object level.

        Return:

            :class:`textops.DictExt` : The commands output

        Example:

            Telnet with multiple commands::

                tn = Telnet('localhost','www','wwwpassword')
                print tn.mrun({'cur_dir':'pwd','big_files':'find . -type f -size +10000'})

            Will return something like::

                {
                    'cur_dir' : '/home/www',
                    'big_files' : 'bigfile1\nbigfile2\nbigfile3\n...'
                }
        """
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
                        dct[k] = _filter_result(output,k,cmd, expected_pattern or self.expected_pattern,
                                                           unexpected_pattern or self.unexpected_pattern,
                                                           filter or self.filter)
            except TimeoutError:
                dct[k] = _filter_result('<timeout>',k,cmd, expected_pattern or self.expected_pattern,
                                                   unexpected_pattern or self.unexpected_pattern,
                                                   filter or self.filter)
        if auto_close:
            self.close()
        return dct

class Ssh(object):
    r"""Ssh class helper

    This class create a ssh connection in order to run one or many commands.

    Args:

        host (str): IP address or hostname to connect to
        user (str): The username to use for login
        password (str): The password
        timeout (int): Time in seconds before raising an error or a None value
        prompt_pattern (str): None by Default. If defined, the way to run commands is to capture
            the command output up to the prompt pattern. If not defined, it uses paramiko exec_command()
            method (preferred way).
        get_pty (bool): Create a pty, this is useful for some ssh connection (Default: False)
        expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
            in methods that collect data (like run,mrun,get,mget,walk,mwalk...)
            if None, there is no test. By default, tests the result is not empty.
        unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
            if None, there is no test. By default, it tests <timeout>.
        filter (callable): call a filter function with ``result, key, cmd`` parameters.
            The function should return the modified result (if there is no return statement,
            the original result is used).
            The filter function is also the place to do some other checks : ``cmd`` is the command
            that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
            ``mget`` and ``mwalk``.
            By Default, there is no filter.
        add_stderr (bool): If True, the stderr will be added at the end of results (Default: True)
        port (int): port number to use (Default : 0 = 22)
        pkey (PKey): an optional private key to use for authentication
        key_filename (str):
            the filename, or list of filenames, of optional private key(s) to
            try for authentication
        allow_agent (bool): set to False to disable connecting to the SSH agent
        look_for_keys (bool): set to False to disable searching for discoverable private key
            files in ``~/.ssh/``
        compress (bool): set to True to turn on compression
        sock (socket): an open socket or socket-like object (such as a `.Channel`) to use
            for communication to the target host
        gss_auth (bool): ``True`` if you want to use GSS-API authentication
        gss_kex (bool):  Perform GSS-API Key Exchange and user authentication
        gss_deleg_creds (bool): Delegate GSS-API client credentials or not
        gss_host (str): The targets name in the kerberos database. default: hostname
        banner_timeout (float): an optional timeout (in seconds) to wait
            for the SSH banner to be presented.
    """
    def __init__(self,host, user, password=None, timeout=30, auto_accept_new_host=True,
                 prompt_pattern=None, get_pty=False, expected_pattern=r'\S', unexpected_pattern=r'<timeout>',
                 filter=None, add_stderr=True, *args,**kwargs):
        #import is done only on demand, because it takes some little time
        import paramiko
        self.in_with = False
        self.is_connected = False
        self.prompt_pattern = prompt_pattern
        self.get_pty = get_pty
        self.expected_pattern = expected_pattern
        self.unexpected_pattern = unexpected_pattern
        self.filter = filter
        self.add_stderr = add_stderr
        self.client = paramiko.SSHClient()
        if not host:
            raise ConnectionError('No host specified for Ssh')
        if not user:
            raise ConnectionError('No user specified for Ssh')
        if auto_accept_new_host:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.load_system_host_keys()
        naghelp.logger.debug('#### Ssh( %s@%s ) ###############',user, host)
        try:
            self.client.connect(host,username=user,password=password, timeout=timeout, **kwargs)
            if self.prompt_pattern:
                self.prompt_pattern = re.compile(re.sub(r'^\^',r'[\r\n]',prompt_pattern))
                self.chan = self.client.invoke_shell(width=160,height=48)
                self.chan.settimeout(timeout)
                self._read_to_prompt()
        except Exception,e:
            raise ConnectionError(e)
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
            stdin, stdout, stderr = self.client.exec_command(cmd,timeout=timeout,get_pty=self.get_pty)
            out = stdout.read()
            if self.add_stderr:
                out += stderr.read()
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

    def run(self, cmd, timeout=30, auto_close=True, expected_pattern=None, unexpected_pattern=None, filter=None, **kwargs):
        r"""Execute one command

        Runs a single command at the usual prompt and then close the connection. Timeout
        will not raise any error but will return None.
        If you want to execute many commands without closing the connection, use ``with`` syntax.

        Args:

            cmd (str): The command to be executed
            timeout (int): A timeout in seconds after which the result will be None
            auto_close (bool): Automatically close the connection.
            expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
                if None, there is no test. By default, use the value defined at object level.
            unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
                if None, there is no test. By default, use the value defined at object level.
            filter (callable): call a filter function with ``result, key, cmd`` parameters.
                The function should return the modified result (if there is no return statement,
                the original result is used).
                The filter function is also the place to do some other checks : ``cmd`` is the command
                that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
                ``mget`` and ``mwalk``.
                By default, use the filter defined at object level.

        Return:

            :class:`textops.StrExt` : The command output or None on timeout

        Examples:

            SSH with default login/password/prompt::

                ssh = Ssh('localhost','www','wwwpassword')
                print ssh.run('ls -la')

            SSH with multiple commands (use ``with`` to keep connection opened). This is
            usefull when one command depend on another one::

                with Ssh('localhost','www','wwwpassword') as ssh:
                    cur_dir = ssh.run('pwd').strip()
                    big_files_full_path = ssh.run('find %s -type f -size +10000' % cur_dir)
                print big_files_full_path
        """
        if not self.is_connected:
            raise NotConnected('No ssh connection to run your command.')
        try:
            out = self._run_cmd(cmd,timeout=timeout)
        except socket.timeout:
            out = '<timeout>'
        if auto_close:
            self.close()
        return textops.StrExt(_filter_result(out,'',cmd, expected_pattern or self.expected_pattern,
                                                         unexpected_pattern or self.unexpected_pattern,
                                                         filter or self.filter))

    def mrun(self, cmds, timeout=30, auto_close=True, expected_pattern=None, unexpected_pattern=None, filter=None, **kwargs):
        r"""Execute many commands at the same time

        Runs a dictionary of commands at the specified prompt and then close the connection.
        Timeout will not raise any error but will return None for the running command.
        It returns a dictionary where keys are the same as the ``cmds`` dict and the values are
        the commmands output.

        Args:

            cmds (dict or list of items): The commands to be executed by remote host
            timeout (int): A timeout in seconds after which the result will be None
            auto_close (bool): Automatically close the connection.
            expected_pattern (str or regex): raise UnexpectedResultError if the pattern is not found
                if None, there is no test. By default, use the value defined at object level.
            unexpected_pattern (str or regex): raise UnexpectedResultError if the pattern is found
                if None, there is no test. By default, use the value defined at object level.
            filter (callable): call a filter function with ``result, key, cmd`` parameters.
                The function should return the modified result (if there is no return statement,
                the original result is used).
                The filter function is also the place to do some other checks : ``cmd`` is the command
                that generated the ``result`` and ``key`` the key in the dictionary for ``mrun``,
                ``mget`` and ``mwalk``.
                By default, use the filter defined at object level.

        Return:

            :class:`textops.DictExt` : The commands output

        Example:

            SSH with multiple commands::

                ssh = Ssh('localhost','www','wwwpassword')
                print ssh.mrun({'cur_dir':'pwd','big_files':'find . -type f -size +10000'})

            Will return something like::

                {
                    'cur_dir' : '/home/www',
                    'big_files' : 'bigfile1\nbigfile2\nbigfile3\n...'
                }

            To be sure to have the commands order respected, use list of items instead of a dict::

                ssh = Ssh('localhost','www','wwwpassword')
                print ssh.mrun( (('cmd','./mycommand'),('cmd_err','echo $?')) )

        """
        if not self.is_connected:
            raise NotConnected('No ssh connection to run your command.')
        dct = textops.DictExt()
        if isinstance(cmds,dict):
            cmds = cmds.items()
        for k,cmd in cmds:
            try:
                out = self._run_cmd(cmd,timeout=timeout)
                if k:
                    dct[k] = _filter_result(out,k,cmd, expected_pattern or self.expected_pattern,
                                                       unexpected_pattern or self.unexpected_pattern,
                                                       filter or self.filter)
            except socket.timeout:
                if k:
                    dct[k] = _filter_result('<timeout>',k,cmd,  expected_pattern or self.expected_pattern,
                                                       unexpected_pattern or self.unexpected_pattern,
                                                       filter or self.filter)
        if auto_close:
            self.close()
        return dct

class Snmp(object):
    r"""Snmp class helper

    This class helps to collect OIDs from a remote snmpd server. One can issue some snmpget and/or
    snmpwalk. Protocols 1, 2c and 3 are managed. It uses pysnmp library.

    Args:

        host (str): IP address or hostname to connect to
        community (str): community to use (For protocol 1 and 2c)
        version (int): protocol to use : None, 1,2,'2c' or 3 (Default: None). If None, it will use
            protocol 3 if a user is specified, 2c otherwise.
        timeout (int): Time in seconds before raising an error or a None value
        port (int): port number to use (Default : 161 UDP)
        user (str): protocol V3 authentication user
        auth_passwd (str): snmp v3 authentication password
        auth_protocol (str): snmp v3 auth protocol ('md5' or 'sha')
        priv_passwd (str): snmp v3 privacy password
        priv_protocol (str): snmp v3 privacy protocol ('des' or 'aes')
    """
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
                raise ConnectionError('user must be not empty')
            self.cmd_args.append(cmdgen.UsmUserData(user, auth_passwd, priv_passwd,
                authProtocol=authProtocol,
                privProtocol=privProtocol ) )
        else:
            raise ConnectionError('Bad snmp version protocol, given : %s, possible : 1,2,2c,3' % version)

        self.cmd_args.append(cmdgen.UdpTransportTarget((host, port),timeout = timeout/3, retries=2))

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
            val = textops.StrExt(oval.prettyPrint())
        elif isinstance(oval, v2c.IpAddress):
            val = textops.StrExt(oval.prettyPrint())
        else:
            val = oval
        return val

    def normalize_oid(self,oid):
        """Normalize OID object in order to be used with pysnmp methods

        Basically, it converts OID with a tuple form into a ObjectIdentity form,
        keeping other forms unchanged.

        Args:

            oid (str,tuple or ObjectIdentity): The OID to normalize

        Returns:

            str or ObjectIdentity: OID form that is ready to be used with pysnmp

        Examples:

            >>> s=Snmp('demo.snmplabs.com')
            >>> s.normalize_oid(('SNMPv2-MIB', 'sysDescr2', 0))
            ObjectIdentity('SNMPv2-MIB', 'sysDescr2', 0)
            >>> s.normalize_oid('1.3.6.1.2.1.1.1.0')
            '1.3.6.1.2.1.1.1.0'

        """
        if isinstance(oid,tuple):
            return self.cmdgen.MibVariable(*oid)
        return oid

    def get(self,oid_or_mibvar):
        """get one OID

        Args:

            oid_or_mibvar (str or ObjectIdentity): an OID path or a pysnmp ObjectIdentity

        Returns:

            :class:`textops.StrExt` or int: OID value. The python type depends on OID MIB type.

        Examples:

            To collect a numerical OID::

                >>> snmp = Snmp('demo.snmplabs.com')
                >>> snmp.get('1.3.6.1.2.1.1.1.0')
                'SunOS zeus.snmplabs.com 4.1.3_U1 1 sun4m'

            To collect an OID with label form::

                >>> snmp = Snmp('demo.snmplabs.com')
                >>> snmp.get('iso.org.dod.internet.mgmt.mib-2.system.sysDescr.0')
                'SunOS zeus.snmplabs.com 4.1.3_U1 1 sun4m'

            To collect an OID with MIB symbol form::

                >>> snmp = Snmp('demo.snmplabs.com')
                >>> snmp.get(('SNMPv2-MIB', 'sysDescr', 0))
                'SunOS zeus.snmplabs.com 4.1.3_U1 1 sun4m'
        """
        oid_or_mibvar = self.normalize_oid(oid_or_mibvar)
        args = list(self.cmd_args)
        args.append(oid_or_mibvar)
        errorIndication, errorStatus, errorIndex, varBinds = self.cmdGenerator.getCmd(*args)
        if errorIndication:
            raise CollectError(errorIndication)
        else:
            if errorStatus:
                try:
                    err_at = errorIndex and varBinds[int(errorIndex)-1] or '?'
                except:
                    err_at = '?'
                raise CollectError('%s at %s' % (errorStatus.prettyPrint(),err_at) )
        return self.to_native_type(varBinds[0][1])

    def walk(self,oid_or_mibvar):
        """Walk from a OID root path

        Args:

            oid_or_mibvar (str or ObjectIdentity): an OID path or a pysnmp ObjectIdentity

        Returns:

            :class:`textops.ListExt`: List of tuples (OID,value).
                Values type are int or :class:`textops.StrExt`

        Example:

            >>> snmp = Snmp('localhost')
            >>> for oid,val in snmp.walk('1.3.6.1.2.1.1'):  #doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
            ...     print oid,'-->',val
            ...
            1.3.6.1.2.1.1.1.0 --> SunOS zeus.snmplabs.com 4.1.3_U1 1 sun4m
            1.3.6.1.2.1.1.2.0 --> 1.3.6.1.4.1.20408
                 ...

        """
        oid_or_mibvar = self.normalize_oid(oid_or_mibvar)
        lst = textops.ListExt()
        args = list(self.cmd_args)
        args.append(oid_or_mibvar)
        errorIndication, errorStatus, errorIndex, varBindTable = self.cmdGenerator.nextCmd(*args)
        if errorIndication:
            raise CollectError(errorIndication)
        else:
            if errorStatus:
                try:
                    err_at = errorIndex and varBindTable[-1][int(errorIndex)-1] or '?'
                except:
                    err_at = '?'
                raise CollectError('%s at %s' % (errorStatus.prettyPrint(),err_at) )
        for varBindTableRow in varBindTable:
            for name, val in varBindTableRow:
                lst.append((str(name),self.to_native_type(val)))
        return lst

    def mwalk(self,vars_oids):
        """Walk from multiple OID root pathes

        Args:

            vars_oids (dict): keyname/OID root path dictionary

        Returns:

            :class:`textops.DictExt`: A dictionary of list of tuples (OID,value).
                Values type are int or :class:`textops.StrExt`

        Example:

            >>> snmp = Snmp('localhost')
            >>> print snmp.mwalk({'node1' : '1.3.6.1.2.1.1.9.1.2', 'node2' : '1.3.6.1.2.1.1.9.1.3'})
            {'node1': [('1.3.6.1.2.1.1.9.1.2.1', ObjectIdentity(ObjectIdentifier('1.3.6.1.6.3.10.3.1.1'))),
                       ('1.3.6.1.2.1.1.9.1.2.2', ObjectIdentity(ObjectIdentifier('1.3.6.1.6.3.11.3.1.1')))
                       ... ],
             'node2': [('1.3.6.1.2.1.1.9.1.3.1', 'The SNMP Management Architecture MIB.'),
                       ('1.3.6.1.2.1.1.9.1.3.2', 'The MIB for Message Processing and Dispatching.'),
                       ... ]}

        """
        dct = textops.DictExt()
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
            raise CollectError('An OID range must have one and only one "-"')
        return oids

    def mget(self,vars_oids):
        """Get multiple OIDs at the same time

        This method is much more faster than doing multiple :meth:`get` because it uses the same
        network request. In addition, one can request a range of OID. To build a range, just use a
        dash between to integers : this OID will be expanded with all integers in between :
        For instance, '1.3.6.1.2.1.1.2-4.1' means : [ 1.3.6.1.2.1.1.2.1,
        1.3.6.1.2.1.1.3.1, 1.3.6.1.2.1.1.4.1 ]

        Args:

            vars_oids (dict): keyname/OID dictionary

        Returns:

            :class:`textops.DictExt`: List of tuples (OID,value).
                Values type are int or :class:`textops.StrExt`

        Example:

            >>> snmp = Snmp('demo.snmplabs.com')
            >>> print snmp.mget({'uname':'1.3.6.1.2.1.1.0','other':'1.3.6.1.2.1.1.2-9.0'})  #doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
            {'uname' : 'SunOS zeus.snmplabs.com 4.1.3_U1 1 sun4m',
             'other' : ['value for 1.3.6.1.2.1.1.2.0', 'value for 1.3.6.1.2.1.1.3.0', etc... ] }

        """
        dct = textops.DictExt()
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
            raise CollectError(errorIndication)
        else:
            if errorStatus:
                try:
                    err_at = errorIndex and varBinds[int(errorIndex)-1] or '?'
                except:
                    err_at = '?'
                raise CollectError('%s at %s' % (errorStatus.prettyPrint(),err_at) )
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
