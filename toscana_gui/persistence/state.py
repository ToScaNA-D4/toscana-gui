from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

APP_STATE_FILENAME = "app-state.json"
PROJECT_STATE_FILENAME = "ntsa-project.json"
PARIS_TZ = ZoneInfo("Europe/Paris")

TopLevelTab = Literal[
    "main_menu",
    "project",
    "numors",
    "background",
    "normalization",
    "self",
    "ft",
    "bft",
    "run_history",
    "help",
]
RecentProjectStatus = Literal["ok", "missing", "invalid"]
RunStatus = Literal["pending", "running", "succeeded", "failed"]


@dataclass(slots=True)
class AppPreferences:
    host: str = "localhost"
    port: int = 5006
    auto_show_browser: bool = True


@dataclass(slots=True)
class RecentProjectEntry:
    project_name: str
    project_file: str
    last_opened_at: str
    status: RecentProjectStatus = "ok"
    warning: str | None = None


@dataclass(slots=True)
class AppState:
    schema_version: int = 1
    recent_projects: list[RecentProjectEntry] = field(default_factory=list)
    app_preferences: AppPreferences = field(default_factory=AppPreferences)

    def remember_project(self, entry: RecentProjectEntry, limit: int = 5) -> None:
        remaining = [
            existing
            for existing in self.recent_projects
            if Path(existing.project_file) != Path(entry.project_file)
        ]
        self.recent_projects = [entry, *remaining[: max(limit - 1, 0)]]

    def remove_project(self, project_file: str) -> None:
        target = Path(project_file)
        self.recent_projects = [
            entry
            for entry in self.recent_projects
            if Path(entry.project_file) != target
        ]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AppState:
        raw_preferences = payload.get("app_preferences", {})
        if not isinstance(raw_preferences, dict):
            raw_preferences = {}
        allowed = {"host", "port", "auto_show_browser"}
        preferences = AppPreferences(**{k: raw_preferences[k] for k in raw_preferences if k in allowed})
        recent_projects = [
            RecentProjectEntry(**entry)
            for entry in payload.get("recent_projects", [])
        ]
        return cls(
            schema_version=int(payload.get("schema_version", 1)),
            recent_projects=recent_projects,
            app_preferences=preferences,
        )


@dataclass(slots=True)
class ProjectMetadata:
    name: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ResumeState:
    last_top_level_tab: TopLevelTab = "main_menu"
    has_static_plot_warning: bool = False
    static_plot_warning: str | None = None


@dataclass(slots=True)
class OutputPaths:
    stdout_file: str | None = None
    logfile: str | None = None
    reg_file: str | None = None
    adat_file: str | None = None
    qdat_file: str | None = None
    generated_files: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RunRecord:
    run_id: str
    workflow: str
    status: RunStatus
    started_at: str
    finished_at: str | None = None
    summary: str | None = None
    error: str | None = None
    workflow_data: dict[str, Any] = field(default_factory=dict)
    output_paths: OutputPaths = field(default_factory=OutputPaths)


@dataclass(slots=True)
class ProjectState:
    schema_version: int
    project: ProjectMetadata
    resume: ResumeState = field(default_factory=ResumeState)
    numors: dict[str, Any] = field(default_factory=dict)
    background: dict[str, Any] = field(default_factory=dict)
    runs: list[RunRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProjectState:
        project = ProjectMetadata(**payload["project"])
        resume = ResumeState(**payload.get("resume", {}))
        runs = []
        for record in payload.get("runs", []):
            run_payload = dict(record)
            output_paths = OutputPaths(**run_payload.pop("output_paths", {}))
            runs.append(RunRecord(output_paths=output_paths, **run_payload))

        return cls(
            schema_version=int(payload.get("schema_version", 1)),
            project=project,
            resume=resume,
            numors=dict(payload.get("numors", payload.get("d4creg", {}))),
            background=dict(payload.get("background", {})),
            runs=runs,
        )


def now_iso() -> str:
    return datetime.now(tz=PARIS_TZ).isoformat()


def create_project_state(
    project_name: str,
    *,
    last_top_level_tab: TopLevelTab = "project",
) -> ProjectState:
    timestamp = now_iso()
    return ProjectState(
        schema_version=1,
        project=ProjectMetadata(
            name=project_name,
            created_at=timestamp,
            updated_at=timestamp,
        ),
        resume=ResumeState(last_top_level_tab=last_top_level_tab),
        numors={},
        background={},
        runs=[],
    )


def load_app_state(path: str | Path) -> AppState:
    target = Path(path)
    if not target.exists():
        return AppState()
    payload = json.loads(target.read_text(encoding="utf-8"))
    return AppState.from_dict(payload)


def save_app_state(path: str | Path, state: AppState) -> Path:
    target = Path(path)
    target.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
    return target


def load_project_state(path: str | Path) -> ProjectState:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    return ProjectState.from_dict(payload)


def save_project_state(path: str | Path, state: ProjectState) -> Path:
    target = Path(path)
    target.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
    return target
