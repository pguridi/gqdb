import sys
import os

if __name__ == '__main__':
    # When invoked as main program:
    if '--test' in sys.argv:
        test()
    # Check environment for configuration parameters:
    kwargs = {}
    for param in 'host', 'port', 'authkey':
       if 'QDB_%s' % param.upper() in os.environ:
            kwargs[param] = os.environ['QDB_%s' % param.upper()]

    # start the debugger on a script
    # reimport as global __main__ namespace is destroyed
    import qdb
    qdb.main(**kwargs)
