import os
from gi.repository import Gtk, Gio, GdkPixbuf

MODULE_DIRECTORY = os.path.dirname(__file__)
ICONS_DIR = os.path.join(MODULE_DIRECTORY, "images")

def get_pixbuf_from_file(image_file):
    return GdkPixbuf.Pixbuf.new_from_file(os.path.join(ICONS_DIR, image_file))

def get_giofileicon_from_file(image_file):
    return Gio.FileIcon.new(Gio.File.new_for_path(os.path.join(ICONS_DIR, image_file)))

BREAKPOINT_PIXBUF = "breakpoint.png"
# BREAKPOINT_HIT_PIXBUF = "breakpoint_hit.png"
CURRENT_STEP_PIXBUF = "current_step.png"
DEBUGGER_CONSOLE_PIXBUF = "debugger_console.png"
DEBUGGER_CONSOLE_IMAGE = Gtk.Image.new_from_pixbuf(get_pixbuf_from_file(DEBUGGER_CONSOLE_PIXBUF))

DEBUG_ICON = "debug_executable.png"
STEP_INTO_ICON = "step_into_instruction.png"
STEP_OUT_ICON = "step_out_instruction.png"
STEP_OVER_ICON = "step_over_instruction.png"
STOP_ICON = "stop.png"
STEP_CONTINUE_ICON = "run.png"
VARIABLE_ICON = "variable.png"