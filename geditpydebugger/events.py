class Event:

    def __init__(self, name, sync=False):
        self.name = name
        self.listeners = {}
        self.sync = sync

    def add(self, function, data=None):
        self.listeners[function] = data

    def delete(self, function):
        self.listeners.pop(function)

    def called(self, sender, *data):
        try:
            for function, d in list(self.listeners.items()):
                # data : extra parameters to the function
                # sender: object that sent the event
                # function: function registered to handle the event
                #
                if len(data) == 0:
                    if d is None:
                        # Se llama directamente. Sin argumentos
                        function(sender)
                    else:
                        if type(d) == type([]):
                            function(sender, *d)
                        elif type(d) == type({}):
                            function(sender, **d)
                        else:
                            function(sender, d)
                else:
                    # Se llama pasando los datos extras.
                    if d is None:
                        if type(data) == type({}):
                            function(sender, **data)
                        else:
                            function(sender, *data)
                    else:
                        if type(data) == type({}):
                            function(sender, d, **data)
                        else:
                            function(sender, d, *data)

        except Exception as e:
            print(("Error dispaching event: ", e))


class EventManager(object):

    def __init__(self):
        self.events = {}

    def add_event(self, Event):
        self.events[Event.name] = Event

    def del_event(self, Event):
        self.events.pop(Event.name)

    def flush(self):
        self.events.clear()

    def connect(self, event, function, data=None):
        self.events[event].add(function, data)

    def disconnect(self, event, function):
        self.events[event].delete(function)

    def signal(self, event, sender, *args):
        try:
            if len(args) == 0:
                self.events[event].called(sender)
            else:
                self.events[event].called(sender, *args)
            return False
        except Exception as e:
            print(("Error running callback", e))