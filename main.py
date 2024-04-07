from core.modulemanager import ModuleManager

from core.modules.log import Log
import modules

def main():
    with ModuleManager('vcs') as module_manager:
        module_manager.register(Log)
        # TODO: Implement a dependency system. For now, force Manifest to load
        #       first.
        module_manager.register_package(modules)
        module_manager.run()

if __name__ == '__main__':
    main()
