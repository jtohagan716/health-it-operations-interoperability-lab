from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class IncidentState(str, Enum):
    CREATED = "CREATED"
    PREPARED = "PREPARED"
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLEANED = "CLEANED"


@dataclass
class IncidentArtifact:
    path: Path
    artifact_type: str
    description: str


@dataclass
class OwnedResource:
    resource_type: str
    identifier: str
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class IncidentCase:
    incident_id: str
    scenario_id: str
    title: str
    protocols: tuple[str, ...]
    symptom: str
    case_key: str
    workspace: Path

    state: IncidentState = IncidentState.CREATED

    artifacts: list[IncidentArtifact] = field(
        default_factory=list
    )

    owned_resources: list[OwnedResource] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def register_artifact(
        self,
        path: Path,
        artifact_type: str,
        description: str,
    ) -> None:
        self.artifacts.append(
            IncidentArtifact(
                path=path,
                artifact_type=artifact_type,
                description=description,
            )
        )

    def register_owned_resource(
        self,
        resource_type: str,
        identifier: str,
        **metadata: Any,
    ) -> None:
        self.owned_resources.append(
            OwnedResource(
                resource_type=resource_type,
                identifier=identifier,
                metadata=metadata,
            )
        )

    def set_state(
        self,
        state: IncidentState,
    ) -> None:
        self.state = state
