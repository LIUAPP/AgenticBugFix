"""Thin wrapper around the Codex CLI."""

import os
import subprocess
from dotenv import load_dotenv

# 1️⃣ Load .env so OPENAI_API_KEY is available
load_dotenv()

from config import CodexConfig

class CodexCLIError(RuntimeError):
    """Raised when the Codex CLI returns a non-zero exit status."""
    pass

class CodexClient:
    def __init__(self, config: CodexConfig) -> None:
        self._config = config

    async def _run(self, cmd, input_text=None):
        result = subprocess.run(
            cmd,
            cwd=self._config.project_path,
            input=input_text,          # send stdin if needed
            text=True,
            capture_output=True,
            env=os.environ,
        )
        if result.returncode != 0:
            print("❌ Error running:", " ".join(cmd))
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            raise subprocess.CalledProcessError(result.returncode, cmd)
        return result.stdout.strip()

    async def login_codex(self):
        api_key = self._config.api_key
        print("🔐 Logging into Codex CLI using piped API key…")
        # Equivalent of: printenv OPENAI_API_KEY | codex login --with-api-key
        cmd = ["codex", "login", "--with-api-key"]
        output = await self._run(cmd, input_text=api_key)
        print("✅ Login successful!\n", output)

    async def exec_codex(self,prompt:str) -> str:
        print(f"🧠 Running Codex CLI prompt: {prompt}")
        cmd = ["codex", "exec", prompt, "--full-auto"]
        output = await self._run(cmd)
        print("📝 Codex output:\n", output)
        return output
    
    

