from json_serializer import JsonClient
from multiprocessing import Queue

import os
import time

import sys

import threading
import sys

print(sys.path)
from qdb import Frontend

from .breakpoint import LineBreakpoint


class LoggingPipeWrapper:

    def __init__(self, pipe):
        self.__pipe = pipe

    def send(self, data):
        print("PIPE:send: %s %s %s %s" % (data.get("id"), data.get("method"), data.get("args"), repr(data.get("result",""))[:40]))
        self.__pipe.send(data)

    def recv(self, *args, **kwargs):
        data = self.__pipe.recv(*args, **kwargs)
        print("PIPE:recv: %s %s %s %s" % (data.get("id"), data.get("method"), data.get("args"), repr(data.get("result",""))[:40]))
        return data

    def close(self):
        self.__pipe.close()

    def poll(self):
        return self.__pipe.poll()


class CallbackFrontend(Frontend):
    "A callback driven Frontend interface to qdb"

    def __init__(self, pipe=None, breakpoints=None):
        Frontend.__init__(self, pipe)
        self.messages_queue = Queue()
        if breakpoints:
            self._breakpoints = breakpoints
        else:
            self._breakpoints = set()

        self.interacting = False    # flag to signal user interaction
        self.quitting = False       # flag used when Quit is called
        self.attached = False       # flag to signal remote side availability
        self.post_event = True      # send event to the GUI
        self.start_continue = True  # continue on first run
        self.rawinput = None
        self.filename = self.lineno = None
        self.unrecoverable_error = False
        self.pipe = None

        t = threading.Thread(target=self._run)
        t.start()

    """
    Start Frontend API
    """

    def exception(self, *args):
        "Notify that a user exception was raised in the backend"
        if not self.unrecoverable_error:
            print("Exception raised in backend")
            self.unrecoverable_error = "%s" % args[0]

    def startup(self):
        "Initialization procedures (called by the backend)"
        # notification sent by _runscript before Bdb.run
        self.LoadBreakpoints()
        print("enabling call_stack and environment at interaction")
        self.set_params(dict(call_stack=True, environment=True, postmortem=True))
        # return control to the backend:
        Frontend.startup(self)

    def write(self, text):
        "ouputs a message (called by the backend)"
        self.messages_queue.put(("write", (text,)))

    def readline(self):
        "returns a user input (called by the backend)"
        # "raw_input" should be atomic and uninterrupted
        try:
            self.interacting = None
            print("Called readline, not implemented!!")
        finally:
            self.interacting = False

    def interaction(self, filename, lineno, line, **context):
        "Start user interaction -show current line- (called by the backend)"
        self.interacting = True
        try:
            if self.start_continue:
                self.Continue()
                self.start_continue = None
                return

            #  sync_source_line()
            self.filename = self.orig_line = self.lineno = None
            if filename[:1] + filename[-1:] != "<>" and os.path.exists(filename):
                self.filename = filename
                self.orig_line = line.strip().strip("\r").strip("\n")
                self.lineno = lineno
                if self.post_event:
                    # send the event to mark the current line
                    self.messages_queue.put(("mark-current-line", (filename, lineno, context)))
                else:
                    # ignore this (async command) and reenable notifications
                    self.post_event = True
        finally:
            pass


    """
    End Frontend API
    """
    def _run(self):
        "Debugger main loop: read and execute remote methods"
        try:
            while True:
                if self.attached and self.pipe:
                    time.sleep(0.01)
                    while self.pipe.poll():
                        self.run()
        except EOFError as e:
            print("DEBUGGER disconnected...")
            self.detach()
        except IOError as e:
            print("DEBUGGER connection exception:", e)
            self.detach()
        except Exception as e:
            # print the exception message and close (avoid recursion)
            print("DEBUGGER exception", e)
            import traceback
            traceback.print_exc()
            import sys
            sys.exit()
        finally:
            return True

    def init(self, cont=False):
        # restore sane defaults:
        self.start_continue = cont
        self.attached = False
        self.unrecoverable_error = None
        self.quitting = False
        self.post_event = True
        self.lineno = None

    def attach(self, host='localhost', port=6000, authkey=b'secret password'):
        self.address = (host, port)
        self.authkey = authkey
        self.pipe = LoggingPipeWrapper(JsonClient(self.address, authkey=self.authkey))
        self.attached = True
        print("DEBUGGER connected!")

    def detach(self):
        self.attached = False
        if self.pipe:
            self.pipe.close()
        self.clear_interaction()

    def is_remote(self):
        return (self.attached and
                self.address[0] not in ("localhost"))

    def check_interaction(fn):
        "Decorator for mutually exclusive functions"
        def check_fn(self, *args, **kwargs):
            if not self.interacting or not self.pipe or not self.attached:
                print(self.pipe, self.attached)
                print("not interacting! reach a breakpoint or interrupt the running code (CTRL+I)")
            else:
                # do not execute if edited (code editions must be checked)
                #if self.check_running_code(fn.func_name):
                ret = fn(self, *args, **kwargs)
                #if self.post_event:
                #    self.clear_interaction()
                return ret
        return check_fn

    def is_waiting(self):
        # check if interaction is banned (i.e. readline!)
        if self.interacting is None:
            print("cannot interrupt now (readline): debugger is waiting your user input at the Console window")
            return True

    def force_interaction(fn):
        "Decorator for functions that need to break immediately"
        def check_fn(self, *args, **kwargs):
            # only send if debugger is connected and attached
            if not self.pipe or not self.attached or self.is_waiting():
                print(self.attached, self.pipe)
                return False
            # do not send GUI notifications (to not alter the focus)
            self.post_event = False
            # if no interaction yet, send an interrupt (step on the next stmt)
            if not self.interacting:
                self.interrupt()
                cont = True
            else:
                cont = False
            # wait for interaction (only retry i times to not block forever):
            i = 10000
            while not self.interacting and i:
                # allow wx process some events 
                #wx.SafeYield()      # safe = user input "disabled"
                #self.OnIdle(None)   # force pipe processing
                i -= 1              # decrement safety counter
            if self.interacting:
                # send the method request                
                ret = fn(self, *args, **kwargs)

                if self.quitting:
                    # clean up interaction marker
                    self.clear_interaction()
                elif cont:
                    # if interrupted, send a continue to resume
                    self.post_event = True
                    self.do_continue()
                return True
            else:
                # re-enable event notification (interaction not received yet!)
                self.post_event = True
                print("cannot interrupt now (blocked): remote interpreter is not executing python code (ui mainloop, socket poll, c extension, sleep, etc.)")
                return False
        return check_fn

    def clear_interaction(self):
        self.interacting = False
        self.messages_queue.put(("clear-interaction", ()))
        # interaction is done, clean current line marker
        #wx.PostEvent(self.gui, DebugEvent(EVT_DEBUG_ID, 
        #                                 (None, None, None, None)))

