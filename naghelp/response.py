# -*- coding: utf-8 -*-
#
# Création : July 8th, 2015
#
# @author: Eric Lapouyade
#

import sys
import naghelp
from types import NoneType
import re

__all__ = [ 'ResponseLevel', 'PluginResponse', 'OK', 'WARNING', 'CRITICAL', 'UNKNOWN', 'LevelComment' ]

class ResponseLevel(object):
    """Object to use when exiting a naghelp plugin

    Instead of using numeric code that may be hard to memorize, predefined objects has be created :

    =====================   =========
    Response level object   exit code
    =====================   =========
    OK                      0
    WARNING                 1
    CRITICAL                2
    UNKNOWN                 3
    =====================   =========

    To exit a plugin with the correct exit code number, one have just to call the :meth:`exit` method
    of the wanted ResonseLevel object
    """
    def __init__(self, name, exit_code):
        self.name = name
        self.exit_code = exit_code

    def __repr__(self):
        return self.name

    def info(self):
        """Get name and exit code for a Response Level

        Examples:

            >>> level = CRITICAL
            >>> level.info()
            'CRITICAL (exit_code=2)'
            >>> level.name
            'CRITICAL'
            >>> level.exit_code
            2
        """
        return '%s (exit_code=%s)' % (self.name,self.exit_code)

    def exit(self):
        """This is the official way to exit a naghelp plugin

        Example:

            >>> level = CRITICAL
            >>> level.exit()  #doctest: +SKIP
                SystemExit: 2
        """
        sys.exit(self.exit_code)

OK       = ResponseLevel('OK',0)
WARNING  = ResponseLevel('WARNING',1)
CRITICAL = ResponseLevel('CRITICAL',2)
UNKNOWN  = ResponseLevel('UNKNOWN',3)

class LevelComment(str):
    pass

