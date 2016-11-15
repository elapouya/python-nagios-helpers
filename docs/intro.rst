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

You may have to install some linux package::

    sudo apt-get install libffi-dev

Quickstart
----------

It is higly recommended to use `python-textops <http://python-textops.readthedocs.org>`_
to manipulate collected data.

Here is an exemple of a python plugin, create a file linux_fs_full_plugin.py::

   from naghelp import *
   from textops import *

   class LinuxFsFull(ActivePlugin):
       """ Basic plugin to monitor full filesystems on Linux systems"""
       cmd_params = 'user,passwd'
       tcp_ports = '22'

       def collect_data(self,data):
           data.df = Ssh(self.host.ip,self.host.user,self.host.passwd).run('df -h')

       def parse_data(self,data):
           df = data.df.skip(1)
           data.fs_critical = df.greaterequal(98,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()
           data.fs_warning = df.inrange(95,98,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()
           data.fs_ok = df.lessthan(95,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()

       def build_response(self,data):
           self.response.add_list(CRITICAL,data.fs_critical)
           self.response.add_list(WARNING,data.fs_warning)
           self.response.add_list(OK,data.fs_ok)

   if __name__ == '__main__':
      LinuxFsFull().run()

To excute manually::

   python linux_fs_full_plugin.py --ip=127.0.0.1 --user=naghelp --passwd=lgpl

On error, it may return something liek this::

   STATUS : CRITICAL:2, WARNING:1, OK:3
   ==================================[  STATUS  ]==================================

   ----( CRITICAL )----------------------------------------------------------------
   / : 98%
   /home : 99%

   ----( WARNING )-----------------------------------------------------------------
   /run/shm : 95%

   ----( OK )----------------------------------------------------------------------
   /dev : 1%
   /run : 1%
   /run/lock : 0%


   ============================[ Plugin Informations ]=============================
   Plugin name : __main__.LinuxFsFull
   Description : Basic plugin to monitor full filesystems on Linux systems
   Ports used : tcp = 22, udp = none
   Execution time : 0:00:00.673851
   Exit code : 2 (CRITICAL), __sublevel__=0

Or if no error::

   OK

   ============================[ Plugin Informations ]=============================
   Plugin name : __main__.LinuxFsFull
   Description : Basic plugin to monitor full filesystems on Linux systems
   Ports used : tcp = 22, udp = none
   Execution time : 0:00:00.845603
   Exit code : 0 (OK), __sublevel__=0

Naghelp will automatically manage some options::

   $ python linux_fs_full_plugin.py -h
   Usage:
   linux_fsfull.py [options]

   Options:
     -h, --help         show this help message and exit
     -v                 Verbose : display informational messages
     -d                 Debug : display debug messages
     -l FILE            Redirect logs into a file
     -i                 Display plugin description
     -n                 Must be used when the plugin is started by nagios
     -s                 Save collected data in a file
                        (/tmp/naghelp/<hostname>_collected_data.json)
     -r                 Use saved collected data (option -s)
     -a                 Collect data only and print them
     -b                 Collect and parse data only and print them

     Host attributes:
       To be used to force host attributes values

       --passwd=PASSWD  Passwd
       --ip=IP          Host IP address
       --user=USER      User
       --name=NAME      Hostname


For more information, Read The Fabulous Manual !

Run tests
---------

Many doctests as been developped, you can run them this way::

   cd tests
   python ./runtests.py

Build documentation
-------------------

An already compiled documentation should be available `here<http://python-nagios-helpers.readthedocs.org>`.
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
   evince python-nagios-helpers.pdf   (evince is a PDF reader)

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

