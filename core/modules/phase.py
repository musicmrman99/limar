from core.exceptions import VCSException

from core.modulemanager import ModuleAccessor

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

    @ModuleAccessor.invokable_as_service
    def register_system(self, system: PhaseSystem):
        """Registers a Phase System with the given name."""

        if system.name() in self._systems:
            raise VCSException(
                f"Phase system '{system.name()}' already exists. Cannot"
                " register another phase system with that name."
            )

        self._systems[system.name()] = system

    @ModuleAccessor.invokable_as_service
    def register_process(self, process: PhasedProcess):
        """Registers a phased process with the given name."""

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