#    def check_running_code(self, func_name):
#        "Edit and continue functionality -> True=ok or False=restart"
#        # only check edited code for the following methods:
#        return True
#        if func_name not in ("Continue", "Step", "StepReturn", "Next"):
#            return True
#        if self.filename and self.lineno:
#            #curr_line = self.gui.GetLineText(self.filename, self.lineno)
#            curr_line = open(self.filename, 'r').readlines()[self.lineno]
#            curr_line = curr_line.strip().strip("\r").strip("\n")
#        # check if no exception raised
#        if self.unrecoverable_error:
#            print("Exception raised: %s" % self.unrecoverable_error)
#            quit = False
#            if quit:
#                self.quitting = True
#                self.clear_interaction()
#                self.do_quit()
#                return False
#            else:
#                # clean the error and try to resume:
#                # (raised exceptions could be catched by a except/finally block)
#                self.unrecoverable_error = False
#        # check current text source code against running code
#        if self.lineno is not None and self.orig_line != curr_line:
#            print "edit_and_continue...", self.lineno
#            print "*", self.orig_line, "*"
#            print "*", curr_line, "*"
#            try:
#                compiler.parse(curr_line)
#                self.set_burst(3)
#                self.do_exec(curr_line)
#                print "executed", curr_line
#                ret = self.do_jump(self.lineno+1)
#                print "jump", ret
#                if ret:
#                    raise RuntimeError("Cannot jump to ignore modified line!")
#            except Exception, e:
#                print("Exception: %s" % e)
#                return False
#        return True

    # Methods to handle user interaction by main thread bellow:

    @check_interaction
    def Continue(self, filename=None, lineno=None):
        "Execute until the program ends, a breakpoint is hit or interrupted"
        print("Continue")
        if filename and lineno:
            # set a temp breakpoint (continue to...)
            self.set_burst(2)
            self.do_set_breakpoint(filename, lineno, temporary=1)
        self.do_continue()

    @check_interaction
    def Step(self):
        "Execute until the next instruction (entering to functions)"
        print("> Stepin")
        self.do_step()

    @check_interaction
    def StepReturn(self):
        "Execute until the end of the current function"
        self.do_return()

    @check_interaction
    def Next(self):
        "Execute until the next line (not entering to functions)"
        print("-> Next")
        self.do_next()

    @force_interaction
    def Quit(self):
        "Terminate the program being debugged"
        self.quitting = True
        self.do_quit()

    @check_interaction
    def Jump(self, lineno):
        "Set next line to be executed"
        ret = self.do_jump(lineno)
        if ret:
            print(("Cannot jump %s" % ret))

    def Interrupt(self):
        "Stop immediatelly (similar to Ctrl+C but program con be resumed)"
        if self.attached and not self.is_waiting():
            # this is a notification, no response will come
            # an interaction will happen on the next possible python instruction
            self.interrupt()

    def LoadBreakpoints(self):
        "Set all breakpoints (remotelly, used at initialization)"
        for bk in self._breakpoints:
            self.do_set_breakpoint(bk.fn, bk.line, bk.temporary, None)

    def SetBreakpointOffline(self, filename, lineno, temporary=0, cond=None):
        print("Adding breakpoint: ", filename, lineno)
        self._breakpoints.add(LineBreakpoint(filename, lineno, temporary))

    @force_interaction
    def SetBreakpoint(self, filename, lineno, temporary=0, cond=None):
        "Set the specified breakpoint (remotelly)"
        self.do_set_breakpoint(filename, lineno, temporary, cond)

    def ClearBreakpointOffline(self, filename, lineno, temporary=0):
        "Remove the specified breakpoint (remotelly)"
        bk = LineBreakpoint(filename, lineno, temporary)
        self._breakpoints.remove(bk)

    @force_interaction
    def ClearBreakpoint(self, filename, lineno):
        "Remove the specified breakpoint (remotelly)"
        self.do_clear_breakpoint(filename, lineno)

    @force_interaction
    def ClearFileBreakpoints(self, filename):
        "Remove all breakpoints set for a file (remotelly)"
        self.do_clear_file_breakpoints(filename)

    # modal functions required by Eval (must not block):

