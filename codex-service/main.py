import asyncio
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

app = FastAPI()

class LoginRequest(BaseModel):
    api_key: str

class ExecRequest(BaseModel):
    prompt: str
    project_path: str = "."

async def run_command(cmd: list, cwd: str, input_text: str = None):
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate(
            input=input_text.encode() if input_text else None
        )
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Command failed: {err.decode()}")
        return out.decode()
    except FileNotFoundError:
        # Fallback for when 'codex' binary is not found (e.g. during development/testing without the tool)
        return f"Simulated output for: {' '.join(cmd)}"

@app.post("/login")
async def login(request: LoginRequest):
    cmd = ["codex", "login", "--with-api-key"]
    # We don't really need a specific CWD for login, but we'll use root or app
    output = await run_command(cmd, cwd="/app", input_text=request.api_key)
    return {"output": output}

@app.post("/exec")
async def execute(request: ExecRequest):
    cmd = ["codex", "exec", request.prompt, "--full-auto"]
    # Ensure the project path exists or use a default
    cwd = request.project_path if os.path.exists(request.project_path) else "/app"
    output = await run_command(cmd, cwd=cwd)
    return {"output": output}
