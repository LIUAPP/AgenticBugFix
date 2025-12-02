"""Thin wrapper around the Codex CLI."""
import asyncio
import os
import subprocess
from typing import List, Optional
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

    async def _run(self, cmd: List[str], input_text: Optional[str] = None) -> str:
        """Run a Codex CLI command asynchronously."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self._config.project_path,  # ← set working directory
            stdin=asyncio.subprocess.PIPE, 
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate(
            input=input_text.encode() if input_text else None 
        ) 
        if proc.returncode != 0:
            raise CodexCLIError(f"Codex CLI command {' '.join(cmd)} failed: {err.decode()}")
        
        return(out.decode())


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
    
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    import asyncio

    codex_config = CodexConfig.from_env()
    codex_client = CodexClient(codex_config)
    asyncio.run(codex_client.login_codex())
    prompt = "Fix the bug in the code"
    asyncio.run(codex_client.exec_codex(prompt))


