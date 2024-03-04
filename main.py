"""
Entry point for `vcs`.
"""

from core.modulemanager import ModuleManager
from core.environment import Environment

from core.modules.log import Log
from modules.manifest import Manifest

def main():
    env = Environment()
    modules = ModuleManager(env)
    modules.register(
        Log,
        Manifest
    )
    modules.run_command_line()

if __name__ == '__main__':
    main()
