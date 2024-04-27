from core.modulemanager import ModuleManager

from core.modules.log import LogModule
import modules

def main():
    with ModuleManager('vcs') as module_manager:
        module_manager.register(LogModule)
        module_manager.register_package(modules)
        module_manager.run()

if __name__ == '__main__':
    main()
