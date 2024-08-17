import sys
from core.modulemanager import ModuleManager
import modules

def main():
    """
    LIMAR is an information management tool.
    """

    if main.__doc__ is None:
        print('ERROR: Docs for main() missing. This is an issue with LIMAR, please report it to them.')
        return 1

    with ModuleManager('limar', main.__doc__) as module_manager:
        module_manager.register_package(modules)
        module_manager.run()

    return 0

if __name__ == '__main__':
    sys.exit(main())
