from argparse import ArgumentParser, Namespace

from core.exceptions import VCSException
from core.modulemanager import ModuleAccessor

from core.modules.phase_utils.phase import Phase
from core.modules.phase_utils.phase_system import PhaseSystem
from core.modules.phase_utils.phased_process import PhasedProcess

class PhaseModule:
    """
    Allows modules to interact with the ModuleManager phasing system, as well as
    to define their own phasing systems.
    """

    def __init__(self):
        self._systems: dict[str, PhaseSystem] = {}
        self._processes: dict[str, PhasedProcess] = {}

    # Invokation
    # --------------------

    @ModuleAccessor.invokable_as_function
    def configure_phase_control_args(self, parser: ArgumentParser):
        """
        Configures the standard phasing arguments on an argument parser.
        """

        parser.add_argument('-L', '--min-phase', default=None,
            help="""
            Specifies that no phases of processing before the given phase should
            be performed, even if the default is to perform them. Overrides
            `--include-from-phase`. The default is no constraints.
            """)
        parser.add_argument('-U', '--max-phase', default=None,
            help="""
            Specifies that no phases of processing after the given phase should
            be performed, even if the default is to perform them. Overrides
            `--include-to-phase`. The default is no constraints.
            """)

        parser.add_argument('-Li', '--include-from-phase', default=None,
            help="""
            Specifies that all phases of processing after the given phase should
            be performed, even if the default is not to perform them. The
            default is no constraints.
            """)
        parser.add_argument('-Ui', '--include-to-phase', default=None,
            help="""
            Specifies that all phases of processing up to the given phase should
            be performed, even if the default is not to perform them. The
            default is no constraints.
            """)

    @ModuleAccessor.invokable_as_service
    def transition_to_phase(self,
            process_name: str,
            phase: Phase,
            args: Namespace,
            default: bool | None = None
    ):
        """
        Transition to the given phase of the given registered process, then
        return whether that phase should run, depending on the args passed.

        Use `configure_phasing_args()` in the `configure_args()` MM lifecycle
        method to configure the args that this service interprets.
        """

        mod_subproc = self._processes[process_name]
        mod_subproc.transition_to(phase)

        # If not within these bounds, then don't run the phase, regardless of
        # the default.
        if (
            (
                args.max_phase is not None and
                mod_subproc.is_after(args.max_phase)
            ) or (
                args.min_phase is not None and
                mod_subproc.is_before(args.min_phase)
            )
        ):
            return False

        # If within these bounds (which may be infinite on one end), then run
        # the phase, regardless of the default.
        if (
            (
                args.include_from_phase is not None and
                args.include_to_phase is not None and
                (
                    mod_subproc.is_at_or_after(args.include_from_phase) and
                    mod_subproc.is_at_or_before(args.include_to_phase)
                )
            ) or (
                args.include_from_phase is not None and
                mod_subproc.is_at_or_after(args.include_from_phase)
            ) or (
                args.include_to_phase is not None and
                mod_subproc.is_at_or_before(args.include_to_phase)
            )
        ):
            return True

        # Otherwise, run the phase only if the module defaults to it being run
        return default

    @ModuleAccessor.invokable_as_config
    def register_static_system(self, system: PhaseSystem):
        """Register a Phase System with the given name."""

        if system.name() in self._systems:
            raise VCSException(
                f"Phase system '{system.name()}' already exists. Cannot"
                " register another phase system with that name."
            )

        self._systems[system.name()] = system

    @ModuleAccessor.invokable_as_service
    def register_system(self, system: PhaseSystem):
        """Register a Phase System with the given name."""

        self.register_static_system(system)

    @ModuleAccessor.invokable_as_service
    def register_process(self, process: PhasedProcess):
        """Register a phased process with the given name."""

        if process.name() in self._processes:
            raise VCSException(
                f"Phased process '{process.name()}' already exists. Cannot"
                " register another phased process with that name."
            )

        self._processes[process.name()] = process

    @ModuleAccessor.invokable_as_service
    def get_system(self, name: str):
        return self._systems[name]

    @ModuleAccessor.invokable_as_service
    def get_process(self, name: str):
        return self._processes[name]
