#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Création : 11 Jan 2016
#
# @author: Eric Lapouyade

import sys

def usage(plugin_base_class,error=''):
    """Prints launcher usage and display all available plugin classes"""
    print 'Usage : %s <plugin name or path.to.module.PluginClass> [options]\n' % sys.argv[0]
    if error:
        print '%s\n' % error
    print 'Available plugins :'
    print '=' * 110
    print '%-30s %-30s %s' % ('Name','File','Description')
    print '-' * 110
    for name,plugin in sorted(plugin_base_class.find_plugins().items(),key=lambda x: x[1]['name']):
        print '%-30s %-30s %s' % (plugin['name'],plugin['path'],plugin['desc'].strip())
    print '-' * 110

    import_errors = plugin_base_class.find_plugins_import_errors()
    if import_errors:
        import traceback
        print
        print '*** Some errors have been found when importing modules ***'
        print
        for filename, e in import_errors:
            print '%s :' % filename
            print '-' * 80
            try:
                raise e
            except:
                print traceback.format_exc()
            print
            print

    exit(1)

def launch(plugin_base_class):
    """Load the class specified in command line then instantiate and run it.

    It will read command line first argument and instantiate the specified class with
    a dotted notation. It will also accept only the class name without any dot, in this case,
    a recursive search will be done from the directory given by ``plugin_base_class.plugins_basedir``
    and will find the class with the right name and having the same ``plugin_type`` attribute value as
    ``plugin_base_class``. the search is case insensitive on the class name.
    Once the plugin instance has been create, the ``run()`` method is executed.
    If you start your launcher without any parameters, it will show you all plugin classes
    it has discovered in ``plugin_base_class.plugins_basedir`` with their first line description.

    Args:

        plugin_base_class(:class:`naghelp.ActivePlugin`): the base class from which all your active
            plugins are inherited. This class must redefine attributes
            :attr:`~naghelp.plugin.Plugin.plugins_basedir` and
            :attr:`~naghelp.plugin.Plugin.plugin_type`.

    This function has to be used in a launcher script you may want to write to start a class
    as a Nagios plugin, here is a an example::

        #!/usr/bin/python
        # change python interpreter if your are using virtualenv or buildout

        from plugin_commons import MyProjectActivePlugin
        from naghelp.launcher import launch

        def main():
            launch(MyProjectActivePlugin)

        if __name__ == '__main__':
            main()

    Then you can run your plugin class like that (faster)::

        /path/to/your/launcher my_project_plugins.myplugin.MyPlugin --name=myhost --user=nagiosuser --passwd=nagiospwd

    or (slower)::

        /path/to/your/launcher myplugin --name=myhost --user=nagiosuser --passwd=nagiospwd

    """
    args=sys.argv
    if len(args) < 2:
        usage(plugin_base_class,'*** You must specify a valid plugin name')
    if args[1].startswith('-'):
        usage(plugin_base_class)
    plugin_name = args[1]
    plugin = plugin_base_class.get_instance(plugin_name)
    if not plugin:
        usage(plugin_base_class,'*** "%s" is not a valid plugin' % plugin_name)
    plugin.usage = 'usage: \n%prog <plugin name or path.to.module.PluginClass> [options]'
    plugin.run()