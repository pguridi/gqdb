from gi.repository import Gtk, GtkSource, GLib, GdkPixbuf, Gdk, Gio
import os
import qdb

from .console import ConsoleWidget
from .image_utils import get_giofileicon_from_file, get_pixbuf_from_file, \
    DEBUG_ICON, STEP_INTO_ICON, STEP_OUT_ICON, STEP_OVER_ICON, STOP_ICON, \
    STEP_CONTINUE_ICON, VARIABLE_ICON, BREAKPOINT_PIXBUF

MODULE_DIRECTORY = os.path.dirname(__file__)

ICONS_DIR = os.path.join(MODULE_DIRECTORY, "images", "debugger")

class InterpretersDialog:

    def __init__(self, python_runtimes):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(MODULE_DIRECTORY, "main.ui"))
        self._interpreters_liststore = builder.get_object("interpreters_liststore")
        self._interpreters_combobox = builder.get_object("interpreters_combobox")
        self._interpreters_dialog = builder.get_object("dialog1")
        for py, py_path in python_runtimes:
            self._interpreters_liststore.append([str(py), py_path])
        self._interpreters_combobox.set_active(0)

    def run(self):
        ret = self._interpreters_dialog.run()
        self._interpreters_dialog.hide()
        if ret == 0:
            # accept clicked
            act = self._interpreters_combobox.get_active()
            selected = self._interpreters_liststore[act][1]
            self._interpreters_dialog.destroy()
            return selected
        else:
            self._interpreters_dialog.destroy()
            return None

class ContextBox(Gtk.HPaned):

    def __init__(self, main_gui):
        Gtk.HPaned.__init__(self)
        self.main_gui = main_gui

        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(MODULE_DIRECTORY, "main.ui"))
        builder.connect_signals(self)

        self._context_notebook = builder.get_object("context_notebook")
        self._console_box = builder.get_object("leftbox")
        self._console = ConsoleWidget(self.main_gui)
        self._console_box.pack_start(self._console, True, True, 0)

        self._variables_treestore = builder.get_object("variables_treestore")
        self._callstack_list_store = builder.get_object("callstack_list_store")
        self._breakpoints_liststore = builder.get_object("breakpoints_liststore")

        self.debug_action = builder.get_object("debug_action")
        self.debug_action.set_gicon(get_giofileicon_from_file(DEBUG_ICON))

        self.step_into_action = builder.get_object("step_into_action")
        self.step_into_action.set_gicon(get_giofileicon_from_file(STEP_INTO_ICON))

        self.step_over_action = builder.get_object("step_over_action")
        self.step_over_action.set_gicon(get_giofileicon_from_file(STEP_OVER_ICON))

        self.step_out_action = builder.get_object("step_out_action")
        self.step_out_action.set_gicon(get_giofileicon_from_file(STEP_OUT_ICON))

        self.step_continue_action = builder.get_object("step_continue_action")
        self.step_continue_action.set_gicon(get_giofileicon_from_file(STEP_CONTINUE_ICON))

        self.step_stop_action = builder.get_object("step_stop_action")
        self.step_stop_action.set_gicon(get_giofileicon_from_file(STOP_ICON))

        self.pack1(self._console_box, True, False)
        self.pack2(self._context_notebook, True, True)

    def set_sensitive_buttons(self, val):
        self.debug_action.set_sensitive(not val)
        self.step_into_action.set_sensitive(val)
        self.step_over_action.set_sensitive(val)
        self.step_out_action.set_sensitive(val)
        self.step_continue_action.set_sensitive(val)
        self.step_stop_action.set_sensitive(val)
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)

    def debug_cb(self, widget):
        self.main_gui.debug()

    def stop_cb(self, widget):
        self.main_gui.stop_cb()

    def step_into_cb(self, widget):
        self.main_gui.step_into_cb()

    def step_over_cb(self, widget):
        self.main_gui.step_over_cb()

    def step_out_cb(self, widget):
        self.main_gui.step_out_cb()

    def step_continue_cb(self, widget):
        self.main_gui.step_continue()

    def on_breakpoint_cell_toggle(self, widget, row, col):
        model = widget.get_model()
        bk = model[row][3]
        self.main_gui.goto_file_lineno(bk.file, bk.line)
        print(bk.file, bk.line)

    def clear(self):
        self._variables_treestore.clear()
        self._callstack_list_store.clear()

    def set_context(self, context):
        self.BuildCallStackList(context["call_stack"])
        self._variables_treestore.clear()
        globals_it = self._variables_treestore.append(None, [get_pixbuf_from_file(VARIABLE_ICON),
                                                          "Globals", "Global variables"])
        for g in context['environment']['globals'].keys():
            val, vtype = context['environment']['globals'][g]
            it = self._variables_treestore.append(globals_it, [get_pixbuf_from_file(VARIABLE_ICON),
                                                            g, vtype + ': ' + val])

        # now add locals
        for k in context['environment']['locals'].keys():
            val, vtype = context['environment']['locals'][k]
            it = self._variables_treestore.append(None, [get_pixbuf_from_file(VARIABLE_ICON),
                                                      k, vtype + ': ' + val])

    def add_breakpoint(self, bk):
        self._breakpoints_liststore.append([True, str(bk.file) + ':' + str(bk.line),
                                            get_pixbuf_from_file(BREAKPOINT_PIXBUF), bk])

    def remove_breakpoint(self, bk):
        for row in self._breakpoints_liststore:
            if row[3] == bk:
                self._breakpoints_liststore.remove(row.iter)
                break

    def BuildCallStackList(self, items):
        self._callstack_list_store.clear()
        stack = items[1:]
        for i in range(0, len(stack)):
            row = stack.pop()
            filepath, filename = os.path.split(row[0])
            line = row[1]
            func = row[4].strip()
            self._callstack_list_store.append([str(i), filename, str(line), func, row[0]])

    def write_stdout(self, msg):
        self._console.writeToOutputBuffer(msg)
        return
