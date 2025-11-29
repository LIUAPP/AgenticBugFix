"""Git command helpers used by the BugFixer agent."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

from config import GitConfig


class GitCommandError(RuntimeError):
    pass


class GitClient:
    def __init__(self, config: GitConfig) -> None:
        self._config = config

    @property
    def repo_root(self) -> Path:
        return self._config.repo_root

    def _run(
        self,
        args: Iterable[str],
        *,
        check: bool = True,
        capture_output: bool = True,
        text: bool = True,
        input_text: Optional[str] = None,
    ) -> subprocess.CompletedProcess[str]:

        command: List[str] = ["git", *args]
        result = subprocess.run(
            command,
            cwd=self.repo_root,
            check=False,
            capture_output=capture_output,
            text=text,
            input=input_text,
        )
        if check and result.returncode != 0:
            raise GitCommandError(
                f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
            )
        return result

    async def pull(self,repo: str) -> str:
        output = self._run(["init"]).stdout.strip()
        self._run(["branch", "-M", "main"])
        tempOutput = (self._run(["remote", "-v"])).stdout.strip()
        if (tempOutput.find("origin") != -1):
            self._run(["remote", "remove", "origin"])
        self._run(["remote", "add", "origin", repo])
        self._run(["pull", "origin", "main"])
        output = output + "\n Successfully pulled the source code from " + repo
        return output

    async def apply_patch(self, patch_text: str) -> str:
        result = await self._run(["apply", "-"], input_text=patch_text)
        return result.stdout.strip()

    async def diff(self, staged: bool = False) -> str:
        args = ["diff"]
        if staged:
            args.append("--staged")
        return (await self._run(args)).stdout

    async def commit(self, message: str) -> str:
        return (await self._run(["commit", "-am", message])).stdout.strip()

if __name__ == "__main__":
    git = GitClient(GitConfig.from_env())
    print(git.repo_root)
    print(asyncio.run(git.pull("https://github.com/LIUAPP/issue1.git")))