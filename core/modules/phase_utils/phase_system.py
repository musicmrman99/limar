from argparse import Namespace

from core.exceptions import LIMARException

# Types
from core.modules.phase_utils.phase import Phase

PhaseJumps = dict[Phase, tuple[Phase, ...]]
class PhaseSystem:
    """
    Specifies the rules of how a defined set of phases relate to one another and
    the allowed transitions between them.
    """

    def __init__(self,
            name: str,
            phases: tuple[Phase, ...],
            phase_jumps: PhaseJumps | None = None,
            *,
            initial_phase: str | None = None,
            completed_phase: str | None = None,
            is_linear: bool = True,
    ):
        self._name = name
        self._is_linear = is_linear

        # Initial and completed phases
        self._initial_phase = 'INITIALISE'
        if initial_phase is not None:
            self._initial_phase = initial_phase
        self._completed_phase = completed_phase

        # Phases
        self._phases = phases
        if self._initial_phase not in self._phases:
            self._phases = (self._initial_phase, *self._phases)
        if (
            self._completed_phase is not None and
            completed_phase not in self._phases
        ):
            self._phases = (*self._phases, self._completed_phase)

        # Phase Jumps
        self._phase_jumps = {}
        if phase_jumps is not None:
            self._phase_jumps = phase_jumps

        # For user convenience
        self.PHASES = Namespace(**{name: name for name in phases})

    # Getters

    def name(self) -> str:
        return self._name

    def initial_phase(self) -> str:
        return self._initial_phase

    def completed_phase(self) -> str | None:
        return self._completed_phase

    # Queries

    def has_phase(self, phase: str) -> bool:
        return phase in self._phases

    def get_delta(self, from_phase: Phase, to_phase: Phase) -> int:
        """
        Return the signed number of steps needed to get from from_phase to
        to_phase.

        Raise LIMARException if the PhaseSystem isn't linear.
        """

        if not self._is_linear:
            raise LIMARException(
                f"Cannot get delta from phase '{from_phase}' to phase"
                f" '{to_phase}': Phase system is not linear"
            )

        return (
            self._phases.index(to_phase)
            - self._phases.index(from_phase)
        )

    def apply_delta(self, from_phase: Phase, delta: int) -> Phase:
        """
        Return the resulting phase from making the given signed number of steps
        starting from from_phase.

        Raise LIMARException if the PhaseSystem isn't linear.
        """

        if not self._is_linear:
            raise LIMARException(
                f"Cannot apply delta ({delta:+}) to phase '{from_phase}':"
                f" Phase system is not linear"
            )

        return self._phases[self._phases.index(from_phase) + delta]

    def can_transition(self, from_phase: Phase, to_phase: Phase):
        return (
            (
                self._is_linear and
                self.get_delta(from_phase, to_phase) == 1
            ) or (
                from_phase in self._phase_jumps and
                to_phase in self._phase_jumps[from_phase]
            )
        )
