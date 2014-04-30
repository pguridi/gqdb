from gi.repository import Gtk, GtkSource, GLib, GdkPixbuf, Gdk
import os
mod_directory = os.path.dirname(__file__)

def idle_add_decorator(func):
    def callback(*args):
        GLib.idle_add(func, *args)
    return callback


class ContextBox(Gtk.HPaned):

    def __init__(self):
        Gtk.HPaned.__init__(self)
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(mod_directory, "main.ui"))

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