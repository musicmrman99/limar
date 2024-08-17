from core.modulemanager import ModuleManager
from core.modules.docs_utils.docs_arg import docs_for

import modules

def main():
    """
    LIMAR is an information management tool.
    """

    with ModuleManager(main, 'limar') as module_manager:
        module_manager.register_package(modules)
        module_manager.run()

if __name__ == '__main__':
    main()
