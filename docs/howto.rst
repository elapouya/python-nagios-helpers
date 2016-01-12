..
   Created : 2016-1-7

   @author: Eric Lapouyade



=============================
How to build an active plugin
=============================

An Nagios active plugin is a script that is triggered by Nagios which is waiting 2 things :

   * A message on the standard output.
   * An exit code giving the error level.

A passive plugin is a script that is NOT triggered by Nagios, but by external mechanism like event
handlers (syslog handlers), crontabs, mails, snmp traps etc... These plugins send message and error
level through a dedicated Nagios pipe.

Naghelp actually manages only **active** plugins. We plan to extend the framework to passive plugins
later.

Naghelp Vs Nagios
-----------------

There is a little difference between a naghelp plugin and a Nagios plugin :

A naghelp plugin is a python class, a Nagios plugin is a script.
To build a Nagios plugin from a naghelp plugin, you just have to instantiate a naghelp plugin class
and call the ``run()`` method::

   #!/usr/bin/python

   from naghelp import *

   class MyPlugin(ActivePlugin):
      """ My code """

   if __name__ == '__main__':
      plugin = MyPlugin()
      plugin.run()

Plugin execution pattern
------------------------

A Nagios plugin built with naghelp roughly work like this :

.. graphviz::

   digraph execpattern {
      node [shape=box,fontsize=10, height=0]
      a -> b -> c -> d -> e -> f -> g
      a  [shape="invhouse",label="Instantiate plugin class and call run()"]
      b  [label="Manage plugin parameters"]
      c  [label="Collect raw data from remote equipment"]
      d  [label="Parse raw data to structure them"]
      e  [label="Build a response by adding errors and perf data"]
      f  [label="Send response to stdout with Nagios syntax"]
      g  [shape="doubleoctagon",label="Exit plugin with appropriate exit code"]
      }

Plugin development
------------------

The main steps for coding a plugin with naghelp are :

   * Develop a class derived from :class:`naghelp.ActivePlugin` or derived from a project
     common class itself derived from :class:`naghelp.ActivePlugin`.

     The main attributes/method to override are :

         * Attribute :attr:`cmd_params` that lists what parameters are awaited on command line.
         * Attribute :attr:`required_params` tells what parameters are required
         * Attributes :attr:`tcp_ports` and :attr:`udp_ports` tell what ports to check if needed
         * Method :meth:`collect_data` to collect raw data
         * Method :meth:`parse_data` to parse raw data into structured data
         * Method :meth:`build_response` to use collected and parsed data for updating response object

   * Instantiate the plugin class
   * run it with a :meth:`run()`

The :meth:`run()` method takes care of using attributes and calling method specified above. it also
takes care of rendering the response object into Nagios string syntax, to display it onto stdout and
exiting the plugin with appropriate exit code.

That's all.


A Plugin explained
------------------

In order to understand how to code a plugin, let's take the plugin from the :doc:`intro` and explain it
line by line.

