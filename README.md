GqDB
====

GqDB is a Python Debugger for Gedit 3.

Although is still in alpha state, its goal is to provide all the features of modern debuggers within Gedit. 


![screenshot](https://i.imgur.com/pGa00ut.png "GqDB")


Features
--------

* Breakpoints can be set by double clicking in the left margin of the editor.

* Context information for the current execution line is shown in the panel.

* Toolbar buttons for step actions (Step into, Step Over, Step Out, Continue, Stop)

* Supports Python 2.7 and Python 3 debugging.



Installing
----------

Download the project, copy the file geditpydebugger.plugin and folder geditpydebugger to ~/.local/share/gedit/plugins .
Open Gedit and activate the plugin.


Getting Started
---------------

To start debugging, just click on the Debug button in the toolbar, and choose the Python interpreter version to use.


License and Dependencies
------------------------

GqDB is distributed under the MIT license. It relies on the following:

* Gedit 3.10 or newer.
* Mariano Reingart's [QDB](https://github.com/reingart/qdb "QDB") Queues(Pipe)-based independent remote client-server Python Debugger

Development Version
-------------------

You may obtain the development version using the Git:

    git clone https://github.com/pguridi/gqdb.git
