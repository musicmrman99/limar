"""
# TODO:
# parse args
# delegate to subcommands
# parse config (where relevant)
"""

from config import Config

from commandset import CommandSet
from commands.log import Log
from commands.resolve import Resolve
from commands.manifest import Manifest

def main():
    config = Config()
    commands = CommandSet(config)
    commands.register(
        Log,
        Resolve,
        Manifest
    )
    commands.run_cli()

if __name__ == '__main__':
    main()
