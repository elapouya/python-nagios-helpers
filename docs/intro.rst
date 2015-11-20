..
   Created : 2015-11-04

   @author: Eric Lapouyade


===============
Getting started
===============


Install
-------

To install::

    pip install python-nagios-helpers

Quickstart
----------

Note: In this document, *naghelp* will refer to *python-nagios-helpers* 

Here is an exemple of a python plugin:: 

   class MyPlugin(ActivePlugin):
       cmd_params = 'user,passwd,community'
       tcp_ports = '22'
       udp_ports = '161'
   
       def collect_data(self,data):
           data.srv = Ssh(self.host.ip,self.host.user,self.host.passwd).mrun({
               'server' : 'show server status all',
           data.snmp = Snmp(self.host.ip,self.host.community).mget({
               'fan_present'   : '1.3.6.1.4.1.232.22.2.3.1.3.1.8.1-10',
               'fan_status'    : '1.3.6.1.4.1.232.22.2.3.1.3.1.11.1-10',})
   
       def parse_data(self,data):
           data.server_status = data.srv.server.state_pattern((
               ('',      'blade', r'^Blade #(?P<blade_id>\d+) Status:','blade_{blade_id}',None),
               ('blade', 'diag',  r'^\s+Diagnostic Status:',None,None),
               ('blade', None,    r'^\s+(?P<key>[^:]+):\s*(?P<val>.*)','blade_{blade_id}.main.{key}','{val}'),
               ('diag',  None,    r'^\s+(?P<key>[\S\s]+)\s{2,}(?P<val>[\S\s]+)','blade_{blade_id}.diag[]',None) ))
   
       def build_response(self,data):
           for fan_id,(fan_present,fan_status) in enumerate(zip(data.snmp.fan_present,data.snmp.fan_status),1):
               self.response.add_if(fan_present == 3 and fan_status == 3, WARNING, 'FAN #%s WARNING' % fan_id)
               self.response.add_if(fan_present == 3 and fan_status == 4, CRITICAL, 'FAN #%s CRITICAL' % fan_id)
           for blade in data.server_status.values():
               if not blade.main.grepc('No Server Blade Installed|Bay Subsumed'):
                   diag_errors = blade.diag.grepv('OK').grepv('exit|Other|Connection closed|Partner Device|Bay:|Name:').formatdicts('    {key} -> {val}\n')
                   self.response.add_if(blade.main.health != 'OK' or ( blade.main.other and blade.main.other != 'OK') or diag_errors, CRITICAL, 'Server slot #%s CRITICAL : \n%s' % (blade.blade_id,diag_errors))


For more information, Read The Fabulous Manual !

Run tests
---------

Many doctests as been developped, you can run them this way::

   cd tests
   python ./runtests.py

Build documentation
-------------------

An already compiled documentation should be available `here<http://python-textops.readthedocs.org>`.
Nevertheless, one can build the documentation.

For HTML:: 

   cd docs
   make html
   cd _build/html
   firefox ./index.html
   
For PDF, you may have to install some linux packages::

   sudo apt-get install texlive-latex-recommended texlive-latex-extra
   sudo apt-get install texlive-latex-base preview-latex-style lacheck tipa

   cd docs
   make latexpdf
   cd _build/latex
   evince python-textops.pdf   (evince is a PDF reader)

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

