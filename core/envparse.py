import os
from argparse import Namespace

from core.exceptions import VCSException

# Types
from typing import Any

class EnvironmentParser:
    def __init__(self, prefix: str | None = None):
        self._spec: dict[str, dict[str, Any]] = {}
        self._prefix = (
            self._in_env_case(prefix+'_')
            if prefix is not None and prefix != ''
            else ''
        )
        self._subparsers: list[tuple[str, EnvironmentParser]] = []

    def add_parser(self, prefix):
        subparser = EnvironmentParser(self._prefix + prefix)
        self._subparsers.append((prefix, subparser))
        return subparser

    def add_variable(self,
            name: str,
            type: type | None = None,
            default: Any = None,
            default_is_none: bool = False
    ):
        full_name = self._prefix + self._in_env_case(name)

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

    def parse_env(self,
            env: dict[str, str] | None = None,
            *,
            subparsers_to_use: list[str] | None = None,
            collapse_prefixes: bool = False
    ) -> Namespace:
        """
        If env is given, parse the given env, otherwise parse the system env.

        If subparsers_to_use is given, it is a list of prefixes of subparsers
        to use for this parse. Ignore prefixes where there are no corresponding
        subparsers.

        If collapse is True, then omit this parser's prefix and the prefixes of
        all subparsers from the resulting namespace.
        """

        return Namespace(
            **self._parse_env(env, subparsers_to_use, collapse_prefixes)
        )

    def _parse_env(self,
            env=None,
            subparsers_to_use=None,
            collapse_prefixes=False
    ):
        if env is None:
            env = os.environ

        env_vars = {}

        # Parse this parser's spec
        for name, opts in self._spec.items():
            type = opts['type'] if 'type' in opts else str

            collapsed_name = name
            if collapse_prefixes:
                collapsed_name = name.removeprefix(self._prefix)

            try:
                env_vars[collapsed_name] = type(env[name])
            except KeyError as e:
                if 'default' in opts:
                    env_vars[collapsed_name] = opts['default']
                else:
                    raise VCSException(
                        f"Required environment variable '{name}' not set"
                    ) from e
            except ValueError as e:
                raise VCSException(
                    f"Environment variable '{name}' not parsable as"
                    f" '{type.__name__}"
                ) from e

        # Parse the specs of all selected subparsers
        subparsers = (
            (sp for _, sp in self._subparsers)
            if subparsers_to_use is None else
            (sp for name, sp in self._subparsers if name in subparsers_to_use)
        )
        for subparser in subparsers:
            env_vars.update(subparser._parse_env(
                env,
                subparsers_to_use=subparsers_to_use,
                collapse_prefixes=collapse_prefixes
            ))

        return env_vars

    def _in_env_case(self, name: str):
        return name.replace('-', '_').upper()
