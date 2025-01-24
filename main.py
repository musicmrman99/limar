from core.modulemanager import ModuleManager

import modules

def main():
    """
    The Local Information Management, Architecture, and Representation system
    (LIMAR) is a tool for showing and manipulating digital information.

    It primarily achieves this by integrating other tools into a single
    comprehensive and consistent model of concepts, data, and operations called
    the LIMAR Model, though some of its modules provide custom capabilities.
    """

    with ModuleManager(main, 'limar') as module_manager:
        module_manager.register_package(modules)
        module_manager.run()

if __name__ == '__main__':
    main()
