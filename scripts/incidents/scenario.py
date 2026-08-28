from __future__ import annotations

from abc import ABC, abstractmethod

from scripts.incidents.models import IncidentCase


class IncidentScenario(ABC):
    """
    Protocol-neutral contract for a reproducible
    interoperability incident scenario.
    """

    @abstractmethod
    def create_case(self) -> IncidentCase:
        """
        Create a new isolated incident case with
        unique identifiers and workspace metadata.
        """
        raise NotImplementedError

    @abstractmethod
    def prepare(
        self,
        case: IncidentCase,
    ) -> None:
        """
        Create the source-controlled or generated
        artifacts required to execute the scenario.

        Preparation should not yet expose the root cause
        to the operator-facing incident report.
        """
        raise NotImplementedError

    @abstractmethod
    def activate(
        self,
        case: IncidentCase,
    ) -> None:
        """
        Execute the workflow that produces the controlled
        operational symptom.

        This may involve real protocol transport,
        persistence, downstream systems, or reconciliation.
        """
        raise NotImplementedError

    @abstractmethod
    def cleanup(
        self,
        case: IncidentCase,
    ) -> None:
        """
        Remove only resources explicitly registered as
        owned by this incident case.
        """
        raise NotImplementedError
