from gi.repository import Gtk, GtkSource, GLib, GdkPixbuf, Gdk
import os
MODULE_DIRECTORY = os.path.dirname(__file__)

def idle_add_decorator(func):
    def callback(*args):
        GLib.idle_add(func, *args)
    return callback

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
        self._interpreters_dialog.destroy()
        if ret == 0:
            # accept clicked
            act = self._interpreters_combobox.get_active()
            return self._interpreters_liststore[act][1]
        else:
            return None

class ContextBox(Gtk.HPaned):

    def __init__(self):
        Gtk.HPaned.__init__(self)
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(MODULE_DIRECTORY, "main.ui"))

        self._context_notebook = builder.get_object("context_notebook")
        self._console_box = builder.get_object("console_box")
        self._console_textview = builder.get_object("console_textview")

        self.pack1(self._console_box, True, False)
        self.pack2(self._context_notebook, False, True)

    @idle_add_decorator
    def write_stdout(self, sender, msg):
        self._console_textbuffer = self._console_textview.get_buffer()
        start, end = self._console_textbuffer.get_bounds()
        self._console_textbuffer.insert(end, msg)

        it = self._console_textbuffer.get_iter_at_line(self._console_textbuffer.get_line_count() - 1)
        tmark = self._console_textbuffer.create_mark("eot", it, False)
        self._console_textview.scroll_to_mark(tmark, 0, False, 0, 0)