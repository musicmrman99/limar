from core.shellscript import ShellScript

# Types
from argparse import ArgumentParser, Namespace

class ShellModule:
    # Lifecycle
    # --------------------

    # NOTE: As a core module, this module follows the core module lifecycle,
    #       which 'wraps around' the main module lifecycle.

    def __init__(self):
        self._script = None

    def dependencies(self):
        return ['log']

    def configure_root_args(self, *, parser: ArgumentParser, **_) -> None:
        parser.add_argument('--shell-script', default='/tmp/vcs-source',
            help="""
            The path to a temporary script file that will be sourced in the
            parent shell (outside of this python app). When using this module,
            it is recommended for your app to use a shell wrapper (such as a
            bash function) that generates the value for this option, passes it
            to your app, then sources the file it refers to.

            This option allows other modules to add commands to execute in the
            context of the calling shell process, such as changing directory or
            setting environment variables.
            """)

    def start(self, *, mod: Namespace, args: Namespace, **_):
        self._mod = mod
        self._script = ShellScript(args.shell_script)

    def stop(self, *,
            mod: Namespace,
            start_exceptions: list[Exception | KeyboardInterrupt],
            run_exception: Exception | KeyboardInterrupt,
            **_
    ):
        assert self._script is not None, 'stop() run before start()'
        if len(start_exceptions) == 0 and run_exception is None:
            mod.log().debug("Writing added commands to the shell script")
            self._script.write()
        else:
            mod.log().warning(
                "Skipping writing commands to the shell script to avoid causing"
                " any more changes than necessary after the above error(s)."
            )

    # Invokation
    # --------------------

    def add_command(self, command: str) -> None:
        assert self._script is not None, 'add_shell_command() run before start()'
        self._mod.log().debug(
            f"Adding shell command to shell script: {command}"
        )
        self._script.add_command(command)
