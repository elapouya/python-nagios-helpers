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

Naghelp Vs Nagios plugin
------------------------

There is a little difference between a naghelp plugin and a Nagios plugin :

A naghelp plugin is a python class, a Nagios plugin is a scripts.
To build a Nagios plugin from a naghelp plugin, you just have to instantiate a naghelp plugin class
and call the ``run()`` method::

You can have the naghelp class plugin definition inside the Nagios plugin script itself.
It should look like this::

   #!/usr/bin/python

   from naghelp import *

   class MyPlugin(ActivePlugin):
      """ My code """

   if __name__ == '__main__':
      plugin = MyPlugin()
      plugin.run()

Plugin Structure
----------------

dd

Basic Plugin
------------

aaa

step 1
......

bbb

step 2
......

ccc


Advanced plugin
---------------

ddd

step 1
......

eee

step 2
......

fff

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
``MyProjectActivePlugin``. The search is case insensitive on the class name. If you start ``pypa``
without any parameters, it will show you all plugin classes it has discovered with their first line
description::

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

All your plugins must inherit from a common plugin class where you specify the plugins base directory,
and type name here is the ``plugin_commons.py``::

   from naghelp import *
   from textops import *

   class MyProjectActivePlugin(ActivePlugin):
       plugins_basedir = '/home/me/myplugin_dir'
       plugin_type = 'myproject_plugin'  # you choose whatever you want but not 'plugin'

Then, a typical code for your plugins would be like this, here ``/path/to/my_project_plugins/myplugin.py``::

   from plugin_commons import *

   class MyPlugin(MyProjectActivePlugin):
      """ My code """

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

