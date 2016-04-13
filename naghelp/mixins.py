# -*- coding: utf-8 -*-
#
# Creation : 2016-03-01
#
# author: Eric Lapouyade
#
"""This module contains mixins to extended naghelp with some additional features"""

from naghelp import *
from textops import *
import re
import time,datetime

__all__ = ['GaugeMixin','GaugeException','HostsManagerMixin']

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
        self.response.add_more('%s : %s',label,value,no_debug=True)
        if isinstance(value,basestring):
            value = find_pattern.op(value,r'(-?[\d,\.]+)').replace(',','.')
            if value:
                if '.' in value:
                    value=float(value)
                else:
                    value=int(value)
        self.debug('response -> Gauge id=%s, value=%s (warn_min=%s,crit_min=%s,warn_max=%s,crit_max=%s)',id,value,warn_min,crit_min,warn_max,crit_max)
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
        The new value is stored and become the new reference value.

        Args:

            id (str): The id of the gauge : an arbitrary string without space (aka slug).
                This is used for storing the value in persistent data and for debug purposes.
            label (str): The gauge meaning. This will be used to build the response message
            value (any): The value to test
            level (:class:`naghelp.ResponseLevel`): WARNING or CRITICAL

        Example:

            >>> class MyPluginWithGauges(GaugeMixin, ActivePlugin):
            ...     pass
            ...
            >>> p=MyPluginWithGauges()
            >>> p.doctest_begin()                    # only for doctest
            >>> p.gauge_etalon_clear('tempcursor')   # only for doctest
            >>> p.gauge_response_etalon_change('tempcursor','Temperature cursor',20,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            OK
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 20
            >>> p.doctest_end()
            >>> p=MyPluginWithGauges()
            >>> p.doctest_begin()                    # only for doctest
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
            >>> p.doctest_end()                      # only for doctest
            >>> p=MyPluginWithGauges()
            >>> p.doctest_begin()
            >>> p.gauge_response_etalon_change('tempcursor','Temperature cursor',21,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            OK
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 21
            >>> p.doctest_end()
        """
        self.response.add_more('%s : %s',label,value,no_debug=True)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('response -> Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
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
        """Remember a value, detect if it has changed by going down

        At the first call the value is stored in host persistent data. The next times, it adds
        a CRITICAL or WARNING response if the value has changed by going down.
        The new value is stored and become the new reference value.

        Args:

            id (str): The id of the gauge : an arbitrary string without space (aka slug).
                This is used for storing the value in persistent data and for debug purposes.
            label (str): The gauge meaning. This will be used to build the response message
            value (any): The value to test
            level (:class:`naghelp.ResponseLevel`): WARNING or CRITICAL

        Example:

            >>> class MyPluginWithGauges(GaugeMixin, ActivePlugin):
            ...     pass
            ...
            >>> p=MyPluginWithGauges()                   # 1st plugin execution
            >>> p.doctest_begin()                        # only for doctest
            >>> p.gauge_etalon_clear('tempcursor')       # only for doctest
            >>> p.gauge_response_etalon_down('tempcursor','Temperature cursor',20,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            OK
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 20
            >>> p.doctest_end()
            >>> p=MyPluginWithGauges()                   # 2nd plugin execution
            >>> p.doctest_begin()                        # only for doctest
            >>> p.gauge_response_etalon_down('tempcursor','Temperature cursor',19,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            Temperature cursor : actual value (19) is less than the reference value (20...
            ... )
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Temperature cursor : actual value (19) is less than the reference value (20)
            <BLANKLINE>
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 19
            >>> p.doctest_end()                          # only for doctest
            >>> p=MyPluginWithGauges()
            >>> p.doctest_begin()                        # only for doctest
            >>> p.gauge_response_etalon_down('tempcursor','Temperature cursor',19,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            OK
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 19
            >>> p.doctest_end()                          # only for doctest
        """
        self.response.add_more('%s : %s',label,value,no_debug=True)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('response -> Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
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
        """Remember a value, detect if it has changed by going up

        At the first call the value is stored in host persistent data. The next times, it adds
        a CRITICAL or WARNING response if the value has changed by going up.
        The new value is stored and become the new reference value.

        Args:

            id (str): The id of the gauge : an arbitrary string without space (aka slug).
                This is used for storing the value in persistent data and for debug purposes.
            label (str): The gauge meaning. This will be used to build the response message
            value (any): The value to test
            level (:class:`naghelp.ResponseLevel`): WARNING or CRITICAL

        Example:

            >>> class MyPluginWithGauges(GaugeMixin, ActivePlugin):
            ...     pass
            ...
            >>> p=MyPluginWithGauges()                   # 1st plugin execution
            >>> p.doctest_begin()                        # only for doctest
            >>> p.gauge_etalon_clear('tempcursor')       # only for doctest
            >>> p.gauge_response_etalon_up('tempcursor','Temperature cursor',20,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            OK
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 20
            >>> p.doctest_end()
            >>> p=MyPluginWithGauges()                   # 2nd plugin execution
            >>> p.doctest_begin()                        # only for doctest
            >>> p.gauge_response_etalon_up('tempcursor','Temperature cursor',21,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            Temperature cursor : actual value (21) is more than the reference value (20...
            ... )
            ==================================[  STATUS  ]==================================
            <BLANKLINE>
            ----( CRITICAL )----------------------------------------------------------------
            Temperature cursor : actual value (21) is more than the reference value (20)
            <BLANKLINE>
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 21
            >>> p.doctest_end()                          # only for doctest
            >>> p=MyPluginWithGauges()
            >>> p.doctest_begin()                        # only for doctest
            >>> p.gauge_response_etalon_up('tempcursor','Temperature cursor',21,CRITICAL)
            >>> print p.response                                  #doctest: +NORMALIZE_WHITESPACE
            OK
            ==========================[ Additionnal informations ]==========================
            Temperature cursor : 21
            >>> p.doctest_end()                          # only for doctest
        """
        self.response.add_more('%s : %s',label,value,no_debug=True)
        etalon_name = id + '_etalon'
        etalon_value = self.host.get(etalon_name,None)
        self.debug('response -> Gauge id=%s, was:%s, now:%s',id,etalon_value,value)
        if etalon_value is not None and value > etalon_value:
            self.response.add(level,'%s : actual value (%s) is more than the reference value (%s)' % (label, value, etalon_value))
        if isinstance(value,(int,float)):
            # save the gauge value as the new reference value in host's persistent data
            self.host.set(etalon_name,value)

    def gauge_etalon_clear(self,id):
        """Clear the reference value for an "etalon" gauge

        By this way, you ask the plugin to learn a new reference value

        Args:

            id (str): The id of the gauge
        """
        etalon_name = id + '_etalon'
        self.host.set(etalon_name,None)

    def gauge_etalon_set(self,id,value):
        """Force a reference value for an "etalon" gauge

        Args:

            id (str): The id of the gauge
            value (any): The value that will be the new reference value
        """
        etalon_name = id + '_etalon'
        self.host.set(etalon_name,value)

class HostsManagerMixin(object):
    managed_default_level = OK
    managed_service_description = 'ManagedHost'
    managed_response_retention_delta = 0
    managed_hosts = None
    managed_data_filename = '/tmp/managed_hosts.json'

    def __init__(self,*args,**kwargs):
        from pynag.Control import Command
        from pynag import Model
        self.pynag_cmd = Command
        self.pynag_model = Model
        super(HostsManagerMixin,self).__init__(*args,**kwargs)

    def build_manager_response(self,data):
        pass

    def build_managed_responses(self,data):
        pass

    def get_managed_data_filename(self):
        return self.managed_data_filename

    def clean_managed_host_data(self,hostname):
        """Method to clean old managed data after loading them"""

    def get_managed_host_data(self,hostname):
        hostname = self.normalize_hostname(hostname)
        return self.get_managed_hosts_data().setdefault(hostname,DictExt())

    def get_managed_hosts_data(self):
        return self.managed_data.setdefault('hosts',DictExt())

    def load_managed_data(self):
        self.managed_data=self.load_data(self.get_managed_data_filename())
        self.clean_managed_host_data()

    def normalize_hostname(self,name):
        if not name:
            return 'noname'
        return re.sub(r'[^\w-]+','_',name.strip())

    def is_managed_host(self, hostname_or_serial):
        if not hostname_or_serial:
            return False
        hostname_or_serial = self.normalize_hostname(hostname_or_serial)
        if not hostname_or_serial:
            return False
        if hostname_or_serial in self.managed_data.hosts:
            return True
        hostname = self.managed_data.serials[hostname_or_serial]
        return hostname and hostname in self.managed_data.hosts

    def save_managed_data(self):
        for hostname, response in self.managed_responses.items():
            managed_host = self.managed_data.hosts[hostname]
            managed_host.prev_hash = managed_host.new_hash
            managed_host.new_hash = response.get_hash()
            managed_host.prev_state = managed_host.new_state
            managed_host.new_state = response.get_current_level().exit_code
            managed_host.updated = int(time.time())
        self.save_data(self.get_managed_data_filename(),self.managed_data)

    def get_managed_nagios_states(self):
        return dict([(srv.host_name,int(srv.get_current_status().current_state)) for srv in self.pynag_model.Service.objects.filter(service_description=self.managed_service_description)])

    def init_managed_hosts(self,data):
        self.managed_responses = {}
        self.managed_nagios_states = self.get_managed_nagios_states()
        self.managed_lock = Lockfile(self.get_managed_data_filename())
        self.managed_lock.acquire()
        self.load_managed_data()

    def get_managed_response(self,hostname):
        hostname = self.normalize_hostname(hostname)
        if hostname in self.managed_responses:
            return self.managed_responses[hostname]
        response_class = getattr(self,'managed_reponse_class',self.response_class)
        response = response_class(default_level=self.managed_default_level)
        self.managed_responses[hostname] = response
        return response

    def build_response(self,data):
        self.init_managed_hosts(data)
        self.build_manager_response(data)
        self.build_managed_responses(data)

    def get_plugin_managed_informations(self,response):
        """Get plugin informations for managed hosts"""
        managers = getattr(response,'managers',[self.host.name])
        out = '\n' + response.section_format('Plugin Informations') + '\n'
        out += 'This host is managed by : %s\n' % ','.join(managers)
        out += 'Manager plugin name : %s.%s\n' % (self.__class__.__module__,self.__class__.__name__)
        out += 'Execution date : %s\n' % datetime.datetime.now()
        level = response.get_current_level()
        out += 'Response level : %s (%s), __sublevel__=%s' % (level.exit_code,level.name,response.sublevel)
        return out

    def send_managed_responses(self):
        for hostname, response in self.managed_responses.items():
            managed_host = self.managed_data.hosts[hostname]
            self.debug('[%s] before : hash=%s,state=%s now : hash=%s,state=%s',hostname,managed_host.prev_hash,self.managed_nagios_states.get(hostname,0),managed_host.new_hash,managed_host.new_state)
            if managed_host.new_hash != managed_host.prev_hash or self.managed_nagios_states.get(hostname,0) != managed_host.new_state:
                self.debug('[%s] ---> sending alert',hostname)
                response.add_end(self.get_plugin_managed_informations(response))
                response.send(nagios_host=hostname,nagios_svc=self.managed_service_description,nagios_cmd=self.pynag_cmd)

    def save_host_data(self):
        self.save_managed_data()
        super(HostsManagerMixin,self).save_host_data()

    def send_response(self):
        self.send_managed_responses()
        super(HostsManagerMixin,self).send_response()