The plugin class is included into a python scripts (let's say ``linux_fs_full_plugin.py``) that will be executed
by Nagios directly::

   #!/usr/bin/python
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

Now let's explain...

Python interpreter
..................

.. code::

   #!/usr/bin/python

The first line tell what python interpreter have to run the script. Above we supposed that naghelp
has been install system-wide.
But may be, you are using ``virtualenv``, in such a case, you should use
the correct interpreter, when activated run ``which python`` to see where it is,
modify the first line then::

   #!/home/myproject/myvenv/bin/python

If you are using buildout, replace this by a customized python interpreter, to do so,
have a ``/home/myproject/buildout.cfg`` about like that::

   [buildout]
   ...
   parts = eggs tests wsgi
   ...
   eggs =
       naghelp
       <other python packages>
       ...

   [eggs]
   recipe = zc.recipe.egg
   eggs =
       ${buildout:eggs}
   extra-paths =
       ${buildout:directory}
       ${buildout:directory}/my_project_plugins
       ...
   interpreter = py2
       ...

With buildout, the plugin's first line will become::

   #!/home/myproject/bin/py2

Import modules
..............

.. code::

   from naghelp import *
   from textops import *

As you can see, not only we import naghelp but also `python-textops <http://python-textops.readthedocs.org>`_ :
it has been developed especially for naghelp so it is highly recommended to use it.
You will be able to manipulate strings and parse texts very easily.

Instead of importing these two modules, one can choose to build a ``plugin_commons.py`` to import
all modules needed for all your plugins, initialize some constants and define a common project
plugin class, see an example in :ref:`plugin_commons <plugin_commons>`.

Subclass the ActivePlugin class
...............................

.. code::

   class LinuxFsFull(ActivePlugin):

To create your active plugin class, just subclass :class:`naghelp.ActivePlugin`.

Nevertheless, if you have many plugin classes, it is highly recommended to subclass a class
common to all your plugins : see :ref:`plugin_commons <plugin_commons>`.

Specify parameters
..................

.. code::

   cmd_params = 'user,passwd'

Here, by setting :attr:`~naghelp.ActivePlugin.cmd_params`, you are asking naghelp to
accept on command line ``--user`` and ``--passwd`` options. The given values will availabe in
:meth:`~naghelp.ActivePlugin.collect_data`, :meth:`~naghelp.ActivePlugin.parse_data` and
:meth:`~naghelp.ActivePlugin.build_response` at ``self.host.user`` and
``self.host.passwd``. By default, ``ip`` and ``name`` options are also available in the same way,
you do not need to specify them.

Note that naghelp automatically sets many other options in command line, use ``-h`` to see the help::

   ./linux_fs_full_plugin.py -h
   Usage:
   linux_fs_full_plugin.py [options]

   Options:
     -h, --help           show this help message and exit
     -v                   Verbose : display informational messages
     -d                   Debug : display debug messages
     -l FILE              Redirect logs into a file
     -i                   Display plugin description
     -n                   Must be used when the plugin is started by nagios
     -s                   Save collected data in a file
                          (/tmp/naghelp/<hostname>_collected_data.json)
     -r                   Use saved collected data (option -s)
     -a                   Collect data only and print them
     -b                   Collect and parse data only and print them

     Host attributes:
       To be used to force host attributes values

       --passwd=PASSWD    Password
       --ip=IP            Host IP address
       --user=USER        User
       --name=NAME        Hostname
       --subtype=SUBTYPE  Plugin subtype (usually host model)

     Specific to my project:
       -c FILE            override default path to the db.json file

Specify tcp/udp ports
.....................

.. code::

   tcp_ports = '22'

You can specify :attr:`~naghelp.ActivePlugin.tcp_ports` and/or :attr:`~naghelp.ActivePlugin.udp_ports`
your plugin is using : by this way, the administrator will be warned what port has to be opened on his
firewall. Port informations will be displayed at the end of each message in plugin informations section.

For tcp_ports, an additional check will be done if an error occurs will collecting data.

Redefine :meth:`~naghelp.ActivePlugin.collect_data`
...................................................

.. code::

    def collect_data(self,data):
        data.df = Ssh(self.host.ip,self.host.user,self.host.passwd).run('df -h')

:meth:`~naghelp.ActivePlugin.collect_data` main purpose is to collect **raw data** from the remote
equipment. Here are some precisions :

   * You have to collect **all** data in :meth:`~naghelp.ActivePlugin.collect_data`, this means
     it is not recommended to collect some other data in :meth:`~naghelp.ActivePlugin.parse_data`
     or :meth:`~naghelp.ActivePlugin.build_response`.

   * You have to collect **only raw** data in :meth:`~naghelp.ActivePlugin.collect_data`, this means
     if raw data cannot be used at once and needs some kind of extraction, you have to do that after
     into :meth:`~naghelp.ActivePlugin.parse_data` or if there is very little processing to do,
     into :meth:`~naghelp.ActivePlugin.build_response`.

   * The data collect must be optimized to make as few requests as possible to remote equipment.
     To do so, use ``mget()``, ``mrun()``, or ``mwalk()`` methods or ``with:`` blocks (see
     module :mod:`naghelp.collect`).

   * The collected data must be set onto ``data`` object. It is a :class:`~textops.DictExt`
     dictionary that accepts dotted notation to write information (only one level at a time).

   * The collected data can be saved with ``-s`` comand-line option and restored with ``-r``.

For the example above, it is asked to run the unix command ``df -h`` through :meth:`naghelp.Ssh.run`
on the remote equipment at ``host = self.host.ip`` with ``user = self.host.user`` and
``password = self.host.passwd``.

You can run your plugin with option ``-a`` to stop it just after data collect and display all
harvested informations (ie ``data`` :class:`~textops.DictExt`)::

   # ./linux_fs_full_plugin.py --ip=127.0.0.1 --user=naghelp --passwd=naghelppw -a
   Collected Data =
   {   'df': 'Filesystem      Size  Used Avail Use% Mounted on
   /dev/sdb6           20G     19G  1,0G  95% /
   udev               7,9G    4,0K  7,9G   1% /dev
   tmpfs              1,6G    1,1M  1,6G   1% /run
   none               5,0M       0  5,0M   0% /run/lock
   none               7,9G     77M  7,8G   1% /run/shm
   /dev/sda5           92G     91G  0,9G  99% /home
   '}

Redefine :meth:`~naghelp.ActivePlugin.parse_data`
.................................................

.. code::

    def parse_data(self,data):
        df = data.df.skip(1)
        data.fs_critical = df.greaterequal(98,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()
        data.fs_warning = df.inrange(95,98,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()
        data.fs_ok = df.lessthan(95,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()

:meth:`~naghelp.ActivePlugin.parse_data` main purpose is to structure or extract information from
collected raw data. To do so, it is highly recommended to use
`python-textops <http://python-textops.readthedocs.org>`_.
The ``data`` object is the same as the one from :meth:`~naghelp.ActivePlugin.collect_data`
that is a :class:`~textops.DictExt`, so you can access collected raw data with a dotted notation.
`textops <http://python-textops.readthedocs.org>`_ methods are also directly available from anywhere
in the ``data`` object.

``data.df`` should be equal to::

   Filesystem      Size  Used Avail Use% Mounted on
   /dev/sdb6           20G     19G  1,0G  95% /
   udev               7,9G    4,0K  7,9G   1% /dev
   tmpfs              1,6G    1,1M  1,6G   1% /run
   none               5,0M       0  5,0M   0% /run/lock
   none               7,9G     77M  7,8G   1% /run/shm
   /dev/sda5           92G     91G  0,9G  99% /home

In ``df = data.df.skip(1)`` :class:`~textops.skip` will skip the first line of the collect raw data
and store in ``df`` local variable, this should be equal to::

   /dev/sdb6           20G     19G  1,0G  95% /
   udev               7,9G    4,0K  7,9G   1% /dev
   tmpfs              1,6G    1,1M  1,6G   1% /run
   none               5,0M       0  5,0M   0% /run/lock
   none               7,9G     77M  7,8G   1% /run/shm
   /dev/sda5           92G     91G  0,9G  99% /home

In ``df.greaterequal(98,key=cuts(r'(\d+)%'))``, :class:`~textops.greaterequal` will select all lines
where the column with a percent has a value greater or equal to 98, in our case, there is only one::

   ['/dev/sda5           92G     81G  6,9G  93% /home']

In ``df.greaterequal(98,key=cuts(r'(\d+)%')).cut(col='5,4')`` :class:`~textops.cut` will select
only column 5 and 4 in that order::

   [['/home', '99%']]

In ``df.greaterequal(98,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()``
:class:`~textops.renderitems` will format/render above this way::

   ['/home : 99%']

This will be stored in ``data.fs_critical``. This is about the same for ``data.fs_warning`` and
``data.fs_ok``.

Finally, if you want to see what has been parsed, use ``-b`` command line option::

   # ./linux_fs_full_plugin.py --ip=127.0.0.1 --user=naghelp --passwd=naghelppw -b
   ...
   Parsed Data =
   {   'fs_critical': [u'/home : 99%'],
       'fs_ok': [u'/dev : 1%', u'/run : 1%', u'/run/lock : 0%', u'/run/shm : 2%'],
       'fs_warning': [u'/ : 95%']}

Redefine :meth:`~naghelp.ActivePlugin.build_response`
.....................................................

.. code::

    def build_response(self,data):
        self.response.add_list(CRITICAL,data.fs_critical)
        self.response.add_list(WARNING,data.fs_warning)
        self.response.add_list(OK,data.fs_ok)

In :meth:`~naghelp.ActivePlugin.build_response`, ``data`` will contain all collected data AND
all parsed data in the same :class:`~textops.DictExt`.
Now you just have to use :class:`~naghelp.PluginResponse` methods to modify ``self.response``.

In the script, we are adding lists of messages with :meth:`~naghelp.PluginResponse.add_if` :
``self.response.add_list(OK,data.fs_ok)`` is the same as writing::

   for msg in data.fs_ok:
      if msg:
         self.response.add(OK, msg)

Which is equivalent to::

   self.response.add(OK,'/dev : 1%')
   self.response.add(OK,'/run : 1%')
   self.response.add(OK,'/run/lock : 0%')
   self.response.add(OK,'/run/shm : 2%')

To see what naghelp will finally send to Nagios, just execute the script ::

   STATUS : CRITICAL:1, WARNING:1, OK:4
   ==================================[  STATUS  ]==================================

   ----( CRITICAL )----------------------------------------------------------------
   /home : 99%

   ----( WARNING )-----------------------------------------------------------------
   / : 95%

   ----( OK )----------------------------------------------------------------------
   /dev : 1%
   /run : 1%
   /run/lock : 0%
   /run/shm : 2%


   ============================[ Plugin Informations ]=============================
   Plugin name : __main__.LinuxFsFull
   Description : Basic plugin to monitor full filesystems on Linux systems
   Ports used : tcp = 22, udp = none
   Execution time : 0:00:00.003662
   Exit code : 2 (CRITICAL), __sublevel__=0

As you can see :

   * naghelp generated automatically a synopsis : ``STATUS : CRITICAL:1, WARNING:1, OK:4``
   * naghelp created the ``==[ STATUS ]==`` section where messages has be splitted into
     several sub-sections corresponding to their level.
   * naghelp automatically add a ``==[ Plugin Informations ]==`` section with many useful
     information including ports to be opened on the firewall.
   * naghelp automatically used the appropriate exit code, here 2 (CRITICAL)

Advanced plugin
---------------

Manage errors
.............

You can abort the plugin execution when an error is encountered at monitoring level,
or when it is not relevant to monitor an equipment in some conditions.

For exemple, your have collected data about an equipment controller, but it is not the active one,
that means data may be incomplete or not relevant : you should use the
:meth:`~naghelp.ActivePlugin.fast_response` or :meth:`~naghelp.ActivePlugin.fast_response_if` method::

    def build_response(self,data):
        self.fast_response_if(data.hpoa.oa.grep('^OA Role').grepc('Standby'), OK, 'Onboard Administration in Standby mode')
        ...

Above, if the monitored controller is in standby mode, we get out the plugin at once without
any error (``OK`` response level).

Create mixins
.............

To re-use some code, you can create a plugin mixin.

Let's create a mixin that manages gauges : When a metric (for example the number of fans) is seen
the first time, the metric is memorized as the reference value (``etalon``).
Next times, it is compared : if the metric goes below, it means that one part has been lost
and an error should be raise.

Here is the mixin::

   class GaugeMixin(object):
       def get_gauges(self,data):
           # To be defined in child class
           # must return a tuple of tuples like this:
           # return ( ('gaugeslug','the gauge full name', <calculated gauge value as int>, <responselevel>),
           #          ('gaugeslug2','the gauge2 full name', <calculated gauge2 value as int>, <responselevel2>) )
           pass

       def gauge_response(self,data):
           for gname,fullname,gvalue,level in self.get_gauges(data):
               self.response.add_more('%s : %s',fullname,gvalue)
               etalon_name = gname + '_etalon'
               etalon_value = self.host.get(etalon_name,None)
               if etalon_value is not None and gvalue < etalon_value:
                   self.response.add(level,'%s : actual count (%s) not equal to the reference value (%s)' % (fullname, gvalue, etalon_value))
               if gvalue:
                   # save the gauge value as the new reference value in host's persistent data
                   self.host.set(etalon_name,gvalue)
               else:
                   self.response.add(UNKNOWN,'%s : unknown count.' % gname.upper())

       def build_response(self,data):
           self.gauge_response(data)
           # this will call plugin build_response() or another mixin build_response() if present.
           super(GaugeMixin,self).build_response(data)

Then use the mixin in your plugin by using multiple inheritage mechanism (mixin first)::

   class SunRsc(GaugeMixin,ActivePlugin):
      ...
       def get_gauges(self, data):
           return ( ('fan',      'Fans',       data.showenv.grep(r'^FAN TRAY|_FAN').grepc('OK'), WARNING ),
                    ('localdisk','Local disks',data.showenv.grep(r'\bDISK\b').grepc('OK|PRESENT'), WARNING ),
                    ('power',    'Powers',     data.showenv.after(r'Power Supplies:').grepv(r'^---|Supply|^\s*$').grepc('OK'), WARNING ) )

By this way, you can re-use very easily gauge feature in many plugins.
Of course, you can use several plugin mixins at a time, just remember to put the
:meth:``~naghelp.ActivePlugin`` class (or some derived one) at the end of the parent class list.

Create a launcher
-----------------

If you have a lot of plugins, you should consider to code only naghelp classes.
By this way, you will be able to define more than one plugin per python file and you will discover
the joy of subclassing your own plugin classes to build some others much more faster.
You will be also able to use python mixins to compact your code.

To do so, you will need a launcher that will load the right python module, instantiate the
right naghelp plugin class and run it. Lets call the launcer script ``pypa``,
the Nagios commands.cfg will be something like this::

   define command{
       command_name    myplugin
       command_line    /path/to/pypa my_project_plugins.myplugin.MyPlugin --name="$ARG1$" --user="$ARG2$" --passwd="$ARG3"
       }

You just have to write a launcher once, naghelp provide a module for that, here is the ``pypa`` script::

   #!/usr/bin/python
   # change python interpreter if your are using virtualenv or buildout

   from plugin_commons import MyProjectActivePlugin
   from naghelp.launcher import launch

   def main():
       launch(MyProjectActivePlugin)

   if __name__ == '__main__':
       main()

The ``launch`` function will read command line first argument and instantiate the specified class with
a dotted notation. It will also accept only the class name without any dot, in this case,
a recursive search will be done from the directory given by ``MyProjectActivePlugin.plugins_basedir``
and will find the class with the right name and having the same ``plugin_type`` attribute value as
``MyProjectActivePlugin``. the search is case insensitive on the class name.
``MyProjectActivePlugin`` is the common class to all your plugins and is derived
from :class:`naghelp.ActivePlugin`.

If you start ``pypa`` without any parameters, it will show you all plugin classes
it has discovered with their first line description::

   $ ./pypa
   Usage : bin/pypa <plugin name or path.to.module.PluginClass> [options]

   Available plugins :
   ==============================================================================================================
   Name                           File                           Description
   --------------------------------------------------------------------------------------------------------------
   AixErrpt                       ibm_aix.py                     IBM plugin using errpt command on all AIX systems
   BrocadeSwitch                  brocade.py                     Brocade Switch Active plugin
   HpBladeC7000                   hp_blade_c7000.py              HP bladecenter C7000 plugin
   HpEva                          hp_eva.py                      HP Enterprise Virtual Array (EVA) SAN Storage Plugin
   HpHpuxSyslog                   hp_hpux.py                     HPUX syslog analyzing active plugin
   HpProliant                     hp_proliant.py                 HP Proliant Active plugin
   SunAlom                        sun_ctrl.py                    Sun microsystems/Oracle plugin for hardware with ALOM controller
   SunFormatFma                   sun_fma.py                     Sun microsystems/Oracle plugin using format and fmadm commands on solaris system
   SunIlom                        sun_ctrl.py                    Sun microsystems/Oracle plugin for hardware with ILOM controller
   SunRsc                         sun_ctrl.py                    Sun microsystems/Oracle plugin for hardware with RSC controller
   VIOErrlog                      ibm_aix.py                     IBM plugin using errlog command on all VIO systems
   VmwareEsxi                     vmware_esxi.py                 VMWare ESXi active plugin
   --------------------------------------------------------------------------------------------------------------

plugin_commons
--------------

.. _plugin_commons:

All your plugins should (*must* when using a launcher) derive from a common plugin class
which itself is derived from :class:`naghelp.ActivePlugin`. You will specify the plugins base directory,
and type name. All this should be placed in a file ``plugin_commons.py``::

   from naghelp import *
   from textops import *

   class MyProjectActivePlugin(ActivePlugin):
       plugins_basedir = '/path/to/my_project_plugins'
       plugin_type = 'myproject_plugin'  # you choose whatever you want but not 'plugin'

Then, a typical code for your plugins would be like this, here ``/path/to/my_project_plugins/myplugin.py``::

   from plugin_commons import *

   class MyPlugin(MyProjectActivePlugin):
      """ My code """

Debug
-----

To debug a plugin, the best way is to activate the debug mode with ``-d`` flag::

   $ python ./linux_fs_full_plugin.py --ip=127.0.0.1 --user=naghelp --passwd=naghelppw -d
   2016-01-12 10:12:29,912 - naghelp - DEBUG - Loading data from /home/elapouya/projects/sebox/src/naghelp/tests/hosts/127.0.0.1/plugin_persistent_data.json :
   2016-01-12 10:12:29,913 - naghelp - DEBUG - {   u'ip': u'127.0.0.1',
       u'name': u'127.0.0.1',
       u'passwd': u'naghelppw2',
       u'user': u'naghelp'}
   2016-01-12 10:12:29,913 - naghelp - INFO - Start plugin __main__.LinuxFsFull for 127.0.0.1
   2016-01-12 10:12:29,913 - naghelp - DEBUG - Host informations :
   2016-01-12 10:12:29,914 - naghelp - DEBUG - _params_from_db = {   u'ip': u'127.0.0.1',
       u'name': u'127.0.0.1',
       u'passwd': u'naghelppw2',
       u'user': u'naghelp'}
   2016-01-12 10:12:29,914 - naghelp - DEBUG - _params_from_env = {   }
   2016-01-12 10:12:29,914 - naghelp - DEBUG - _params_from_cmd_options = {   'ip': '127.0.0.1',
       'name': None,
       'passwd': 'naghelppw',
       'subtype': None,
       'user': 'naghelp'}
   2016-01-12 10:12:29,914 - naghelp - DEBUG -
   ------------------------------------------------------------
   ip           : 127.0.0.1
   name         : 127.0.0.1
   passwd       : naghelppw
   user         : naghelp
   ------------------------------------------------------------
   2016-01-12 10:12:30,101 - naghelp - DEBUG - #### Ssh( naghelp@127.0.0.1 ) ###############
   2016-01-12 10:12:30,255 - naghelp - DEBUG - is_connected = True
   2016-01-12 10:12:30,255 - naghelp - DEBUG -   ==> df -h
   2016-01-12 10:12:30,775 - naghelp - DEBUG - #### Ssh : Connection closed ###############
   2016-01-12 10:12:30,775 - naghelp - INFO - Data are collected
   2016-01-12 10:12:30,776 - naghelp - DEBUG - Collected Data =
   {   'df': 'Sys. de fichiers Taille Utilis\xc3\xa9 Dispo Uti% Mont\xc3\xa9 sur
   /dev/sdb6           20G     12G  6,5G  65% /
   udev               7,9G    4,0K  7,9G   1% /dev
   tmpfs              1,6G    1,1M  1,6G   1% /run
   none               5,0M       0  5,0M   0% /run/lock
   none               7,9G    119M  7,8G   2% /run/shm
   /dev/sda5           92G     81G  6,9G  93% /home
   '}
   2016-01-12 10:12:30,777 - naghelp - INFO - Data are parsed
   2016-01-12 10:12:30,777 - naghelp - DEBUG - Parsed Data =
   {   'fs_critical': [],
       'fs_ok': [   '/ : 65%',
                    '/dev : 1%',
                    '/run : 1%',
                    '/run/lock : 0%',
                    '/run/shm : 2%',
                    '/home : 93%'],
       'fs_warning': []}
   2016-01-12 10:12:30,778 - naghelp - DEBUG - Saving data to /home/elapouya/projects/sebox/src/naghelp/tests/hosts/127.0.0.1/plugin_persistent_data.json :
   ip           : 127.0.0.1
   name         : 127.0.0.1
   passwd       : naghelppw
   user         : naghelp
   2016-01-12 10:12:30,778 - naghelp - INFO - Plugin output summary : None
   2016-01-12 10:12:30,778 - naghelp - DEBUG - Plugin output :
   ################################################################################
   OK
   ==================================[  STATUS  ]==================================

   ----( OK )----------------------------------------------------------------------
   / : 65%
   /dev : 1%
   /run : 1%
   /run/lock : 0%
   /run/shm : 2%
   /home : 93%


   ============================[ Plugin Informations ]=============================
   Plugin name : __main__.LinuxFsFull
   Description : Basic plugin to monitor full filesystems on Linux systems
   Ports used : tcp = 22, udp = none
   Execution time : 0:00:00.866135
   Exit code : 0 (OK), __sublevel__=0

Debug params
............

Before looking your code, check the plugin is receiving the right parameters :
parameters are taken from command line options THEN envrionment variables THEN from database and
persistent data. In debug traces, what is set to ``self.host`` is written here::

   2016-01-12 10:12:29,914 - naghelp - DEBUG -
   ------------------------------------------------------------
   ip           : 127.0.0.1
   name         : 127.0.0.1
   passwd       : naghelppw
   user         : naghelp
   ------------------------------------------------------------

Debug ``collect_data``
......................

The main pitfall is to succeed to connect to the remote host and to find prompt pattern.
When using :class:`~naghelp.Ssh`, there is no problem because the prompt is automatically recognized
by the internal ssh library (paramiko), but as soon as you have to specify patterns
for the login steps or to find the prompt or even on remote equipment, this may be a problem.

naghelp provides possibilities to customize these patterns to be able to connect to many
kind of equipments. This could be done on :class:`~naghelp.Telnet`, :class:`~naghelp.Expect` or even
:class:`~naghelp.Ssh`.

The main symptom when a pattern is wrong, this usually hangs the collect, and the plugin should then
raise an TimeoutError exception.

To debug patterns, please do some testing by collecting data manually yourself and test your
patterns on output. Please check patterns syntax in :mod:`re` module.

Use ``-a`` plugin option to check what has been collected

.. note::
   The prompt pattern is mandatory to recognize when a command output has finished and when
   naghelp can send another one.

Debug ``parse_data``
....................

The main pitfall is to correctly parse or extract data from collected raw data.
Use ``-b`` plugin option to check what has been collected and what has be parsed.
and options ``-s`` and ``-r`` to avoid wasting time to collect data.
Check `textops manual <http://python-textops.readthedocs.org>`_ to see how to do this.
There is no particular tip but to have experience with regular expressions.

Debug ``build_response``
........................

The goal is to check that all equipment errors/infos are correctly detected.
There is a little trick to check everything :
The first time, use your plugin with ``-s`` option to save the collect_data
(the ``-h`` will tell you the file path at ``-s`` line).
To test all cases, you can simulate them by modifying the file for collected data.
Then, use ``-r`` to restore it and see how your plugin is working.


* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

