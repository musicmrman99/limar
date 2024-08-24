import random
from core.exceptions import LIMARException

# Types
from typing import Iterable
from core.modules.phase_utils.phase import Phase
from core.modules.phase_utils.phase_system import PhaseSystem

class PhasedProcess:
    """
    Tracks the current phase of a process and allows inspection and mutation of
    that phase according to the rules of the phase system it uses.

    The name of a phased process is the same as the name of the phase system it
    uses. If you have multiple statically identifiable sets of processes that
    use the same phase system, you should override the process 'name' when
    creating the phased process to make it easier for users to differentiate
    between them. For all of those sets that will only ever contain a single
    process instance, then you should set the 'id_length' to 0 when creating the
    phased processes with those names to enforce only a single instance of the
    process with each of those names. For example:

        # A system with one process instance.
        system_a = PhaseSystem(f'{__name__}:system_a', ['a', 'b', 'c'])
        sA_proc = PhasedProcess(system_b, id_length=0)

        # A system with one statically identifiable process type, which has
        # potentially multiple instances.
        system_a = PhaseSystem(f'{__name__}:system_b', ['a', 'b', 'c'])
        sB_p1 = PhasedProcess(system_a)
        sB_p2 = PhasedProcess(system_a)
        sB_p2 = PhasedProcess(system_a)

        # A system with two statically identifiable process types (A and B),
        # where A has a single instance, and B has potentially multiple
        # instances.
        system_c = PhaseSystem(f'{__name__}:system_c', ['a', 'b', 'c'])
        sC_pA = PhasedProcess(system_c, name=f'{__name__}:main.a', id_length=0)
        sC_pB1 = PhasedProcess(system_c, name=f'{__name__}:main.b')
        sC_pB2 = PhasedProcess(system_c, name=f'{__name__}:main.b')
        sC_pB3 = PhasedProcess(system_c, name=f'{__name__}:main.b')

    If you try to register multiple phase processes with the same name with the
    PhaseModule, it will raise an error. The longer the id_length is, the lower
    the chance of conflicts. 8 is the default, as and id_length of >=8 makes
    conflicts rare enough for a small number of processes.
    """

    def __init__(self,
            phase_system: PhaseSystem,
            *,
            initial_phase: Phase | None = None,
            completed_phase: Phase | None = None,
            name: str | None = None,
            id_length: int | None = None
    ):
        self._phase_system = phase_system

        if name is None:
            name = phase_system.name()
        if id_length is None:
            id_length = 8
        process_id = f'{random.getrandbits(4*id_length):0{id_length}x}'
        self._name = f'{name}({process_id})'

        self._cur_phase = phase_system.initial_phase()
        if initial_phase is not None:
            self._cur_phase = initial_phase

        self._completed_phase = phase_system.completed_phase()
        if completed_phase is not None:
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
            raise LIMARException(
                f"Phased process '{self._name}' cannot transition phase from"
                f" '{self._cur_phase}' to '{phase}'. Transition not allowed by"
                f" phase system '{self._phase_system.name()}'."
            )

        if (
            self._cur_phase in self._subprocesses and
            not self._subprocesses[self._cur_phase].is_complete()
        ):
            raise LIMARException(
                f"Phased process '{self._name}' cannot transition phase from"
                f" '{self._cur_phase}' to '{phase}'. Subprocess"
                f" '{self._subprocesses[phase].name()}' not yet completed."
            )

        self._cur_phase = phase

    def transition_to_next(self):
        self.transition_to(self._phase_system.apply_delta(self._cur_phase, +1))

    def transition_to_complete(self):
        if self._completed_phase is None:
            raise LIMARException(
                f"Phased process '{self._name}' does not have a completed phase"
                " to transition to"
            )

        self.transition_to(self._completed_phase)

    # Subprocesses

    def start_subprocess(self, phase: Phase, process: "PhasedProcess"):
        if phase in self._subprocesses:
            raise LIMARException(
                f"Phase '{phase}' already has registered subprocess"
                f" '{process.name()}'. Cannot register another subprocess"
                " against that phase."
            )

        self._subprocesses[phase] = process

    def stop_subprocess(self, phase: Phase, force: bool = False):
        if phase not in self._subprocesses:
            raise LIMARException(
                f"Cannot stop subprocess for phase '{phase}' because no"
                " subprocess was started for it."
            )

        if not force and not self._subprocesses[phase].is_complete():
            raise LIMARException(
                f"Cannot stop subprocess '{self._subprocesses[phase].name()}'"
                f" started for phase '{phase}' because it is not complete."
                " Developers: If it does not matter if the process is complete,"
                " use `process.stop_subprocess(phase, force=True)`."
            )

        del self._subprocesses[phase]

    def get_subprocess_for(self, phase: Phase) -> "PhasedProcess":
        return self._subprocesses[phase]
