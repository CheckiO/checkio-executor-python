import sys
from pprint import pformat

PY3 = sys.version_info[0] == 3


class AttrDict(object):
    def __init__(self, d):
        self.d = d

    def __getattr__(self, name):
        return self.d[name]

    def __setattr__(self, name, value):
        if name == 'd':
            return super(AttrDict, self).__setattr__(name, value)
        self.d[name] = value


def pformat_none(obj):
    return None if obj is None else pformat(obj)


def unicoder(line):
    if PY3:
        return line
    try:
        try:
            return unicode(line)
        except UnicodeDecodeError:
            return str(line).decode('utf-8')
    except Exception as e:
        return u'*** EXCEPTION ***' + unicoder(e)


def get_traceback_frames(exc_type, exc_value, tb):
    frames = []
    while tb is not None:
        # support for __traceback_hide__ which is used by a few libraries
        # to hide internal frames.
        filename = tb.tb_frame.f_code.co_filename
        if filename == '<MYCODE>':
            function = tb.tb_frame.f_code.co_name
            lineno = tb.tb_lineno
            frames.append({
                'tb': tb,
                'function': function,
                'lineno': lineno,
                'vars': tb.tb_frame.f_locals.items(),
                'id': id(tb),
            })
        tb = tb.tb_next

    if not frames:
        frames = [{
            'filename': '&lt;unknown&gt;',
            'function': '?',
            'lineno': '?',
            'context_line': '???',
        }]

    return frames


def str_frames(ex, frames):
    frames.reverse()
    trace_lines = ['%s: %s' % (type(ex).__name__, unicoder(ex))]
    for frame in frames:
        trace_lines.append(' %s, %s' % (frame['function'], frame['lineno']))
    return '\n'.join(trace_lines) + '\n'


def str_traceback(ex, *args):
    return str_frames(ex, get_traceback_frames(*args))
