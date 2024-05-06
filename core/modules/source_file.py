from core.shellscript import ShellScript

# Types
from argparse import ArgumentParser, Namespace

class SourceFileModule:
    # Lifecycle
    # --------------------

    # NOTE: As a core module, this module's lifecycle is not the normal MM
    #       module lifecycle. It uses the same method names, but its lifecycle
    #       is managed by ModuleManager directly.

    def __init__(self):
        self._source_file = None

    def dependencies(self):
        return ['log']

    def configure_root_args(self, *, parser: ArgumentParser, **_) -> None:
        parser.add_argument('--mm-source-file', default='/tmp/vcs-source',
            help="""
            The path to a temporary file that will be sourced in the parent
            shell (outside of this python app). Your ModuleManager-based app
            should use a shell wrapper (such as a bash function) that generates
            the value for this option, passes it to the python app, then sources
            the file it refers to.

            This option allows modules managed by ModuleManager to add commands
            to execute in the context of the calling shell process, such as
            changing directory or setting environment variables.
            """)

    def start(self, *, mod: Namespace, args: Namespace, **_):
        self._mod = mod
        self._source_file = ShellScript(args.mm_source_file)

    def stop(self, *,
            mod: Namespace,
            start_exceptions: list[Exception | KeyboardInterrupt],
            run_exception: Exception | KeyboardInterrupt,
            **_
    ):
        assert self._source_file is not None, 'stop() run before start()'
        if len(start_exceptions) == 0 and run_exception is None:
            mod.log().debug("Writing added commands to source file")
            self._source_file.write()
        else:
            mod.log().warning(
                "Skipping writing commands to the source file to avoid causing"
                " any more changes than necessary after the above error(s)."
            )

    # Invokation
    # --------------------

    def add_shell_command(self, command: str) -> None:
        assert self._source_file is not None, 'add_shell_command() run before start()'
        self._mod.log().debug(f"Adding shell command to source file: {command}")
        self._source_file.add_command(command)