#    def modal_write(self, text):
#        "Aux dialog to show output (modal for Exec/Eval)"
#        dlg = wx.MessageDialog(self.gui, text, "Debugger console output",
#               wx.OK | wx.ICON_INFORMATION)
#        dlg.ShowModal()
#        dlg.Destroy()

#    def modal_readline(self, msg='Input required', default=''):
#        "Aux dialog to request user input (modal for Exec/Eval)"
#        return
##        dlg = wx.TextEntryDialog(self.gui, msg,
##                'Debugger console input', default)
##        if dlg.ShowModal() == wx.ID_OK:
##            return dlg.GetValue()
##        dlg.Destroy()

#    @check_interaction
#    def Eval(self, arg):
#        "Returns the evaluation of an expression in the debugger context"
#        if self.pipe and self.attached:
#            try:
#                old_write = self.write
#                old_readline = self.readline
#                # replace console functions
#                self.write = self.modal_write
#                self.readline = self.modal_readline
#                self.post_event = None   # ignore one interaction notification
#                # we need the result right now:
#                return self.do_eval(arg)
#            except qdb.RPCError, e:
#                return u'*** %s' % unicode(e)
#            finally:
#                self.write = old_write
#                self.readline = old_readline


#    @check_interaction
#    def ReadFile(self, filename):
#        "Load remote file"
#        from cStringIO import StringIO
#        data = self.do_read(filename)
#        return StringIO(data)

#    @check_interaction
#    def GetContext(self):
#        "Request call stack and environment (locals/globals)"
#        self.set_burst(3)
#        w = self.do_where()
#        ret = []
#        for filename, lineno, bp, current, source in w:
#            ret.append((filename, lineno, "%s%s" % (bp, current), source))
#        d = {'call_stack': ret}
#        env = self.do_environment()
#        ret = ""
#        d['environment'] = env
#        return d

    # methods used by the shell:

#    def Exec(self, statement, write=None, readline=None):
#        "Exec source code statement in debugger context (returns string)"
#        if statement == "" or not self.attached:
#            # 1. shell seems to call Exec without statement on init
#            # 2. if not debuging, exec on the current local wx shell
#            pass  
#        elif not self.interacting:
#            #wx.Bell()
#            return u'*** no debugger interaction (stop first!)'
#        else:
#            old_write = self.write
#            old_readline = self.readline
#            try:
#                # replace console function
#                if write:
#                    self.write = write
#                if readline:
#                    self.readline = readline
#                self.post_event = None   # ignore one interaction notification
#                # execute the statement in the remote debugger:
#                ret = self.do_exec(statement)
#                if isinstance(ret, basestring):
#                    return ret
#                else:
#                    return str(ret)
#            except qdb.RPCError, e:
#                return u'*** %s' % unicode(e)
#            finally:
#                self.write = old_write
#                self.readline = old_readline
#        return None

#    def GetAutoCompleteList(self, expr=''):
#        "Return list of auto-completion options for an expression"
#        if self.pipe and self.attached and self.interacting:
#            try:
#                self.post_event = None   # ignore one interaction notification
#                return self.get_autocomplete_list(expr)
#            except qdb.RPCError, e:
#                return u'*** %s' % unicode(e)

#    def GetCallTip(self, expr):
#        "Returns (name, argspec, tip) for an expression"
#        if self.pipe and self.attached and self.interacting:
#            try:
#                self.post_event = None   # ignore one interaction notification
#                return self.get_call_tip(expr)
#            except qdb.RPCError, e:
#                return u'*** %s' % unicode(e)

