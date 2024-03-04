"""
Entry point for `vcs`.
"""

from core.modulemanager import ModuleManager
from core.environment import Environment

from core.modules.log import Log
from modules.manifest import Manifest

def main():
    env = Environment()
    commands = ModuleManager(env)
    commands.register(
        Log,
        Manifest
    )
    commands.run_cmd_line()

if __name__ == '__main__':
    main()
