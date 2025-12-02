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

    async def _request(self, endpoint: str, json_data: dict) -> str:
        """Helper to send requests to the Codex service."""
        # Assuming the codex service is available at http://codex:8000
        # You might want to move the URL to config
        url = f"http://codex:8000/{endpoint}"
        
        # We use aiohttp or requests. Since this is async, aiohttp is better, 
        # but to keep dependencies simple if not already using aiohttp, we can use requests in a thread or just requests if blocking is acceptable (it's not ideal for async).
        # However, looking at agent.py, it uses openai async client.
        # Let's use httpx or aiohttp if available. 
        # For now, I'll use standard requests wrapped in asyncio.to_thread to avoid blocking the loop,
        # or just use requests directly if we assume low concurrency.
        # Better: use httpx.
        
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=json_data, timeout=60.0)
            if resp.status_code != 200:
                raise CodexCLIError(f"Codex service failed: {resp.text}")
            return resp.json().get("output", "")

    async def login_codex(self):
        api_key = self._config.api_key
        print("🔐 Logging into Codex service...")
        output = await self._request("login", {"api_key": api_key})
        print("✅ Login successful!\n", output)

    async def exec_codex(self, prompt: str) -> str:
        print(f"🧠 Running Codex prompt via service: {prompt}")
        # The code is mounted at /app/code in the codex container
        output = await self._request("exec", {"prompt": prompt, "project_path": "/app/code"})
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


