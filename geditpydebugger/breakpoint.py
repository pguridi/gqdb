import os
from hashlib import sha1

def canonic(filename):
    if filename == "<" + filename[1:-1] + ">":
        return filename
    canonic = os.path.abspath(filename)
    canonic = os.path.normcase(canonic)
    if canonic.endswith(('.pyc', '.pyo')):
        canonic = canonic[:-1]
    return canonic


class Breakpoint(object):
    """Simple breakpoint that breaks if in file"""

    def __init__(self, file, temporary=False):
        self.fn = file
        if not file.endswith(('.py', '.pyc', '.pyo')):
            file = file_from_import(file)
        self.file = canonic(file)
        self.temporary = temporary

    def on_file(self, filename):
        return canonic(filename) == self.file

    def breaks(self, frame):
        return self.on_file(frame.f_code.co_filename)

    def __repr__(self):
        s = 'Temporary ' if self.temporary else ''
        s += self.__class__.__name__
        s += ' on file %s' % self.file
        return s

    def __eq__(self, other):
        return self.file == other.file and self.temporary == other.temporary

    def __hash__(self):
        s = sha1()
        s.update(repr(self).encode('utf-8'))
        return int(s.hexdigest(), 16)

    def to_dict(self):
        return {
            'fn': getattr(self, 'file', None),
            'lno': getattr(self, 'line', None),
            'cond': getattr(self, 'condition', None),
            'fun': getattr(self, 'function', None)
        }

class LineBreakpoint(Breakpoint):
    """Simple breakpoint that breaks if in file at line"""
    def __init__(self, file, line, temporary=False):
        self.line = line
        super(LineBreakpoint, self).__init__(file, temporary)

    def breaks(self, frame):
        return (super(LineBreakpoint, self).breaks(frame) and
                frame.f_lineno == self.line)

    def __repr__(self):
        return (super(LineBreakpoint, self).__repr__() +
                ' on line %d' % self.line)

    def __eq__(self, other):
        return super(LineBreakpoint, self).__eq__(
            other) and self.line == other.line

    def __hash__(self):
        return super(LineBreakpoint, self).__hash__()
