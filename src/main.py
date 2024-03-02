"""
# TODO:
# parse args
# delegate to subcommands
# parse config (where relevant)
"""

from environment import Environment

from commandset import CommandSet
from commands.log import Log
from commands.manifest import Manifest

def main():
    env = Environment()
    commands = CommandSet(env)
    commands.register(
        Log,
        Manifest
    )
    commands.run_cmd_line()

if __name__ == '__main__':
    main()
