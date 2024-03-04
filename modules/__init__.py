# Based on: https://stackoverflow.com/a/1057534/16967315

from os.path import dirname, basename, isfile, join
import glob

modules = glob.glob(join(dirname(__file__), "*.py"))
__all__ = [
    basename(module)[:-3]
    for module in modules
    if isfile(module) and not basename(module).startswith('__')
]
