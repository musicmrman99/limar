from argparse import Namespace

from core.exceptions import VCSException

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
            is_linear: bool = True,
    ):
        self._name = name
        self._phases = phases

        self._phase_jumps = {}
        if phase_jumps is not None:
            self._phase_jumps = phase_jumps

        self._is_linear = is_linear

        # For user convenience
        self.PHASES = Namespace(**{name: name for name in phases})

    # Getters

    def name(self) -> str:
        return self._name

    # Queries

    def has_phase(self, phase: str) -> bool:
        return phase in self._phases

    def get_delta(self, from_phase: Phase, to_phase: Phase) -> int:
        """
        Return the signed number of steps needed to get from from_phase to
        to_phase.

        Raise VCSException if the PhaseSystem isn't linear.
        """

        if not self._is_linear:
            raise VCSException(
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

        Raise VCSException if the PhaseSystem isn't linear.
        """

        if not self._is_linear:
            raise VCSException(
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
