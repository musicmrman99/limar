from core.exceptions import VCSException

# Types
from typing import Iterable
from core.modules.phase_utils.phase import Phase
from core.modules.phase_utils.phase_system import PhaseSystem

class PhasedProcess:
    """
    Tracks the current phase of a process and allows inspection and mutation of
    that phase according to the rules of the phase system it uses.
    """

    def __init__(self,
            name: str,
            phase_system: PhaseSystem,
            initial_phase: Phase,
            completed_phase: Phase | None = None
    ):
        self._name = name
        self._phase_system = phase_system
        self._cur_phase = initial_phase
        self._completed_phase = completed_phase

        self._subprocesses: dict[Phase, PhasedProcess] = {}

    # Getters

    def name(self) -> str:
        return self._name

    def phase_system(self) -> PhaseSystem:
        return self._phase_system

    def phase(self) -> Phase:
        return self._cur_phase

    # Queries

    def is_before(self, phase: Phase):
        return self._phase_system.get_delta(self._cur_phase, phase) > 0

    def is_at_or_before(self, phase: Phase):
        return self._phase_system.get_delta(self._cur_phase, phase) >= 0

    def is_at(self, phase: Phase):
        return self._phase_system.get_delta(self._cur_phase, phase) == 0

    def is_at_or_after(self, phase: Phase):
        return self._phase_system.get_delta(self._cur_phase, phase) <= 0

    def is_after(self, phase: Phase):
        return self._phase_system.get_delta(self._cur_phase, phase) < 0

    def __lt__(self, phase: Phase):
        return self.is_before(phase)

    def __le__(self, phase: Phase):
        return self.is_at_or_before(phase)

    def __ge__(self, phase: Phase):
        return self.is_at_or_after(phase)

    def __gt__(self, phase: Phase):
        return self.is_after(phase)

    def is_in_any_of(self, phases: Iterable[Phase]):
        return self._cur_phase in phases

    def is_complete(self) -> bool:
        return (
            self._completed_phase is None or
            self.is_at(self._completed_phase)
        )

    # Mutators

    def transition_to(self, phase: Phase):
        if not self._phase_system.can_transition(self._cur_phase, phase):
            raise VCSException(
                f"Phased process '{self._name}' cannot transition phase from"
                f" '{self._cur_phase}' to '{phase}'. Transition not allowed by"
                f" phase system '{self._phase_system.name()}'."
            )

        if (
            self._cur_phase in self._subprocesses and
            not self._subprocesses[self._cur_phase].is_complete()
        ):
            raise VCSException(
                f"Phased process '{self._name}' cannot transition phase from"
                f" '{self._cur_phase}' to '{phase}'. Subprocess"
                f" '{self._subprocesses[phase].name()}' not yet completed."
            )

        self._cur_phase = phase

    def transition_to_next(self):
        self.transition_to(self._phase_system.apply_delta(self._cur_phase, +1))

    def transition_to_complete(self):
        if self._completed_phase is None:
            raise VCSException(
                f"Phased process '{self._name}' does not have a completed phase"
                " to transition to"
            )

        self.transition_to(self._completed_phase)

    # Subprocesses

    def start_subprocess(self, phase: Phase, process: "PhasedProcess"):
        if phase in self._subprocesses:
            raise VCSException(
                f"Phase '{phase}' already has registered subprocess"
                f" '{process.name()}'. Cannot register another subprocess"
                " against that phase."
            )

        self._subprocesses[phase] = process

    def stop_subprocess(self, phase: Phase, force: bool = False):
        if phase not in self._subprocesses:
            raise VCSException(
                f"Cannot stop subprocess for phase '{phase}' because no"
                " subprocess was started for it."
            )

        if not force and not self._subprocesses[phase].is_complete():
            raise VCSException(
                f"Cannot stop subprocess '{self._subprocesses[phase].name()}'"
                f" started for phase '{phase}' because it is not complete."
                " Developers: If it does not matter if the process is complete,"
                " use `process.stop_subprocess(phase, force=True)`."
            )

        del self._subprocesses[phase]

    def get_subprocess_for(self, phase: Phase) -> "PhasedProcess":
        return self._subprocesses[phase]
