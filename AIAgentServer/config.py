from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

class ConfigError(RuntimeError):
    """Raised when a required configuration value is missing or invalid."""


def _require(name: str, value: Optional[str]) -> str:
    if value:
        return value
    raise ConfigError(f"Missing required configuration value: {name}")


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str = "gpt-5"
    temperature: float = 0.4

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        return cls(
            api_key=_require("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
            model=os.getenv("OPENAI_MODEL", cls.model),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", cls.temperature)),
        )


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    api_token: str
    email: str

    @classmethod
    def from_env(cls) -> "JiraConfig":
        return cls(
            base_url=_require("JIRA_BASE_URL", os.getenv("JIRA_BASE_URL")),
            api_token=_require("JIRA_API_TOKEN", os.getenv("JIRA_API_TOKEN")),
            email=_require("JIRA_EMAIL", os.getenv("JIRA_EMAIL")),
        )


@dataclass(frozen=True)
class CodexConfig:
    api_key: str
    binary_path: str = "codex"
    project_path: str = "."

    @classmethod
    def from_env(cls) -> "CodexConfig":
        return cls(
            binary_path=os.getenv("CODEX_BIN", cls.binary_path),
            project_path=os.getenv("GIT_REPO_ROOT", cls.project_path),
            api_key=_require("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
        )


@dataclass(frozen=True)
class GitConfig:
    repo_root: Path = field(default_factory=lambda: Path.cwd())
    default_branch: str = "main"

    @classmethod
    def from_env(cls) -> "GitConfig":
        # Use environment value if present, otherwise fall back to the
        # dataclass default (current working directory). We can't reference
        # `cls.repo_root` directly because the default is provided via
        # `default_factory` and not stored as a class attribute.
        default_root = Path.cwd()
        env_root = os.getenv("GIT_REPO_ROOT")
        repo_root = Path(env_root) if env_root else default_root
        return cls(
            repo_root=repo_root,
            default_branch=os.getenv("GIT_DEFAULT_BRANCH", cls.default_branch),
        )


@dataclass(frozen=True)
class AgentConfig:
    openai: OpenAIConfig
    jira: JiraConfig
    codex: CodexConfig
    git: GitConfig
    max_iterations: int = 12

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            openai=OpenAIConfig.from_env(),
            jira=JiraConfig.from_env(),
            codex=CodexConfig.from_env(),
            git=GitConfig.from_env(),
            max_iterations=int(os.getenv("BUGFIX_AGENT_MAX_ITERS", cls.max_iterations)),
        )

