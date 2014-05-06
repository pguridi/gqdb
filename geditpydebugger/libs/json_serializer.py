import json
from multiprocessing.connection import Listener, Client

class ConnectionWrapper(object):
    def __init__(self, conn):
        self._conn = conn

        for attr in ('fileno', 'close', 'poll', 'recv_bytes', 'send_bytes'):
            obj = getattr(conn, attr)
            setattr(self, attr, obj)
            
    def send(self, obj):
        s = json.dumps(obj)
        self._conn.send_bytes(s.encode("utf-8"))
        
    def recv(self):
        s = self._conn.recv_bytes()
        try:
            return json.loads(s.decode("utf-8"))
        except ValueError as e:
            print(e, str(s))

class JsonListener(Listener):
    def accept(self):
        obj = Listener.accept(self)
        return ConnectionWrapper(obj)

def JsonClient(*args, **kwds):
    return ConnectionWrapper(Client(*args, **kwds))


# Ugly patching to fixe py2<->py3 multiprocessing compatibility
# Reference: http://bugs.python.org/review/17258/patch/7414/27889

from py3compat import PY3
from multiprocessing import connection, AuthenticationError
from multiprocessing.connection import CHALLENGE, WELCOME, \
    MESSAGE_LENGTH, FAILURE
import os
import hashlib

def answer_challenge(conn, authkey):
    import hmac
    message = conn.recv_bytes(256)         # reject large message
    assert message[:len(CHALLENGE)] == CHALLENGE, 'message = %r' % message
    message = message[len(CHALLENGE):]
    digest = hmac.new(authkey, message, hashlib.sha256).digest()
    conn.send_bytes(digest)
    response = conn.recv_bytes(256)        # reject large message
    if response != WELCOME:
        raise AuthenticationError('digest sent was rejected')

def deliver_challenge(conn, authkey):
    import hmac
    message = os.urandom(MESSAGE_LENGTH)
    conn.send_bytes(CHALLENGE + message)
    digest = hmac.new(authkey, message, hashlib.sha256).digest()
    response = conn.recv_bytes(256)        # reject large message
    if response == digest:
        conn.send_bytes(WELCOME)
    else:
        conn.send_bytes(FAILURE)
        raise AuthenticationError('digest received was wrong')

connection.deliver_challenge = deliver_challenge
connection.answer_challenge = answer_challenge