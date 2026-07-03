"""
Data Transfer Objects — the contract between services and consumers.

Rules:
- No business logic
- No ORM imports
- All fields must be JSON-serializable primitives
- Use dataclasses.asdict() to serialize for transport
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class EnvStatusDTO:
    id: int
    name: str
    project_name: str
    is_active: bool
    project_path: str
    version: str
    github_url: str
    branch_name: str
    database: Optional[str]
    sh_url: Optional[str]
    modules: list
    last_used_at: Optional[str]


@dataclass
class ProjectStatusDTO:
    project: Optional[str]
    environments: list  # list[EnvStatusDTO]


@dataclass
class EnvDetailDTO:
    """Lightweight env record for lookups and the selector TUI."""
    id: int
    name: str
    project_name: str
    branch_name: str
    database: Optional[str]
    last_used_at: Optional[str]
    version_id: Optional[int]
    version_name: str
    status: str = "active"
    pinned: bool = False


@dataclass
class SwitchResultDTO:
    env_id: int
    env_name: str
    project_name: str
    project_path: str
    version_id: Optional[int]
    version_name: str
    version_path: str
    branch_name: str
    database: Optional[str]
