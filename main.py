import os
import sys
import time
import subprocess

from gi.repository import Gtk, GtkSource, GLib, GdkPixbuf, Gdk
from debugger_frontend import CallbackFrontend


def idle_add_decorator(func):
    def callback(*args):
        GLib.idle_add(func, *args)
    return callback


class DebuggerGTKGui:

    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file("main.ui")    
        win = builder.get_object("window1")
        box1 = builder.get_object("box1")
        self._variables_treestore = builder.get_object("variables_treestore")
        self._breakpoints_liststore = builder.get_object("breakpoints_liststore")
        
        self._console_textbuffer = builder.get_object("console_textbuffer")
        self._console_textview = builder.get_object("console_textview")
        
        self._filechooserbutton = builder.get_object("filechooserbutton1")
        self._main_scrolledwindow = builder.get_object("main_scrolledwindow")        
        
        self.sourceview = GtkSource.View.new()
        self.sourceview.set_show_line_marks(True)
        self.sourceview.set_show_line_numbers(True)
        self.sourceview.connect('button-press-event', self.button_press_cb)
        
        # toolbar
        step_into_toolbutton = builder.get_object("step_into_toolbutton")
        step_into_image = Gtk.Image()
        step_into_image.show()
        step_into_image.set_from_file("images/anjuta-step-into-16.png")
        step_into_toolbutton.set_icon_widget(step_into_image)
        
        step_over_toolbutton = builder.get_object("step_over_toolbutton")
        step_over_image = Gtk.Image()
        step_over_image.show()
        step_over_image.set_from_file("images/anjuta-step-over-16.png")
        step_over_toolbutton.set_icon_widget(step_over_image)
        
        step_out_toolbutton = builder.get_object("step_out_toolbutton")
        step_out_image = Gtk.Image()
        step_out_image.show()
        step_out_image.set_from_file("images/anjuta-step-out-16.png")
        step_out_toolbutton.set_icon_widget(step_out_image)
        bk_pixbuf = GdkPixbuf.Pixbuf.new_from_file("images/breakpoint.png")
        source_attrs = GtkSource.MarkAttributes()
        source_attrs.set_pixbuf(bk_pixbuf)
        self.sourceview.set_mark_attributes("1", source_attrs, 2)
        
        current_step_pixbuf = GdkPixbuf.Pixbuf.new_from_file("images/step_current.png")
        source_attrs = GtkSource.MarkAttributes()
        source_attrs.set_pixbuf(current_step_pixbuf)
        self.sourceview.set_mark_attributes("2", source_attrs, 1)
        
        self.buffer = self.sourceview.get_buffer()
        self.lm = GtkSource.LanguageManager.new()
        
        self._style_manager = GtkSource.StyleSchemeManager.get_default()
        oblivion = self._style_manager.get_scheme('oblivion')
        self.buffer.set_style_scheme(oblivion)
        
        self._variable_pixbuf = GdkPixbuf.Pixbuf.new_from_file("images/greendot_big.gif")
        self._breakpoint_pixbuf = GdkPixbuf.Pixbuf.new_from_file("images/breakpoint.png")
        self._breakpoint_disabled_pixbuf = GdkPixbuf.Pixbuf.new_from_file("images/breakpoint_disabled.png")
        
        self._main_scrolledwindow.add(self.sourceview)
        
        win.connect("delete-event", self.on_quit)
        win.show_all()
        builder.connect_signals(self)
        
        self.debugging = False
        
        self.debugger = CallbackFrontend()
        self.debugger.connect_signal('write', self.write_msg)
        self.debugger.connect_signal('mark-current-line', self.mark_current_line)
        
        self._current_file = None
        self.sourceview.set_visible(False)
        
        Gtk.main()
    
    def on_quit(self, widget, event):
        self.debugger.close()
        Gtk.main_quit()
    
    def on_breakpoint_cell_toggle(self, cell, path):
        if path is not None:
            it = self._breakpoints_liststore.get_iter(path)
            self._breakpoints_liststore[it][0] = not self._breakpoints_liststore[it][0]
            if self._breakpoints_liststore[it][0]:
                self._breakpoints_liststore[it][2] = self._breakpoint_pixbuf
            else:
                self._breakpoints_liststore[it][2] = self._breakpoint_disabled_pixbuf
    
    def open_file_in_srcview(self, filename, *args, **kwargs):
        self.buffer = self.sourceview.get_buffer()
        self.filename = filename
        self.language = self.lm.guess_language(self.filename,None)
        self.sourceview.set_show_line_numbers(True)
        if self.language:
            self.buffer.set_highlight_syntax(True)
            self.buffer.set_language(self.language)
        else:
            print('No language found for file "%s"' % self.filename)
            self.buffer.set_highlight_syntax(False)
        with open(self.filename, 'r') as f:
            self.buffer.set_text(f.read())
        self.buffer.place_cursor(self.buffer.get_start_iter())
        self._current_file = filename
        self.sourceview.set_visible(True)
    
    def clear_markers(self):
        start, end = self.buffer.get_bounds()
        self.buffer.remove_source_marks(start, end, "2")
        self._variables_treestore.clear()
    
    def button_press_cb(self, view, ev):
        mark_category = "1"
        buf = view.get_buffer()
        # check that the click was on the left gutter
        if ev.window == view.get_window(Gtk.TextWindowType.LEFT):
            if ev.button != 1:
                return
            
            if ev.type != Gdk.EventType._2BUTTON_PRESS:
                return
                
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
                    if self.debugger.attached:
                        self.debugger.ClearBreakpoint(self._current_file, line_start.get_line() + 1)
                    else:
                        self.debugger.ClearBreakpointOffline(self._current_file, line_start.get_line() + 1)
                    break
            else:
                # no marker found, create one
                buf.create_source_mark(None, mark_category, line_start)
                self._breakpoints_liststore.append([True, 'Line: ' + str(line_start.get_line() + 1),
                                                    self._breakpoint_pixbuf])
                if self.debugger.attached:
                    self.debugger.SetBreakpoint(self._current_file, line_start.get_line() + 1)
                else:
                    self.debugger.SetBreakpointOffline(self._current_file, line_start.get_line() + 1)
                
        return False

    def on_open_file(self, widget):
        self.open_file_in_srcview(widget.get_filename())
    
    def on_save_clicked(self, widget):
        if self._current_file:
            with open(self._current_file, 'w') as f:
                start, end = self.buffer.get_bounds()
                f.write(self.buffer.get_text(start, end, False))
    
    def on_close_file_clicked(self, widget):
        self.buffer.set_text("")
        self._filechooserbutton.set_filename("")
        self._current_file = None
        self.sourceview.set_visible(False)
    
    def on_run_clicked(self, widget):
        if not self.debugging:
            self.debugging = True
            self.debugger.init(1)
            self.execute()

    def on_next_clicked(self, widget):
        self.clear_markers()
        self.debugger.Next()
        
    def on_continue_clicked(self, widget):
        self.clear_markers()
        self.debugger.Continue()
        
    def on_step_clicked(self, widget):
        self.clear_markers()
        self.debugger.Step()
    
    def on_step_out_clicked(self, widget):
        self.clear_markers()
        self.debugger.StepReturn()
        
    def on_stop_clicked(self, widget):
        self.clear_markers()
        self.debugger.Quit()
        self.debugging = False
    
    def execute(self, debug=True):
        cdir, filen = os.path.split(self._current_file)
        if not cdir: 
            cdir = "."
        cwd = os.getcwd()
        try:
            os.chdir(cdir)
            pythexec = sys.executable
            print("Executing: %s" % self._current_file)
            
            proc = subprocess.Popen([pythexec + " -u qdb.py " + self._current_file], 
             shell=True, close_fds=True)
            if debug:
                time.sleep(0.5)
                self.debugger.attach()
        except Exception as e:
            raise
        finally:
            os.chdir(cwd)
    
    @idle_add_decorator
    def write_msg(self, sender, msg):
        start, end = self._console_textbuffer.get_bounds()
        self._console_textbuffer.insert(end, msg)
        
        it = self._console_textbuffer.get_iter_at_line(self._console_textbuffer.get_line_count() - 1)
        tmark = self._console_textbuffer.create_mark("eot", it, False)
        self._console_textview.scroll_to_mark(tmark, 0, False, 0, 0)
                
    @idle_add_decorator
    def mark_current_line(self, sender, filename, lineno, context):
        print("context: ", context)
        self.buffer.place_cursor(self.buffer.get_iter_at_line(lineno - 1))
        self.sourceview.set_highlight_current_line(True)
        self.buffer.create_source_mark(None, "2", self.buffer.get_iter_at_line(lineno - 1))
        
        # Add context
        globals_it = self._variables_treestore.append(None, [self._variable_pixbuf,
                                                             "Globals", "Global variables"])
        for g in context['environment']['globals'].keys():
            val, vtype = context['environment']['globals'][g]
            it = self._variables_treestore.append(globals_it, [self._variable_pixbuf,
                                                               g, vtype + ': ' + val])
            
        # now add locals
        for k in context['environment']['locals'].keys():
            val, vtype = context['environment']['locals'][k]
            it = self._variables_treestore.append(None, [self._variable_pixbuf,
                                                         k, vtype + ': ' + val])

if __name__ == '__main__':
    DebuggerGTKGui()
