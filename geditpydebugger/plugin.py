import os
import re
import sys


import time
import subprocess
MODULE_DIRECTORY = os.path.dirname(__file__)

sys.path.append(os.path.join(MODULE_DIRECTORY, "libs"))

QDB_LAUNCHER_PATH = os.path.join(MODULE_DIRECTORY, "libs", "qdb_launcher.py")

from .debugger_frontend import CallbackFrontend
from .components import ContextBox, InterpretersDialog
from .breakpoint import LineBreakpoint

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
CURRENT_STEP_PIXBUF = GdkPixbuf.Pixbuf.new_from_file(os.path.join(MODULE_DIRECTORY, "images", "anjuta-pcmark-16.png"))

DEBUGGER_GIO_ICON = Gio.FileIcon.new(Gio.File.new_for_path(os.path.join(MODULE_DIRECTORY, "images", "bug-icon.png")))
STEP_INTO_GIO_ICON = Gio.FileIcon.new(Gio.File.new_for_path(os.path.join(MODULE_DIRECTORY, "images", "anjuta-step-into-16.png")))
STEP_OUT_GIO_ICON = Gio.FileIcon.new(Gio.File.new_for_path(os.path.join(MODULE_DIRECTORY, "images", "anjuta-step-out-16.png")))
STEP_OVER_GIO_ICON = Gio.FileIcon.new(Gio.File.new_for_path(os.path.join(MODULE_DIRECTORY, "images", "anjuta-step-over-16.png")))

menu_ui_str = """
<ui>
  <menubar name="MenuBar">
    <menu name="Debugger" action="Debugger">
      <placeholder name="Debugger">
        <menuitem action="Debug"/>
        <menuitem action="StepInto"/>
        <menuitem action="StepOver"/>
        <menuitem action="StepOut"/>
        <menuitem action="Continue"/>
        <menuitem action="Stop"/>
      </placeholder>
    </menu>
  </menubar>

  <toolbar name="ToolBar">
    <separator />
    <placeholder name="DebugBar">
      <toolitem action="Debug"/>
      <toolitem action="StepInto"/>
      <toolitem action="StepOver"/>
      <toolitem action="StepOut"/>
      <toolitem action="Continue"/>
      <toolitem action="Stop"/>
    </placeholder>
  </toolbar>
</ui>
"""

def idle_add_decorator(func):
    def callback(*args):
        GLib.idle_add(func, *args)
    return callback

