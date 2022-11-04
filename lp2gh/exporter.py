import sys


class Exporter(object):
    def emit(self, message):
        print(message, file=sys.stderr)
