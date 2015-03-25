import uuid
import random
import re
import sys

try:
    import builtins as __builtin__
except ImportError:
    # http://stackoverflow.com/a/9047762
    import __builtin__

from checkio_executor_python.permissions import CLOSE_BUILDINS
from checkio_executor_python.permissions import ALLOWED_MODULES as _ALLOWED_MODULES
from checkio_executor_python.utils import str_traceback, pformat_none, AttrDict

RANDOM_SEED = uuid.uuid4().hex
random.seed(RANDOM_SEED)


def _import_secure(*args, **kwargs):
    if args[0] not in Runner.ALLOWED_MODULES:
        error_message = (
            "The module `{}` is not allowed on checkio. "
            "Please see http://www.checkio.org/wiki/Modules/SupportedModulesForPython2/"
        ).format(args[0])
        raise ImportError(error_message)
    return __import__(*args, **kwargs)


def _help_secure(val):
    return help(val)


def cover_exec(func, data):
    return func(data)


def _from_str_to_func(func_code):
    g_data = {}
    exec(func_code, g_data)
    return g_data['cover']


class Runner(object):
    ALLOWED_MODULES = _ALLOWED_MODULES
    CHECKIO_INENV = '__CHECKIO_ENV__'  # WTF?

    def __init__(self):
        self.builtins = self.init_builtins()
        self.globals = self.init_globals()
        self._cover_exec = cover_exec
        self._sys_env = None

    def init_builtins(self):
        """
        https://docs.python.org/2/library/__builtin__.html
        __builtins__ - this var is different in running module and imported
        so it used __builtin__ (python 2.7) and builtins (python 3)
        """
        _builtins = {
            '__import__': _import_secure,
            'help': _help_secure
        }
        for name in dir(__builtin__):
            if name in CLOSE_BUILDINS:
                continue
            _builtins[name] = getattr(__builtin__, name)
        return _builtins

    def init_globals(self):
        """
        https://docs.python.org/2/library/functions.html#eval
        eval required __builtins__ in globals (not __builtin__)
        """
        return {
            '__builtins__': self.builtins,
            '__name__': 'MYCODE',
            '__import__': _import_secure
        }

    def execute(self, execution_data):
        callback = self._get_callback(execution_data)
        try:
            return callback(execution_data)
        except ActionFail as e:
            return {
                'status': 'fail',
                'description': str(e)
            }
        except Exception as e:
            return {
                'status': 'fail',
                'description': str(e)
            }

    def _get_callback(self, execution_data):
        callback_name = execution_data.get('action')
        if not callback_name:
            raise RefereeException('`action` is required argument')
        callback_name = "action_" + callback_name
        callback = getattr(self, callback_name, None)
        if not callback:
            raise RefereeException('Callback not found')
        return callback

    def _execute_statement(self, statement):
        """
        expression means "something" while statement means "do something".
        """
        statement = re.sub('\s+$', '', statement).replace('\t', '    ')
        try:
            exec (compile(statement, '<MYCODE>', 'exec'), self.globals)
        except Exception as e:
            sys.stderr.write(str_traceback(e, *sys.exc_info()))
            raise

    def _execute_expression(self, expression):
        """
        expression means "something" while statement means "do something".
        """
        try:
            return eval(compile(expression, '<MYCODE>', 'eval'), self.globals)
        except SyntaxError:
            try:
                exec (compile(expression, '<MYCODE>', 'exec'), self.globals)
            except Exception as e:
                sys.stderr.write(str_traceback(e, *sys.exc_info()))
                raise

    def _config_env(self, data):
        # TODO: add description for config options
        config = data.get('env_config')
        if config is None:
            return

        if 'remove_builtins' in config:
            for name in config['remove_builtins']:
                try:
                    self.builtins.pop(name)
                except KeyError:
                    pass

        if 'add_allowed_modules' in config:
            Runner.ALLOWED_MODULES += config['add_allowed_modules']

        if 'remove_allowed_modules' in config:
            for name in config['remove_allowed_modules']:
                try:
                    Runner.ALLOWED_MODULES.remove(name)
                except ValueError:
                    pass
        if 'cover_code' in config:
            self._cover_exec = _from_str_to_func(config['cover_code'])

        if 'random_seed' in config:
            random.seed(config['random_seed'])

        if 'global_name' in config:
            self.globals.update({'__name__': config['global_name']})

    def action_run_code(self, data):
        self._config_env(data)
        return {
            'status': 'success',
            'result': self._execute_statement(data['code']),
        }

    def action_run_function(self, data):
        self._config_env(data)
        function_name = data.get('function_name')
        function_args = data.get('function_args')
        if function_name is None:
            raise ActionFail('Attribute function_name is required for action run_function')
        try:
            function = self.globals[function_name]
            return {
                'status': 'success',
                'result': self._cover_exec(function, function_args)
            }
        except Exception as e:
            sys.stderr.write(str_traceback(e, *sys.exc_info()))
            raise

    def action_run_code_and_function(self, data):
        self._config_env(data)
        self._execute_statement(data['code'])
        return self.action_run_function(data)

    def action_run_in_console(self, data):
        result = self._execute_expression(data['code'])
        return {
            'status': 'success',
            'result': pformat_none(result)
        }

    def action_config(self, data):
        self._config_env(data)
        return {
            'status': 'success',
        }

    def action_stop(self, data):
        sys.exit(0)


class RefereeException(Exception):
    pass


class ActionFail(RefereeException):
    pass
