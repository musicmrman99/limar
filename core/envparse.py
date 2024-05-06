import os
from argparse import Namespace

from core.exceptions import VCSException

# Types
from typing import Any

class EnvironmentParser:
    def __init__(self, prefix: str | None = None):
        self._spec = {}
        self._prefix = prefix.upper() if prefix is not None else ''
        self._subparsers: list[EnvironmentParser] = []

    def add_variable(self,
            name: str,
            type: type | None = None,
            default: Any = None,
            default_is_none: bool = False
    ):
        full_name = self._with_prefix(name.upper())

        if full_name in self._spec:
            raise VCSException(
                "Attempt to add environment variable to spec that is already"
                " configured"
            )

        self._spec[full_name] = {
            **({'type': type} if type is not None else {}),
            **({'default': default}
               if default is not None or default_is_none
               else {})
        }

    def add_parser(self, prefix):
        subparser = EnvironmentParser(self._with_prefix(prefix))
        self._subparsers.append(subparser)
        return subparser

    def parse_env(self, env=None):
        return Namespace(**self._parse_env(env))

    def _parse_env(self, env=None):
        if env is None:
            env = os.environ

        env_vars = {}

        # Parse this parser's spec
        for name, opts in self._spec.items():
            type = opts['type'] if 'type' in opts else str
            try:
                env_vars[name] = type(env[name])
            except KeyError as e:
                if 'default' in opts:
                    env_vars[name] = opts['default']
                else:
                    raise VCSException(
                        f"Required environment variable '{name}' not set"
                    ) from e
            except ValueError as e:
                raise VCSException(
                    f"Environment variable '{name}' not parsable as"
                    f" '{type.__name__}"
                ) from e

        # Parse all subparsers' specs
        for subparser in self._subparsers:
            env_vars.update(subparser._parse_env())

        return env_vars

    def _with_prefix(self, name):
        prefix_list = [self._prefix] if self._prefix != '' else []
        return '_'.join([*prefix_list, name])
