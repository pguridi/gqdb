import os
import re
import sys
import time
import subprocess
MODULE_DIRECTORY = os.path.dirname(__file__)

from .debugger_frontend import CallbackFrontend
from .components import ContextBox, InterpretersDialog

from distutils.version import StrictVersion as V
from gi.repository import GObject, Gtk, GLib, Gdk, GtkSource, Gedit, Gio, GdkPixbuf

def get_version_from_str(version_str):
    return re.search('\d+(\.\d+)+', str(version_str)).group(0)
    
# Get the gedit version
proc = subprocess.Popen('gedit --version', shell=True, 
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(stdout, stderr) = proc.communicate()
    
GEDIT_VERSION = get_version_from_str(stdout)
if not GEDIT_VERSION:
    print("Could not determine Gedit version")
else:
    GEDIT_VERSION = V(GEDIT_VERSION)

if GEDIT_VERSION < V("3.10"):
    print("Gedit version not compatible. Version 3.10 or higher is required but %s detected." % GEDIT_VERSION)
else:
    print("Gedit version: %s" % GEDIT_VERSION)


PYTHON_RUNTIMES = []
# Get the installed interpreters #TODO: do something less ugly
for py in ['python2', 'python3']:
    try:
        out = subprocess.check_output("%s --version" % str(py), shell=True)
        py_path = subprocess.check_output("which %s" % str(py), shell=True)
        PYTHON_RUNTIMES.append([py, py_path.decode("utf-8").strip("\n")])
    except subprocess.CalledProcessError as e:
        print("Error: ", e)

print("Detected python runtimes: %s" % str(PYTHON_RUNTIMES))

BREAKPOINT_PIXBUF = GdkPixbuf.Pixbuf.new_from_file(os.path.join(MODULE_DIRECTORY, "images", "breakpoint.png"))
CURRENT_STEP_PIXBUF = GdkPixbuf.Pixbuf.new_from_file(os.path.join(MODULE_DIRECTORY, "images", "step_current.png"))

menu_ui_str = """<ui>
<toolbar name="ToolBar">
<separator />
<placeholder name="Debug">
<toolitem name="Debug" action="gqdb" />
</placeholder>
</toolbar>
<menubar name="MenuBar">
<menu name="ToolsMenu" action="Tools">
<placeholder name="ToolsOps_2">
<menuitem name="Debug" action="gqdb" />
</placeholder>
</menu>
</menubar>
</ui>"""


def idle_add_decorator(func):
    def callback(*args):
        GLib.idle_add(func, *args)
    return callback

class GDebugger:

    def __init__(self):
        self.DEBUGGER = CallbackFrontend()

    def set_app(self, app):
        self.APP = app

    def set_window(self, window):
        self.WINDOW = window

    def get_frontend(self):
        return self.DEBUGGER

DEBUGGER = GDebugger()

class GqdbPluginAppActivatable(GObject.Object, Gedit.AppActivatable):

    app = GObject.property(type=Gedit.App)

    def __init__(self):
        GObject.Object.__init__(self)

    def do_activate(self):
        self.app.add_accelerator("F2", "win.gqdb", None)
        self.app.add_accelerator("F3", "win.step", None)
        self.app.add_accelerator("F4", "win.step_in", None)
        self.app.add_accelerator("F5", "win.continue", None)

        if GEDIT_VERSION < V("3.12"):
            print("Need to implement menus for gedit <3.10")
        else:
            self.menu_ext = self.extend_menu("tools-section")
            item = Gio.MenuItem.new(("Debug"), "win.gqdb")
            self.menu_ext.prepend_menu_item(item)

    def do_deactivate(self):
        self.app.remove_accelerator("win.gqdb", None)
        self.app.remove_accelerator("win.step_in", None)
        self.app.remove_accelerator("win.step", None)
        self.app.remove_accelerator("win.continue", None)
        self.menu_ext = None


class GqdbPluginWindowActivatable(GObject.Object, Gedit.WindowActivatable):
    #__gtype_name__ = "GQdb"
    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self._ui_id = None

    @idle_add_decorator
    def mark_current_line(self, sender, filename, lineno, context):
        lineno -= 1
        current_doc = DEBUGGER.WINDOW.get_active_document().get_location()
        if not current_doc:
            return

        found = False
        # get the document
        for doc in self.window.get_documents():
            if doc.get_location() and doc.get_location().get_path() == filename:
                found = True
                doc.goto_line(lineno)
                doc.create_source_mark(None, "2", doc.get_iter_at_line(lineno))
        if not found:
            print("Doc not opened, lets open it..")
            print(filename)
            gfile = Gio.File.new_for_path(filename)
            self.window.create_tab_from_location(gfile, None, lineno, 0, False, True)

        return

        # # Add context
        # globals_it = self._variables_treestore.append(None, [self._variable_pixbuf,
        #                                                      "Globals", "Global variables"])
        # for g in context['environment']['globals'].keys():
        #     val, vtype = context['environment']['globals'][g]
        #     it = self._variables_treestore.append(globals_it, [self._variable_pixbuf,
        #                                                        g, vtype + ': ' + val])
        #
        # # now add locals
        # for k in context['environment']['locals'].keys():
        #     val, vtype = context['environment']['locals'][k]
        #     it = self._variables_treestore.append(None, [self._variable_pixbuf,
        #                                                  k, vtype + ': ' + val])

    def clear_markers(self):
        for doc in self.window.get_documents():
            start, end = doc.get_bounds()
            doc.remove_source_marks(start, end, "2")

    def do_activate(self):
        action = Gio.SimpleAction(name="gqdb")
        action.connect('activate', lambda a, p: self.debug())
        action.connect('activate', lambda a, p: self.clear_markers())
        self.window.add_action(action)

        action = Gio.SimpleAction(name="step")
        action.connect('activate', lambda a, p: DEBUGGER.get_frontend().Next())
        action.connect('activate', lambda a, p: self.clear_markers())
        self.window.add_action(action)

        action = Gio.SimpleAction(name="step_in")
        action.connect('activate', lambda a, p: DEBUGGER.get_frontend().Step())
        action.connect('activate', lambda a, p: self.clear_markers())
        self.window.add_action(action)

        action = Gio.SimpleAction(name="continue")
        action.connect('activate', lambda a, p: DEBUGGER.get_frontend().Continue())
        action.connect('activate', lambda a, p: self.clear_markers())
        self.window.add_action(action)

        panel = self.window.get_bottom_panel()
        self._context_box = ContextBox()

        if GEDIT_VERSION < V("3.12"):
            manager = self.window.get_ui_manager()
            # Create a new action group
            self._action_group = Gtk.ActionGroup("DebuggerActions")
            self._action_group.add_actions([("gqdb", Gtk.STOCK_EXECUTE, _("Debug"),
                                            None, _("Debug"),
                                            self.debug)])

            # Insert the action group
            manager.insert_action_group(self._action_group, -1)
            self._ui_id = manager.add_ui_from_string(menu_ui_str)
            panel.add_item(self._context_box, "debuggerpanel", "Python debugger", None)
        else:
            panel.add_titled(self._context_box, "debuggerpanel", "Python debugger")
        panel.show_all()
        
        DEBUGGER.set_window(self.window)

        DEBUGGER.get_frontend().connect_signal('write', self._context_box.write_stdout)
        DEBUGGER.get_frontend().connect_signal('mark-current-line', self.mark_current_line)

    def do_deactivate(self):
        self.window.remove_action("gqdb")
        panel = self.window.get_bottom_panel()
        panel.remove(self._context_box)
        if GEDIT_VERSION < V("3.10"):
            manager = self.window.get_ui_manager()
            manager.remove_ui(self._ui_id)

    def execute(self, file_path):
        # ask for interpreter
        diag = InterpretersDialog(PYTHON_RUNTIMES)
        pythexec = diag.run()
        if not pythexec:
            return

        DEBUGGER.get_frontend().init(1)
        cdir, filen = os.path.split(file_path)
        if not cdir:
            cdir = "."
        cwd = os.getcwd()
        try:
            os.chdir(cdir)
            print("Executing: %s" % file_path)
            qdb_path = os.path.join(MODULE_DIRECTORY, 'qdb.py')
            proc = subprocess.Popen([pythexec + " -u " + qdb_path + ' ' + file_path],
             shell=True, close_fds=True)
            time.sleep(0.5)
            DEBUGGER.get_frontend().attach()
        except Exception as e:
            raise
        finally:
            os.chdir(cwd)

    def do_update_state(self):
        pass

    def debug(self, action=None):
        active_document = self.window.get_active_document()
        doc_location = active_document.get_location()
        if not doc_location:
            return
        self.execute(doc_location.get_path())


class GqdbPluginViewActivatable(GObject.Object, Gedit.ViewActivatable):
    #__gtype_name__ = "GqdbPluginViewActivatable"
    view = GObject.property(type=Gedit.View)

    def do_activate(self):
        self.view.set_show_line_marks(True)
        source_attrs = GtkSource.MarkAttributes()
        source_attrs.set_pixbuf(BREAKPOINT_PIXBUF)
        self.view.set_mark_attributes("1", source_attrs, 1)

        source_attrs = GtkSource.MarkAttributes()
        source_attrs.set_pixbuf(CURRENT_STEP_PIXBUF)
        self.view.set_mark_attributes("2", source_attrs, 2)

        self.view.connect('button-press-event', self.button_press_cb)

    def button_press_cb(self, view, ev):
        mark_category = "1"
        buf = view.get_buffer()
        # check that the click was on the left gutter
        if ev.window == view.get_window(Gtk.TextWindowType.LEFT):
            if ev.button != 1:
                return

            if ev.type != Gdk.EventType._2BUTTON_PRESS:
                return

            current_doc = DEBUGGER.WINDOW.get_active_document().get_location()
            if not current_doc:
                return
            print(current_doc.get_path())
            current_doc_path = current_doc.get_path()

            x_buf, y_buf = view.window_to_buffer_coords(Gtk.TextWindowType.LEFT,
                                                    int(ev.x), int(ev.y))
            # get line bounds
            line_start = view.get_line_at_y(y_buf)[0]

            # get the markers already in the line
            mark_list = buf.get_source_marks_at_line(line_start.get_line(), mark_category)
            # search for the marker corresponding to the button pressed
            for m in mark_list:
                if m.get_category() == mark_category:
                    # a marker was found, so delete it
                    buf.delete_mark(m)
                    if DEBUGGER.get_frontend().attached:
                        DEBUGGER.get_frontend().ClearBreakpoint(current_doc_path, line_start.get_line() + 1)
                    else:
                        DEBUGGER.get_frontend().ClearBreakpointOffline(current_doc_path, line_start.get_line() + 1)
                    break
            else:
                # no marker found, create one
                buf.create_source_mark(None, mark_category, line_start)
                #self._breakpoints_liststore.append([True, 'Line: ' + str(line_start.get_line() + 1),
                #                                    self._breakpoint_pixbuf])
                if DEBUGGER.get_frontend().attached:
                    DEBUGGER.get_frontend().SetBreakpoint(current_doc_path, line_start.get_line() + 1)
                else:
                    DEBUGGER.get_frontend().SetBreakpointOffline(current_doc_path, line_start.get_line() + 1)

        return False
