#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Création : 8 Jan 2016

@author: Eric Lapouyade
'''

import sys

def usage(plugin_base_class,error=''):
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
                traceback.print_exc()
            print
            print

    exit(1)

def launch(plugin_base_class):
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