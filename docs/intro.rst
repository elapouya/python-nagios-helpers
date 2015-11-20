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

Here is an exemple of a python plugin, create a file linux_fsfull.py:: 

   from naghelp import *

   class LinuxFsFull(ActivePlugin):
       cmd_params = 'user,passwd'
       tcp_ports = '22'
   
       def collect_data(self,data):
           data.df = Ssh(self.host.ip,self.host.user,self.host.passwd).run('df -h')
   
       def parse_data(self,data):
           data.fsfull = data.df.grep('100%').cut(col=1)
   
       def build_response(self,data):
           self.response.add_if(data.fsfull,CRITICAL,'%s : 100% Full !' % ', '.join(data.fsfull))
     
    LinuxFsFull().run()
    
To excute manually::

   python linux_fsfull.py --ip=127.0.0.1 --user=root --passwd=toor
   
It will return::

   to be completed    

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

