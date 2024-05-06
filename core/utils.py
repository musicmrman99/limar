from os.path import dirname, basename, isfile, join
import glob

def modules_adjacent_to(file):
    """
    Utility for getting a list of all python modules in the same directory
    as the given python file path.

    Can be used make a package support being registered with
    `register_package()` by placing the following in the package's
    `__init__.py`:
    ```
    from core.modulemanager_utils import modules_adjacent_to
    __all__ = modules_adjacent_to(__file__)
    ```
    """

    # Based on: https://stackoverflow.com/a/1057534/16967315
    modules = glob.glob(join(dirname(file), "*.py"))
    return [
        basename(module)[:-3]
        for module in modules
        if isfile(module) and not basename(module).startswith('__')
    ]
