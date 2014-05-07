from gi.repository import Gtk, Gdk, Pango


class ConsoleWidget(Gtk.VBox):
    '''
    Console widget Class

    @author: Pedro Guridi <pedro.guridi@gmail.com>
    '''

    def __init__(self, maingui):
        Gtk.VBox.__init__(self)
        #self.set_default_size (680, 400)
        self.set_border_width(3)
        self.connect("delete_event", self._quitConsole)

        self.main_gui = maingui

        self._lastCommand = ""
        self._lastReturn = ""

        # Setup text view
        self.text = Gtk.TextView()
        self.text.set_property('can-focus', False)
        self.text.set_property('cursor-visible', False)
        self.text.modify_font(Pango.FontDescription("mono 9"))

        #self.text.modify_base(Gtk.StateType.NORMAL,Gtk.gdk.Color(255,255,255,0))
        self.text.set_editable(False)
        self.text.set_wrap_mode(True)
        self.text.set_left_margin(1)
        self.text.set_right_margin(1)
        self.text.set_size_request(0, 0)
        self.text.set_border_width(0)
        self.text.connect("button-press-event", self.textViewClicked)

        # Setup output text buffer
        self.buffer = self.text.get_buffer()
        self.buffer.create_tag('bold', \
                               weight=Pango.Weight.BOLD, editable=False)

        self._promptHbox = Gtk.HBox()
        self.promptTextview = Gtk.TextView()

        #whiteBg = self.promptTextview.get_style().bg[Gtk.StateType.NORMAL]

        # Setup prompt textView
        self.promptTextview.set_property('can-focus', True)
        self.promptTextview.modify_font(Pango.FontDescription("mono 9"))
        self.promptTextview.set_editable(True)
        self.promptTextview.set_wrap_mode(True)
        self.promptTextview.set_left_margin(1)
        self.promptTextview.set_right_margin(1)
        self.promptTextview.set_border_width(0)
        self._promptHbox.pack_start(self.promptTextview, True, True, 0)

        self.scrollWin = Gtk.ScrolledWindow()
        self.scrollWin.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrollWin.set_shadow_type(Gtk.ShadowType.NONE)
        self.scrollWin.set_border_width(0)

        self.scrollWin.add(self.text)

        self.pack_start(self.scrollWin, True, True, 0)
        self.pack_start(self._promptHbox, False, False, 0)

        self.set_border_width(0)

        # Setup prompt text buffer
        self.promptBuffer = self.promptTextview.get_buffer()
        self.promptBuffer.create_tag('prompt', \
                                     weight=Pango.Weight.BOLD, editable=False)

        self.promptTextview.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        self.promptTextview.connect('key-press-event', self.onKeyPressed, self.text, self.buffer, self.promptTextview,
                                    self.promptBuffer)
        self.promptTextview.connect('button-press-event', self._grabPromptFocus)
        self.promptTextview.grab_focus()

        self._isShell = True

        self.promptString = ">>>"

        #self._running = False
        self._closing = False

        self._prompt()

    def _quitConsole(self, widget, event=None):
        self._closing = True
        self.destroy()

    def setBusy(self, val):
        if val:
            self.set_sensitive(False)
        else:
            self.set_sensitive(True)

    def destroyConsole(self):
        self._closing = True
        self.destroy()

    def textViewClicked(self, widget, event):
        self._grabPromptFocus()

    def _grabPromptFocus(self, widget=None, event=None):
        self.promptTextview.grab_focus()
        start, end = self.getCurrentLineBounds()
        self.promptBuffer.place_cursor(end)
        self.promptTextview.place_cursor_onscreen()
        return True

    def _prompt(self):
        """Show the prompt."""
        self.promptBuffer.set_text("")
        self.writeToPrompt(self.promptString)

    def Execute(self, cmd):
        try:
            res = self.main_gui.do_exec(cmd)
            if res != 'None':
                self.writeToOutputBuffer(res + "\n")
        except Exception as e:
            print("invalid cmd")
            print(e)

    def onKeyPressed(self, widget, event, textView, buffer, promptTextView, promptBuffer):
        """ Key pressed handler """
        #if self._running:
        #	return True
        key_name = str(Gdk.keyval_name(event.keyval))
        if key_name == "Left":
            it = self.promptBuffer.get_iter_at_mark(self.promptBuffer.get_insert())
            tagTable = self.promptBuffer.get_tag_table()
            tag = tagTable.lookup('prompt')
            it.backward_char()
            if it.has_tag(tag):
                return True
        elif key_name == "Home":
            self.promptTextview.grab_focus()
            start, end = self.getCurrentLineBounds()
            self.promptBuffer.place_cursor(end)
            self.promptTextview.place_cursor_onscreen()
            return True
        elif key_name == "Return" or key_name == "Enter":
            command = self.getCurrentLine()
            if command.strip() == "":
                return True

            # Wrapper for the help
            logLine = self.promptString + ' ' + command

            self.writeToOutputBold(self.promptString + ' ' + command + "\n")
            commandList = command.split(' ')
            if commandList[0].lower() == 'help':
                self._cmd_help(commandList[1:])
            elif commandList[0].lower() == 'clear':
                self._clear()
                self._prompt()
                return True
            elif commandList[0].lower() == 'exit':
                self._exit()
                return True
            else:
                print("running command: ", command)
                self.Execute(command)
            #self._running = True
            #self.promptTextview.set_cursor_visible(False)

            self._lastCommand = self.promptString + ' ' + command + "\n"
            self._lastReturn = ""
            self._prompt()
            return True
        #		elif event.keyval == Gtk.keysyms.Down:
        #			return self.requestHistoryDown()
        #		elif event.keyval == Gtk.keysyms.Up:
        #			return self.requestHistoryUp()
        #		elif event.keyval == Gtk.keysyms.Tab:
        #			# Completion stuff
        #			self.completeCommand()
        #			return True

    def clearPromptBuffer(self):
        self.promptBuffer.delete(self.promptBuffer.get_start_iter(), self.promptBuffer.get_end_iter())
        self.promptBuffer.place_cursor(self.promptBuffer.get_start_iter())
        self.writeToPrompt(">>>")

    def getCurrentLine(self):
        """ Get current active line """
        start, end = self.getCurrentLineBounds()
        return self.promptBuffer.get_text(start, end, True)

    def getCurrentLineBounds(self):
        """ Get current active line bounds """
        tagTable = self.promptBuffer.get_tag_table()
        tag = tagTable.lookup('prompt')
        start = self.promptBuffer.get_start_iter()
        if tag != None:
            while not start.ends_tag(tag):
                start.forward_char()

        end = self.promptBuffer.get_end_iter()

        return start, end

    def writeCommand(self, command):
        """ Write a command text to the prompt """
        start, end = self.promptTextview.get_buffer().get_bounds()
        self.promptTextview.get_buffer().insert(end, command)
        self.promptBuffer.place_cursor(self.promptBuffer.get_end_iter())

    def writeToOutputBuffer(self, line):
        """ Write text to the output buffer """
        if line[:3] == "#@*":
            code, command, status = line.split("&")
            if status.strip() == "finished":
                self.scrollToEnd()
                #self._running = False
                self.scrollToEnd()
                self.promptTextview.set_cursor_visible(True)
                self._lastCommand = ""
                self._lastReturn = ""
            return
        end = self.buffer.get_end_iter()

        #if line != "":
        self._lastReturn += line
        self.buffer.insert(end, line)

    #self.buffer.insert(end, unicode(line))

    def writeToPrompt(self, line):
        """ Write text to the prompt """
        start, end = self.promptTextview.get_buffer().get_bounds()
        self.promptTextview.get_buffer().insert_with_tags_by_name(end, line, "prompt")
        self.promptBuffer.place_cursor(self.promptBuffer.get_end_iter())

    def writeToOutputBold(self, line):
        """ Write bold text to the output """
        start, end = self.buffer.get_bounds()
        self.buffer.insert_with_tags_by_name(end, line, "bold")
        self.scrollToEnd()

    #buffer.place_cursor(self.promptBuffer.get_end_iter())

    def scrollToEnd(self):
        if self._closing:
            return
        it = self.buffer.get_iter_at_line(self.buffer.get_line_count() - 1)
        tmark = self.buffer.create_mark("eot", it, False)
        self.text.scroll_to_mark(tmark, 0, False, 0, 0)

    def _clear(self):
        """ Clears the output buffer"""
        self.buffer.set_text('\n')
        self.scrollToEnd()

    def _exit(self):
        """ Exits the console"""
        self._closing = True
        self.destroy()
