# -*- coding: utf-8 -*-
#
# Creation : 2016-03-01
#
# author: Eric Lapouyade
#
"""This module contains mixins to extended naghelp with some additional features"""

from naghelp import *
from textops import *

__all__ = ['GaugeMixin','GaugeException']

class GaugeException(Exception):
    pass

class GaugeMixin(object):
    """ Gauge response helper Mixin

    This mixin helps to build a response when one expect a value (gauge) to not move up,down or
    to be in range. it has be to be declared in the parent classes of a plugin class,
    before ActivePlugin class. Methods have to be used into :meth:`naghelp.ActivePlugin.build_response`
    method. One must call the ``super`` :meth:`naghelp.ActivePlugin.build_response` at the end

    Example::

        MyPluginWithGauges(GaugeMixin, ActivePlugin):
            ...
            def build_response(self,data):
                ...
                self.gauge_response_etalon_down('fan',   'Fans',   data.boards.grep('Fan Tray').grepc('OK'), WARNING )
                self.gauge_response_etalon_down('board', 'Boards', data.boards.grep('SB|IB').grepc('Available|Assigned'), WARNING )
                self.gauge_response_etalon_down('power', 'Powers', data.boards.grep('^PS').grepc('OK'), WARNING )
                ...
                super(MyPluginWithGauges,self).build_response(data)
    """

    def gauge_response_threshold_list(self,id,label_values,warn_min=None,crit_min=None,warn_max=None,crit_max=None):
        """Test a list of values and add a WARNING or CRITICAL response if the value is out of range

        It calls :meth:`gauge_response_threshold` for each ``(label,value)`` specified in the
        ``label_values`` list.

        Args:

            id (str): The id of the gauge : an arbitrary string without space (aka slug).
                This is used for debug purposes.
            label_values (list): A list of tuple ``(label,value)`` where ``label`` is the gauge
                meaning and ``value`` is the value to test.
            warn_min (int or float): The lower threshold for WARNING response
            crit_min (int or float): The lower threshold for CRITICAL response
            warn_max (int or float): The upper threshold for WARNING response
            crit_max (int or float): The upper threshold for CRITICAL response
        """
        for i,(label,value) in enumerate(label_values):
            self.gauge_response_threshold('%s%s' % (id,i),label,value,warn_min=warn_min,crit_min=crit_min,warn_max=warn_max,crit_max=crit_max)

    def gauge_response_threshold(self,id,label,value,warn_min=None,crit_min=None,warn_max=None,crit_max=None):
        """Test a value and add a WARNING or CRITICAL response if the value is out of range

        It also add gauges value in the response's additional informations section

        Args:

            id (str): The id of the gauge : an arbitrary string without space (aka slug).
                This is used for debug purposes.
            label (str): The gauge meaning. This will be used to build the response message
            value (str, int or float): The value to test. If the value is a string, it will detect
                the first numeric value.
            warn_min (int or float): The lower threshold for WARNING response
            crit_min (int or float): The lower threshold for CRITICAL response
            warn_max (int or float): The upper threshold for WARNING response
            crit_max (int or float): The upper threshold for CRITICAL response

        Example:

            >>> class MyPluginWithGauges(GaugeMixin, ActivePlugin):
            ...     pass
            ...
            >>> p=MyPluginWithGauges()
            >>> p.gauge_response_threshold('test','Test gauge','90',0,10,70,100)
            >>> print p.response                         #doctest: +NORMALIZE_WHITESPACE
            Test gauge : 90 >= MAX WARNING (70)
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( WARNING )-----------------------------------------------------------------
            Test gauge : 90 >= MAX WARNING (70)
            <BLANKLINE>
            ==========================[ Additionnal informations ]==========================
            Test gauge : 90
            >>> p=MyPluginWithGauges()
            >>> p.gauge_response_threshold('test','Test gauge','-10',0,10,70,100)
            >>> print p.response                         #doctest: +NORMALIZE_WHITESPACE
            Test gauge : -10 <= MIN CRITICAL (10)
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Test gauge : -10 <= MIN CRITICAL (10)
            <BLANKLINE>
            ==========================[ Additionnal informations ]==========================
            Test gauge : -10
            >>> p=MyPluginWithGauges()
            >>> p.gauge_response_threshold('test','Test gauge','Temperature=110C',0,10,70,100)
            >>> print p.response                         #doctest: +NORMALIZE_WHITESPACE
            Test gauge : 110 >= MAX CRITICAL (100)
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Test gauge : 110 >= MAX CRITICAL (100)
            <BLANKLINE>
            ==========================[ Additionnal informations ]==========================
            Test gauge : Temperature=110C
            <BLANKLINE>
        """
        self.response.add_more('%s : %s',label,value)
        self.debug('Gauge id=%s, value=%s (warn_min=%s,crit_min=%s,warn_max=%s,crit_max=%s)',id,value,warn_min,crit_min,warn_max,crit_max)
        if isinstance(value,basestring):
            value = find_pattern.op(value,r'(-?[\d,\.]+)').replace(',','.')
            if value:
                if '.' in value:
                    value=float(value)
                else:
                    value=int(value)
        if isinstance(value,(int,float)):
            if isinstance(crit_min,(int,float)) and value <= crit_min:
                self.response.add(CRITICAL,'%s : %s <= MIN CRITICAL (%s)' % (label, value, crit_min))
            elif isinstance(warn_min,(int,float)) and value <= warn_min:
                self.response.add(WARNING,'%s : %s <= MIN WARNING (%s)' % (label, value, warn_min))
            elif isinstance(crit_max,(int,float)) and value >= crit_max:
                self.response.add(CRITICAL,'%s : %s >= MAX CRITICAL (%s)' % (label, value, crit_max))
            elif isinstance(warn_max,(int,float)) and value >= warn_max:
                self.response.add(WARNING,'%s : %s >= MAX WARNING (%s)' % (label, value, warn_max))

    def gauge_response_etalon_change_list(self,id,label_values,level):
        """Call :meth:`gauge_response_etalon_change` for all ``(label,values)`` tuple in the list ``label_values`` """
        for i,(label,value) in enumerate(label_values):
            self.gauge_response_etalon_change('%s%s' % (id,i),label,value,level)

    def gauge_response_etalon_change(self,id,label,value,level):
        """Remember a value, detect if it has changed

        At the first call the value is stored in host persistent data. The next times, it adds
        a CRITICAL or WARNING response if the value has changed.

        Args:

            id (str): The id of the gauge : an arbitrary string without space (aka slug).
                This is used for storing the value in persistent data and for debug purposes.
            label (str): The gauge meaning. This will be used to build the response message
            value (any): The value to test
            level (:class:`naghelp.ResponseLevel`): WARNING or CRITICAL

        Example:

            >>> from plugin_commons import *
            >>> class MyPluginWithGauges(GaugeMixin, ActivePlugin):
            ...     pass
            ...
            >>> p=MyPluginWithGauges()
            >>> p.doctest_begin()
            >>> p.gauge_response_etalon_change('tempcursor','Temperature cursor',20,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            OK
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 20
            >>> p.doctest_end()
            >>> p=MyPluginWithGauges()
            >>> p.doctest_begin()
            >>> p.gauge_response_etalon_change('tempcursor','Temperature cursor',21,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            Temperature cursor : actual value (21) has changed (was 20)
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Temperature cursor : actual value (21) has changed (was 20)
            <BLANKLINE>
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 21
            >>> p.doctest_end()
            >>> p=MyPluginWithGauges()
            >>> p.doctest_begin()
            >>> p.gauge_response_etalon_change('tempcursor','Temperature cursor',21,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            OK
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 21
            >>> p.doctest_end()
        """
        self.response.add_more('%s : %s',label,value)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
        if etalon_value is not None and value != etalon_value:
            self.response.add(level,'%s : actual value (%s) has changed (was %s)' % (label, value, etalon_value))
        if value not in [ NoAttr, None ]:
            # save the gauge value as the new reference value in host's persistent data
            self.host.set(etalon_name,value)

    def gauge_response_etalon_down_list(self,id,label_values,level):
        """Call :meth:`gauge_response_etalon_down` for all ``(label,values)`` tuple in the list ``label_values`` """
        for i,(label,value) in enumerate(label_values):
            self.gauge_response_etalon_down('%s%s' % (id,i),label,value,level)

    def gauge_response_etalon_down(self,id,label,value,level):
        """ qsdqsqsd """
        self.response.add_more('%s : %s',label,value)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
        if etalon_value is not None and value < etalon_value:
            self.response.add(level,'%s : actual value (%s) is less than the reference value (%s)' % (label, value, etalon_value))
        if isinstance(value,(int,float)):
            # save the gauge value as the new reference value in host's persistent data
            self.host.set(etalon_name,value)

    def gauge_response_etalon_up_list(self,id,label_values,level):
        """Call :meth:`gauge_response_etalon_up` for all ``(label,values)`` tuple in the list ``label_values`` """
        for i,(label,value) in enumerate(label_values):
            self.gauge_response_etalon_up('%s%s' % (id,i),label,value,level)

    def gauge_response_etalon_up(self,id,label,value,level):
        """ qsdqsqsd """
        self.response.add_more('%s : %s',label,value)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
        if etalon_value is not None and value > etalon_value:
            self.response.add(level,'%s : actual value (%s) is more than the reference value (%s)' % (label, value, etalon_value))
        if isinstance(value,(int,float)):
            # save the gauge value as the new reference value in host's persistent data
            self.host.set(etalon_name,value)