import os
import pwd
import sys
import numpy as np
import json 
from collections.abc import Iterator, Sequence
import socket
import cgi
import telnetlib

from checkio_executor_python.execs import Runner, StopExecuting

PY3 = sys.version_info[0] == 3


class CiOJSEncoderEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, Sequence) or isinstance(obj, Iterator):
            return list(obj)

        return json.JSONEncoder.default(self, obj)

class RefereeClient(object):

    RECV_DATA_SIZE = 100000000
    DEFAULT_CONNECTION_HOST = '127.0.0.1'
    TERMINATOR = '\0'

    def __init__(self, connect_port, connection_host=None):
        if connection_host is None:
            connection_host = self.DEFAULT_CONNECTION_HOST
        self._client = telnetlib.Telnet(connection_host, connect_port)
        self._collected_data = ''

    @property
    def socket(self):
        return self._client.get_socket()

    def request(self, data, skipp_result=None):
        data_json = self._to_json(data)
        self._write(data_json)
        if skipp_result is None:
            return self._get_response_json()

    def _to_json(self, data):
        try:
            return json.dumps(data, cls=CiOJSEncoderEncoder)
        except TypeError:
            result = data.get('result')
            error = u'TypeError: {0} is wrong data type'.format(cgi.escape(str(type(result))))
            return json.dumps({
                'do': 'exec_fail',
                'text': error
            })

    def _get_response(self):
        no_data_counter = 100
        while True:
            if self.TERMINATOR in self._collected_data:
                ter_index = self._collected_data.index(self.TERMINATOR)
                ret = self._collected_data[0:ter_index]
                self._collected_data = self._collected_data[ter_index+1:]
                return ret

            new_data = self._recive_data()
            if not new_data:
                no_data_counter -= 1
                if not no_data_counter:
                    raise ValueError('No data')

            self._collected_data += new_data

    def _get_response_json(self):
        return json.loads(self._get_response())

    def _write(self, data):
        data = data + self.TERMINATOR
        self._client.write(data.encode())

    def _recive_data(self, tries=4):
        self.socket.settimeout(None)
        try:
            data = self.socket.recv(self.RECV_DATA_SIZE)
            if PY3:
                return data.decode('utf-8')
            return data
        except socket.error as e:
            if PY3:
                errno = e.errno
            else:
                errno = e[0]
            if errno != 4:
                tries -= 1
                if not tries:
                    raise
            return self._recive_data(tries=tries)


class ClientLoop(object):
    cls_client = RefereeClient
    cls_runner = Runner

    def __init__(self, port, environment_id):
        self.environment_id = environment_id
        self.client = self.cls_client(port)
        self.runner = self.cls_runner()

    def set_os_permissions(self):
        try:
            robot_uid, robot_gid = pwd.getpwnam('nobody')[2:4]
        except KeyError:
            pass  # for dev version
        else:
            try:
                os.setgroups([])
                os.setgid(robot_gid)
                os.setuid(robot_uid)
                os.umask(0o777)
            except OSError:
                pass  # for dev version

    def start(self):
        self.set_os_permissions()
        execution_data = self.client.request({
            'status': 'connected',
            'environment_id': self.environment_id,
            'pid': os.getpid(),
        })
        while True:
            try:
                results = self.runner.execute(execution_data)
            except StopExecuting:
                break
            else:
                execution_data = self.client.request(results)
