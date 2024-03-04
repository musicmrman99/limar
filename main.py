"""
Entry point for `vcs`.
"""

from core.modulemanager import ModuleManager
from core.environment import Environment

from core.modules.log import Log
import modules

def main():
    env = Environment()
    module_manager = ModuleManager(env)
    module_manager.register(Log)
    module_manager.register_package(modules)
    module_manager.run_command_line()

if __name__ == '__main__':
    main()