class PluginResponse(object):
    """Response to return to Nagios for a naghelp plugin

    Args:

        default_level (:class:`ResponseLevel`): The level to return when no level messages
            has been added to the response (for exemple when no error has be found).
            usually it is set to ``OK`` or ``UNKNOWN``

    A naghelp response has got many sections :

        * A synopsis (The first line that is directl visible onto Nagios interface)
        * A body (informations after the first line, only visible in detailed views)
        * Some performance Data

    The body itself has got some sub-sections :

        * Begin messages (Usually for a title, an introduction ...)
        * Levels messages, that are automatically splitted into Nagios levels in this order:

            * Critical messages
            * Warning messages
            * Unkown messages
            * OK messages

        * More messages (Usually to give more information about the monitored host)
        * End messages (Custom conclusion messages. naghelp :class:`Plugin` use this section
            to add automatically some informations about the plugin.

    Each section can be updated by adding a message through dedicated methods.

    PluginResponse object takes care to calculate the right ResponseLevel to return to Nagios :
    it will depend on the Levels messages you will add to the plugin response. For example,
    if you add one ``OK`` message and one ``WARNING`` message, the response level will be
    ``WARNING``. if you add again one ``CRITICAL`` message then an ``OK`` message , the response
    level will be ``CRITICAL``.

    About the synopsis section : if not manualy set, the PluginResponse class will build one for
    you : It will be the unique level message if you add only one in the response or a summary
    giving the number of messages in each level.

    Examples:

        >>> r = PluginResponse(OK)
        >>> print r
        OK
        <BLANKLINE>

    """
    def __init__(self,default_level=OK):
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
        """Manually set the response level

        Args:

            level (:class:`ResponseLevel`): OK, WARNING, CRITICAL or UNKNOWN

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.level
            None
            >>> r.set_level(WARNING)
            >>> print r.level
            WARNING
        """
        if not isinstance(level,ResponseLevel):
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))
        if self.level in [ None, UNKNOWN ] or level == CRITICAL or self.level == OK and level == WARNING:
            self.level = level

    def get_current_level(self):
        """get current level

        If no level has not been set yet, it will return the default_level.
        Use this method if you want to know what ResponseLevel will be sent.

        Returns:

            :class:`ResponseLevel` : the response level to be sent

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.get_current_level()
            OK
            >>> r.set_level(WARNING)
            >>> print r.get_current_level()
            WARNING
        """
        return self.default_level if self.level is None else self.level

    def set_sublevel(self, sublevel):
        """sets sublevel attribute

        Args:

            sublevel (int): 0,1,2 or 3  (Default : 0)

        From time to time, the CRITICAL status meaning is not detailed enough :
        It may be useful to color it by a sub-level.
        The ``sublevel`` value is not used directly by :class:`PluginResponse`,
        but by :class:`ActivePlugin` class which adds a ``__sublevel__=<sublevel>`` string
        in the plugin informations section. This string can be used for external filtering.

        Actually, the sublevel meanings are :

        =========  ===========================================================================
        Sub-level  Description
        =========  ===========================================================================
        0          The plugin is 100% sure there is a critical error
        1          The plugin was able to contact remote host but got no answer from agent
        2          The plugin was unable to contact the remote host, it may be a network issue
        3          The plugin raised an unexpected exception : it should be a bug.
        =========  ===========================================================================
        """
        if not isinstance(sublevel,int):
            raise Exception('A response sublevel must be an integer')
        self.sublevel = sublevel

    def get_sublevel(self):
        """get sublevel

        Returns:

            int: sublevel (0,1,2 or 3)

        Exemples:

            >>> r = PluginResponse(OK)
            >>> print r.get_sublevel()
            0
            >>> r.set_sublevel(2)
            >>> print r.get_sublevel()
            2
        """
        return self.sublevel


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
        r"""Add a message in begin section

        You can use this method several times and at any time until the :meth:`send` is used.
        The messages will be displayed in begin section in the same order as they have been added.
        This method does not change the calculated ResponseLevel.

        Args:

            msg (str): the message to add in begin section.
            args (list): if additionnal arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are given,
                ``msg`` will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> r.add_begin('='*40)
            >>> r.add_begin('{hostname:^40}', hostname='MyHost')
            >>> r.add_begin('='*40)
            >>> r.add_begin('Date : %s, Time : %s','2105-12-18','14:55:11')
            >>> r.add_begin('\n')
            >>> r.add(CRITICAL,'This is critical !')
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            This is critical !
            ========================================
                             MyHost
            ========================================
            Date : 2105-12-18, Time : 14:55:11
            <BLANKLINE>
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            <BLANKLINE>
        """
        self.begin_msgs.append(self._reformat_msg(msg,*args,**kwargs))

    def add(self,level,msg,*args,**kwargs):
        r"""Add a message in levels messages section and sets the response level at the same time

        Use this method each time your plugin detects a WARNING or a CRITICAL error. You can also
        use this method to add a message saying there is an UNKNOWN or OK state somewhere.
        You can use this method several times and at any time until the :meth:`send` is used.
        This method updates the calculated ResponseLevel.
        When the response is rendered, the added messages are splitted into sub-section

        Args:

            level (ResponseLevel): the message level (Will affect the final response level)
            msg (str): the message to add in levels messages section.
            args (list): if additionnal arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are given,
                ``msg`` will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.get_current_level()
            OK
            >>> r.add(CRITICAL,'The system crashed')
            >>> r.add(WARNING,'Found some almost full file system')
            >>> r.add(UNKNOWN,'Cannot find FAN %s status',0)
            >>> r.add(OK,'Power {power_id} is ON',power_id=1)
            >>> print r.get_current_level()
            CRITICAL
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            STATUS : CRITICAL:1, WARNING:1, UNKNOWN:1, OK:1
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            The system crashed
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            Found some almost full file system
            <BLANKLINE>
            ----( UNKNOWN )-----------------------------------------------------------------
            Cannot find FAN 0 status
            <BLANKLINE>
            ----( OK )----------------------------------------------------------------------
            Power 1 is ON
            <BLANKLINE>
            <BLANKLINE>
        """
        if isinstance(level,ResponseLevel):
            self.level_msgs[level].append(self._reformat_msg(msg,*args,**kwargs))
            self.set_level(level)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_comment(self,level,msg,*args,**kwargs):
        r"""Add a comment in levels messages section and sets the response level at the same time

        it works like :meth:`add` except that the message is not counted into the synopsis

        Args:

            level (ResponseLevel): the message level (Will affect the final response level)
            msg (str): the message to add in levels messages section.
            args (list): if additionnal arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are given,
                ``msg`` will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.get_current_level()
            OK
            >>> r.add_comment(CRITICAL,'Here are some errors')
            >>> r.add(CRITICAL,'error 1')
            >>> r.add(CRITICAL,'error 2')
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            STATUS : CRITICAL:2
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Here are some errors
            error 1
            error 2
            <BLANKLINE>
            <BLANKLINE>
        """
        if isinstance(level,ResponseLevel):
            self.level_msgs[level].append(LevelComment(self._reformat_msg(msg,*args,**kwargs)))
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_list(self,level,msg_list,header=None,footer=None,*args,**kwargs):
        """Add several level messages having a same level

        Sometimes, you may have to specify a list of faulty parts in the response : this can be done
        by this method in a single line. If a message is empty in the list, it is not added.

        Args:

            level (ResponseLevel): the message level (Will affect the final response level)
            msg_list (list): the messages list to add in levels messages section.
            header (str): Displayed before the message as a level comment if not None (Default : None)
              one can use ``{_len}`` in the comment to get list count.
            footer (str): Displayed after the message as a level comment if not None (Default : None)
              one can use ``{_len}`` in the comment to get list count.
            args (list): if additionnal arguments are given, messages in ``msg_list``
                will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are given, messages in ``msg_list``
                will be formatted with :meth:`str.format`


        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.get_current_level()
            OK
            >>> logs = '''
            ... Power 0 is critical
            ... Power 1 is OK
            ... Power 2 is degraded
            ... Power 3 is failed
            ... Power 4 is OK
            ... Power 5 is degraded
            ... '''
            >>> from textops import grep
            >>> criticals = logs >> grep('critical|failed')
            >>> warnings = logs >> grep('degraded|warning')
            >>> print criticals
            ['Power 0 is critical', 'Power 3 is failed']
            >>> print warnings
            ['Power 2 is degraded', 'Power 5 is degraded']
            >>> r.add_list(CRITICAL,criticals)
            >>> r.add_list(WARNING,warnings)
            >>> print r.get_current_level()
            CRITICAL
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            STATUS : CRITICAL:2, WARNING:2
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Power 0 is critical
            Power 3 is failed
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            Power 2 is degraded
            Power 5 is degraded
            <BLANKLINE>
            <BLANKLINE>

            >>> r = PluginResponse()
            >>> r.add_list(WARNING,['Power warning1','Power warning2'],'{_len} Power warnings:','Power warnings : {_len}')
            >>> r.add_list(WARNING,['CPU warning1','CPU warning2'],'{_len} CPU warnings:','CPU warnings : {_len}')
            >>> print r
            STATUS : WARNING:4
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            2 Power warnings:
            Power warning1
            Power warning2
            Power warnings : 2
            2 CPU warnings:
            CPU warning1
            CPU warning2
            CPU warnings : 2
            <BLANKLINE>
            <BLANKLINE>
        """

        have_added=False
        kwargs['_len'] = len(msg_list)
        for msg in msg_list:
            if msg:
                if not have_added and header is not None:
                    self.add_comment(level, header,*args,**kwargs)
                self.add(level, msg,*args,**kwargs)
                have_added = True
        if have_added and footer is not None:
            self.add_comment(level, footer,*args,**kwargs)

    def add_many(self,lst,*args,**kwargs):
        """Add several level messages NOT having a same level

        This works like :meth:`add_list` except that instead of giving a list of messages one have
        to specify a list of tuples (level,message). By this way, one can give a level to each
        message into the list. If a message is empty in the list, it is not added.

        Args:

            lst (list): A list of (level,message) tuples to add in levels messages section.
            args (list): if additionnal arguments are given, messages in ``lst``
                will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are given, messages in ``lst``
                will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.get_current_level()
            OK
            >>> logs = '''
            ... Power 0 is critical
            ... Power 1 is OK
            ... Power 2 is degraded
            ... Power 3 is failed
            ... Power 4 is OK
            ... Power 5 is degraded
            ... '''
            >>> from textops import *
            >>> errors = [ (CRITICAL if error|haspatterni('critical|failed') else WARNING,error)
            ...            for error in logs | grepv('OK') ]
            >>> print errors  #doctest: +NORMALIZE_WHITESPACE
            [(WARNING, ''), (CRITICAL, 'Power 0 is critical'), (WARNING, 'Power 2 is degraded'),
            (CRITICAL, 'Power 3 is failed'), (WARNING, 'Power 5 is degraded')]
            >>> r.add_many(errors)
            >>> print r.get_current_level()
            CRITICAL
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            STATUS : CRITICAL:2, WARNING:2
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Power 0 is critical
            Power 3 is failed
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            Power 2 is degraded
            Power 5 is degraded
            <BLANKLINE>
            <BLANKLINE>
        """
        for level,msg in lst:
            if msg:
                self.add(level, msg,*args,**kwargs)

    def add_if(self, test, level, msg=None, header=None,footer=None, *args,**kwargs):
        r"""Test than add a message in levels messages section and sets the response level at the same time

        This works like :meth:`add` except that it is conditionnal : ``test`` must be True.
        If no message is given, the value of ``test`` is used.

        Args:

            test (any): the message is added to the response only if bool(test) is True.
            level (ResponseLevel): the message level (Will affect the final response level)
            msg (str): the message to add in levels messages section.
                If no message is given, the value of test is used.
            header (str): Displayed before the message as a level comment if not None (Default : None)
            footer (str): Displayed after the message as a level comment if not None (Default : None)
            args (list): if additionnal arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are given,
                ``msg`` will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.get_current_level()
            OK
            >>> logs = '''
            ... Power 0 is critical
            ... Power 1 is OK
            ... Power 2 is degraded
            ... Power 3 is failed
            ... Power 4 is OK
            ... Power 5 is degraded
            ... '''
            >>> from textops import *
            >>> nb_criticals = logs | grepc('critical|failed')
            >>> print nb_criticals
            2
            >>> warnings = logs | grep('degraded|warning').tostr()
            >>> print warnings
            Power 2 is degraded
            Power 5 is degraded
            >>> unknowns = logs | grep('unknown').tostr()
            >>> print unknowns
            <BLANKLINE>
            >>> r.add_if(nb_criticals,CRITICAL,'{n} power(s) are critical',n=nb_criticals)
            >>> r.add_if(warnings,WARNING)
            >>> r.add_if(unknowns,UNKNOWN)
            >>> print r.get_current_level()
            CRITICAL
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            STATUS : CRITICAL:1, WARNING:1
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            2 power(s) are critical
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            Power 2 is degraded
            Power 5 is degraded
            <BLANKLINE>
            <BLANKLINE>
        """
        if msg is None:
            msg = test
        if isinstance(level,ResponseLevel):
            if test:
                if header is not None:
                    self.add_comment(level, header,*args,**kwargs)
                self.add(level,msg,*args,**kwargs)
                if footer is not None:
                    self.add_comment(level, footer,*args,**kwargs)
                self.set_level(level)
        else:
            raise Exception('A response level must be an instance of ResponseLevel, Found level=%s (%s).' % (level,type(level)))

    def add_elif(self,*add_ifs,**kwargs):
        r"""Multi-conditionnal message add

        This works like :meth:`add_if` except that it accepts multiple tests.
        Like python ``elif``, the method stops on first True test and send corresponding message.
        If you want to build the equivalent of a *default* message, just use ``True`` as the last
        test.

        Args:

            add_ifs (list): list of tuple (test,level,message).
            kwargs (dict): if named arguments are given,
                messages will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> print r.get_current_level()
            OK
            >>> logs = '''
            ... Power 0 is critical
            ... Power 1 is OK
            ... Power 2 is degraded
            ... Power 3 is failed
            ... Power 4 is OK
            ... Power 5 is degraded
            ... Power 6 is smoking
            ... '''
            >>> from textops import *
            >>> for log in logs | rmblank():
            ...     r.add_elif( (log|haspattern('critical|failed'), CRITICAL, log),
            ...                 (log|haspattern('degraded|warning'), WARNING, log),
            ...                 (log|haspattern('OK'), OK, log),
            ...                 (True, UNKNOWN, log) )
            >>> print r.get_current_level()
            CRITICAL
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            STATUS : CRITICAL:2, WARNING:2, UNKNOWN:1, OK:2
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Power 0 is critical
            Power 3 is failed
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            Power 2 is degraded
            Power 5 is degraded
            <BLANKLINE>
            ----( UNKNOWN )-----------------------------------------------------------------
            Power 6 is smoking
            <BLANKLINE>
            ----( OK )----------------------------------------------------------------------
            Power 1 is OK
            Power 4 is OK
            <BLANKLINE>
            <BLANKLINE>
        """
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
        r"""Add a message in "more messages" section (aka "Additionnal informations")

        You can use this method several times and at any time until the :meth:`send` is used.
        The messages will be displayed in the section in the same order as they have been added.
        This method does not change the calculated ResponseLevel.

        Args:

            msg (str): the message to add in end section.
            args (list): if additional arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are give,
                ``msg`` will be formatted with :meth:`str.format`

        Note:

            The "Additionnal informations" section title will be added automatically if the section is
            not empty.

        Examples:

            >>> r = PluginResponse(OK)
            >>> r.add(CRITICAL,'This is critical !')
            >>> r.add_more('Date : %s, Time : %s','2105-12-18','14:55:11')
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            This is critical !
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            ==========================[ Additionnal informations ]==========================
            Date : 2105-12-18, Time : 14:55:11
        """
        if msg:
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
        r"""Add a message in end section

        You can use this method several times and at any time until the :meth:`send` is used.
        The messages will be displayed in end section in the same order as they have been added.
        This method does not change the calculated ResponseLevel.

        Args:

            msg (str): the message to add in end section.
            args (list): if additional arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are give,
                ``msg`` will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> r.add_end('='*40)
            >>> r.add_end('{hostname:^40}', hostname='MyHost')
            >>> r.add_end('='*40)
            >>> r.add_end('Date : %s, Time : %s','2105-12-18','14:55:11')
            >>> r.add_end('\n')
            >>> r.add(CRITICAL,'This is critical !')
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            This is critical !
            <BLANKLINE>
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            <BLANKLINE>
            ========================================
                             MyHost
            ========================================
            Date : 2105-12-18, Time : 14:55:11
        """
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
        r"""Add performance object into the response

        Args:

            data (str or :class:`~naghelp.PerfData`): the perf data string or PerfData object to add to
                the response. Have a look to
                `Performance data string syntax <http://nagios-plugins.org/doc/guidelines.html#AEN200>`_.

        Examples:

            >>> r = PluginResponse(OK)
            >>> r.add_begin('Begin\n')
            >>> r.add_end('End')
            >>> r.add_perf_data(PerfData('filesystem_/','55','%','95','98','0','100'))
            >>> r.add_perf_data(PerfData('filesystem_/usr','34','%','95','98','0','100'))
            >>> r.add_perf_data('cpu_wait=88%;40;60;0;100')
            >>> r.add_perf_data('cpu_user=12%;80;95;0;100')
            >>> print r
            OK|filesystem_/=55%;95;98;0;100
            Begin
            End|filesystem_/usr=34%;95;98;0;100
            cpu_wait=88%;40;60;0;100
            cpu_user=12%;80;95;0;100
        """
        if not isinstance(data,basestring):
            data = str(data)
        self.perf_items.append(data)

    def set_synopsis(self,msg,*args,**kwargs):
        r"""Sets the response synopsis.

        By default, if no synopsis has been set manually, the response synopsis (first line of
        the text returned by the plugin) will be :

            * The error message if there is only one level message
            * Otherwise, some statistics like : ``STATUS : CRITICAL:2, WARNING:2, UNKNOWN:1, OK:2``

        If something else is wanted, one can define a custom synopsis with this method.

        Args:

            msg (str): the synopsis.
            args (list): if additional arguments are given,
                ``msg`` will be formatted with ``%`` (old-style python string formatting)
            kwargs (dict): if named arguments are give,
                ``msg`` will be formatted with :meth:`str.format`

        Examples:

            >>> r = PluginResponse(OK)
            >>> r.add(CRITICAL,'This is critical !')
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            This is critical !
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            >>> r.set_synopsis('Mayday, Mayday, Mayday')
            >>> print r     #doctest: +NORMALIZE_WHITESPACE
            Mayday, Mayday, Mayday
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
        """
        if not isinstance(msg,basestring):
            msg = str(msg)
        if args:
            msg = msg % args
        if kwargs:
            msg = msg.format(**kwargs)
        self.synopsis = msg

    def get_default_synopsis(self):
        """Returns the default synopsis

        This method is called if no synopsis has been set manually, the response synopsis (first line of
        the text returned by the plugin) will be :

            * The error message if there is only one level message
            * Otherwise, some statistics like : ``STATUS : CRITICAL:2, WARNING:2, UNKNOWN:1, OK:2``

        If you want to have a different default synopsis, you can subclass the :class:`PluginResponse`
        class and redefine this method.

        Examples:
            >>> r = PluginResponse(OK)
            >>> r.add(CRITICAL,'This is critical !')
            >>> print r.get_default_synopsis()
            This is critical !
            >>> r.add(WARNING,'This is just a warning.')
            >>> print r.get_default_synopsis()
            STATUS : CRITICAL:1, WARNING:1
        """
        not_comment = lambda s:not isinstance(s, LevelComment)
        nb_ok = len(filter(not_comment,self.level_msgs[OK]))
        nb_nok = len(filter(not_comment,self.level_msgs[WARNING])) + len(filter(not_comment,self.level_msgs[CRITICAL])) + len(filter(not_comment,self.level_msgs[UNKNOWN]))
        if nb_ok + nb_nok == 0:
            return str(self.level or self.default_level or UNKNOWN)
        if nb_ok and not nb_nok:
            return str(OK)
        if nb_nok == 1:
            return filter(not_comment,self.level_msgs[WARNING] + self.level_msgs[CRITICAL] + self.level_msgs[UNKNOWN])[0]
        return 'STATUS : ' + ', '.join([ '%s:%s' % (level,len(filter(not_comment,self.level_msgs[level]))) for level in [CRITICAL, WARNING, UNKNOWN, OK ] if self.level_msgs[level] ])

    def section_format(self,title):
        """Returns the section title string

        This method is automatically called when the response is rendered by :meth:`get_outpout`.
        If you want to have a different output, you can subclass the :class:`PluginResponse`
        class and redefine this method.

        Args:

            title (str): the section name to be formatted

        Returns:

            str: The foramtted section title

        Example:

            >>> r = PluginResponse(OK)
            >>> print r.section_format('My section')
            =================================[ My section ]=================================
        """
        return '{0:=^80}'.format('[ {0:^8} ]'.format(title))

    def subsection_format(self,title):
        """Returns the subsection title string

        This method is automatically called when the response is rendered by :meth:`get_outpout`.
        If you want to have a different output, you can subclass the :class:`PluginResponse`
        class and redefine this method.

        Args:

            title (str): the subsection name to be formatted

        Returns:

            str: The foramtted subsection title

        Example:

            >>> r = PluginResponse(OK)
            >>> print r.subsection_format('My subsection')
            ----( My subsection )-----------------------------------------------------------
        """
        return '----' + '{0:-<76}'.format('( %s )' % title)

    def level_msgs_render(self):
        """Renders level messages

        This method is automatically called when the response is rendered by :meth:`get_outpout`.
        If you want to have a different output, you can subclass the :class:`PluginResponse`
        class and redefine this method.

        Returns:

            str: The foramtted level messages

        Example:

            >>> r = PluginResponse(OK)
            >>> r.add(CRITICAL,'This is critical !')
            >>> r.add(WARNING,'This is just a warning.')
            >>> print r.level_msgs_render()
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            This is just a warning.
            <BLANKLINE>
            <BLANKLINE>
        """
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
        """Escapes forbidden chars in messages

        Nagios does not accept the pipe symbol in messages because it is a separator for performance
        data. This method escapes or replace such forbidden chars.
        Default behaviour is to replace the pipe ``|`` by an exclamation mark ``!``.

        Args:

            msg(str): The message to escape

        Returns

            str : The escaped message
        """
        return msg.replace('|','!')

    def get_output(self):
        r"""Renders the whole response following the Nagios syntax

        This method is automatically called when the response is sent by :meth:`send`.
        If you want to have a different output, you can subclass the :class:`PluginResponse`
        class and redefine this method.

        Returns:

            str: The response text output following the Nagios syntax

        Note:

            As ``__str__`` directly calls :meth:`get_output`, printing a :class:`PluginResponse`
            object is equivalent to call :meth:`get_output`.

        Example:

            >>> r = PluginResponse(OK)
            >>> r.add(CRITICAL,'This is critical !')
            >>> r.add(WARNING,'This is just a warning.')

            >>> print r.get_output()
            STATUS : CRITICAL:1, WARNING:1
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            This is just a warning.
            <BLANKLINE>
            <BLANKLINE>

            >>> print r
            STATUS : CRITICAL:1, WARNING:1
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            This is critical !
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            This is just a warning.
            <BLANKLINE>
            <BLANKLINE>
        """
        synopsis_maxlen = 75
        synopsis = self.synopsis or self.get_default_synopsis()
        synopsis_lines = synopsis.splitlines()
        synopsis_first_line = synopsis_lines[0]
        synopsis_start = synopsis_first_line[:synopsis_maxlen]

        if synopsis_first_line[synopsis_maxlen:] or len(synopsis_lines)>1:
            synopsis_start += '...'

        out = self.escape_msg(synopsis_start)
        out +=  '|%s\n' % self.perf_items[0] if self.perf_items else '\n'

        if synopsis_first_line[synopsis_maxlen:]:
            out += '... %s\n' % self.escape_msg(synopsis_first_line[synopsis_maxlen:])

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
        r"""Send the response to Nagios

        This method is automatically called by :meth:`naghelp.ActivePlugin.run` method and
        follow these steps :

            * if defined, force a level, a sublevel, a synopsis or add a last message
            * render the response string following the Nagios syntax
            * display the string on stdout
            * exit the plugin with the exit code corresponding to the response level.

        Args:

            level(:class:`ResponseLevel`): force a level (optional),
            synopsis(str): force a synopsis (optional),
            msg(str): add a last level message (optional),
            sublevel(int): force a sublevel [0-3] (optional),
        """
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

        print out.encode('utf-8') if isinstance(out,unicode) else out

        naghelp.logger.info('Exiting plugin with response level : %s, __sublevel__=%s', self.level.info(), self.sublevel )
        self.level.exit()
