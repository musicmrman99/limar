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

def list_split(list_, sep):
    lists = [[]]
    for item in list_:
        if item == sep:
            lists.append([])
        else:
            lists[-1].append(item)
    return lists

def list_strip(list_, str_):
    while len(list_) > 0 and list_[0] == str_:
        list_ = list_[1:]
    while len(list_) > 0 and list_[-1] == str_:
        list_ = list_[:-1]
    return list_
