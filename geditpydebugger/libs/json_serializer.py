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
