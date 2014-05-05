GqDB
====

GqDB is a Python Debugger for Gedit 3.

Although is still in alpha state, its goal is to provide all the features of modern debuggers within Gedit. 


![screenshot](https://i.imgur.com/WlDrZ7c.png "Logo Title Text 1")


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

To start debugging, simply click on the Debug button on the toolbar, or the option from the menu.
Then select which Python interpreter to use for debugger.


License and Dependencies
------------------------

GqDB is distributed under the MIT license. It relies on the following:

* Gedit 3.10 (Gedit 3.12 support will be added soon).
* Mariano Reingart's [QDB](https://github.com/reingart/qdb "QDB") Queues(Pipe)-based independent remote client-server Python Debugger

Development Version
-------------------

You may obtain the development version using the Git:

    git clone https://github.com/pguridi/gqdb.git