class GqdbPluginActivatable(GObject.Object, Gedit.WindowActivatable):
    __gtype_name__ = "GqdbPluginActivatable"
    window = GObject.property(type=Gedit.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self._handlers = []
        self._views = []
        self._debugging = False
        self._debugger = None
        self._breakpoints = set()

    def do_activate(self):
        panel = self.window.get_bottom_panel()
        self._context_box = ContextBox()

        if GEDIT_VERSION < V("3.12"):
            manager = self.window.get_ui_manager()
            # Create a new action group
            self._action_group = Gtk.ActionGroup("DebuggerActions")
            actions = [
              ("Debugger", None, "Debugger", None, "Debugger", None),
              ("Debug", None, "Debug","F2", "Debug", self.debug),
              ('StepInto', None, 'Step Into', 'F3', "Step Into", self.step_into_cb),
              ('StepOver', None, 'Step Over', 'F4', "Step Over", self.step_over_cb),
              ('StepOut', None, 'Step Out', 'F5', "Step Out", self.step_out_cb),
              ('Continue', Gtk.STOCK_MEDIA_PLAY, 'Continue', 'F6', "Continue", self.step_continue),
              ('Stop', Gtk.STOCK_STOP, 'Stop', '<Ctrl>F2', "Stop", self.stop_cb)
            ]
            self._action_group.add_actions(actions)
            
            # Set custom icons
            step_into_action = self._action_group.get_action('StepInto')
            step_into_action.set_gicon(STEP_INTO_GIO_ICON)
            
            step_out_action = self._action_group.get_action('StepOut')
            step_out_action.set_gicon(STEP_OUT_GIO_ICON)
            
            step_over_action = self._action_group.get_action('StepOver')
            step_over_action.set_gicon(STEP_OVER_GIO_ICON)
            
            debug_action = self._action_group.get_action('Debug')
            debug_action.set_gicon(DEBUGGER_GIO_ICON)
            
            
            # Insert the action group
            manager.insert_action_group(self._action_group, -1)
            self._ui_id = manager.add_ui_from_string(menu_ui_str)
            panel.add_item(self._context_box, "debuggerpanel", "Python debugger", None)
        else:
            panel.add_titled(self._context_box, "debuggerpanel", "Python debugger")
        panel.show_all()
        
        hid = self.window.connect("active-tab-state-changed", self.on_tab_state_changed)
        self._handlers.append((self.window, hid))
        hid = self.window.connect("active-tab-changed", self.on_active_tab_changed)
        self._handlers.append((self.window, hid))
        hid = self.window.connect("tab-removed", self.on_tab_removed)
        self._handlers.append((self.window, hid))
        self.setDebugging(False)
    
    def step_into_cb(self, cb):
        self.clear_markers()
        if self._debugger and self._debugger.attached:
            self._debugger.Step()

    def step_over_cb(self, cb):
        self.clear_markers()
        if self._debugger and self._debugger.attached:
            self._debugger.Next()
            
    def step_out_cb(self, cb):
        self.clear_markers()
        if self._debugger and self._debugger.attached:
            self._debugger.StepReturn()
            
    def step_continue(self, cb):
        print("step_continue")
        self.clear_markers()
        if self._debugger and self._debugger.attached:
            self._debugger.Continue()
    
    def stop_cb(self, cb):
        self.clear_markers()
        if self._debugger and self._debugger.attached:
            self._debugger.Quit()
    
    def setDebugging(self, val):
        print("Setting debugging to:", val)
        self._debugging = val
        debug_action = self._action_group.get_action('Debug')
        step_into_action = self._action_group.get_action('StepInto')
        step_out_action = self._action_group.get_action('StepOut')
        step_over_action = self._action_group.get_action('StepOver')
        step_continue_action = self._action_group.get_action('Continue')
        stop_action = self._action_group.get_action('Stop')
        
        debug_action.set_sensitive(not val)
        step_into_action.set_sensitive(val)
        step_out_action.set_sensitive(val)
        step_over_action.set_sensitive(val)
        step_continue_action.set_sensitive(val)
        stop_action.set_sensitive(val)
    
    def do_deactivate(self):
        for obj, hid in self._handlers:
            obj.disconnect(hid)
        self._handlers = None
        self.window.remove_action("gqdb")
        panel = self.window.get_bottom_panel()
        panel.remove(self._context_box)
        if GEDIT_VERSION < V("3.10"):
            manager = self.window.get_ui_manager()
            manager.remove_ui(self._ui_id)
    
    def do_update_state(self):
        pass
        
    def on_tab_state_changed(self, window, data=None):
        view = self.window.get_active_view()
        if not view:
            return
    
    def on_tab_removed(self, window, tab, data=None):
        if tab in self._views:
            del self.views[tab]
    
    def on_active_tab_changed(self, window, tab, data=None):
        view = self.window.get_active_view()
        if not view:
            return
            
        if view not in self._views:
            view.set_show_line_marks(True)
            source_attrs = GtkSource.MarkAttributes()
            source_attrs.set_pixbuf(BREAKPOINT_PIXBUF)
            view.set_mark_attributes("1", source_attrs, 1)

            source_attrs = GtkSource.MarkAttributes()
            source_attrs.set_pixbuf(CURRENT_STEP_PIXBUF)
            view.set_mark_attributes("2", source_attrs, 2)

            view.connect('button-press-event', self.button_press_cb)
    
    def button_press_cb(self, view, ev):
        mark_category = "1"
        buf = view.get_buffer()
        # check that the click was on the left gutter
        if ev.window == view.get_window(Gtk.TextWindowType.LEFT):
            if ev.button != 1:
                return

            if ev.type != Gdk.EventType._2BUTTON_PRESS:
                return

            current_doc = self.window.get_active_document().get_location()
            if not current_doc:
                return
            print(current_doc.get_path())
            current_doc_path = current_doc.get_path()

            x_buf, y_buf = view.window_to_buffer_coords(Gtk.TextWindowType.LEFT,
                                                    int(ev.x), int(ev.y))
            # get line bounds
            line_start = view.get_line_at_y(y_buf)[0]
            lineno = line_start.get_line() + 1

            # get the markers already in the line
            mark_list = buf.get_source_marks_at_line(line_start.get_line(), mark_category)
            # search for the marker corresponding to the button pressed
            for m in mark_list:
                if m.get_category() == mark_category:
                    # a marker was found, so delete it
                    buf.delete_mark(m)
                    self._breakpoints.remove(LineBreakpoint(current_doc_path, lineno, 0))
                    if self._debugger and self._debugger.attached:
                        self._debugger.ClearBreakpoint(current_doc_path, lineno)
                    break
            else:
                # no marker found, create one
                buf.create_source_mark(None, mark_category, line_start)
                #self._breakpoints_liststore.append([True, 'Line: ' + str(line_start.get_line() + 1),
                #                                    self._breakpoint_pixbuf])
                self._breakpoints.add(LineBreakpoint(current_doc_path, lineno, 0))                
                if self._debugger and self._debugger.attached:
                    self._debugger.SetBreakpoint(current_doc_path, lineno)

    @idle_add_decorator
    def _clear_interaction(self, sender):
        print("Clear interaction")
        self.clear_markers()
        self._context_box.clear()
        self.setDebugging(False)
##        while Gtk.events_pending():
##            Gtk.main_iteration_do(False)
        #self._debugger.close()

    @idle_add_decorator
    def mark_current_line(self, sender, filename, lineno, context):
        lineno -= 1
        
        gfile = Gio.File.new_for_path(filename)
        document_tab = self.window.get_tab_from_location(gfile)
        if not document_tab:
            # no tab opened with this document, lets open it
            self.window.create_tab_from_location(gfile, None, lineno + 1, 0, False, True)
            document_tab = self.window.get_tab_from_location(gfile)
        
        document = document_tab.get_document()
        self.window.set_active_tab(document_tab)
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
            
        print("Setting mark at line: ", lineno)
        document.goto_line(lineno)
        document.create_source_mark(None, "2", document.get_iter_at_line(lineno))
        self._context_box.set_context(context)
    
    def clear_markers(self):
        for doc in self.window.get_documents():
            start, end = doc.get_bounds()
            doc.remove_source_marks(start, end, "2")
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    
    def _attach(self, retry=0):
        if not self._debugger.attached:
            if retry == 10:
                raise Exception("Max retries error.")
            try:
                time.sleep(0.5)
                self._debugger.attach()
            except ConnectionRefusedError as e:
                self._attach(retry+1)
    
    def execute(self, file_path):
        # ask for interpreter
        diag = InterpretersDialog(PYTHON_RUNTIMES)
        pythexec = diag.run()
        if not pythexec:
            return

        self._debugger = CallbackFrontend(breakpoints=self._breakpoints)
        self._debugger.connect_signal('write', self._context_box.write_stdout)
        self._debugger.connect_signal('mark-current-line', self.mark_current_line)
        self._debugger.connect_signal('clear-interaction', self._clear_interaction)
        self._debugger.init(cont=True)
        self.setDebugging(True)
        
        cdir, filen = os.path.split(file_path)
        if not cdir:
            cdir = "."
        cwd = os.getcwd()
        try:
            os.chdir(cdir)
            cmd = pythexec + " -u " + QDB_LAUNCHER_PATH + ' ' + file_path
            print("Executing: ", cmd)
            proc = subprocess.Popen([cmd], shell=True, close_fds=True)
            retries = 0
            self._attach()
        except Exception as e:
            self.setDebugging(False)
            raise
        finally:
            os.chdir(cwd)

    def debug(self, action=None):
        active_document = self.window.get_active_document()
        doc_location = active_document.get_location()
        if not doc_location:
            return
        self.execute(doc_location.get_path())
