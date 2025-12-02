"""BugFixer agent orchestration."""
import asyncio
from web_agent import web_search
from rag_client import query_jira_rag
import json
import logging
import os
import uuid
import re
import unicodedata
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import random

from typing import Any, Dict, List, Optional, AsyncGenerator
from openai import OpenAI

from codex_client import CodexCLIError, CodexClient
from config import AgentConfig
from git_client import GitClient
from jira_client import JiraClient

from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT, toolsForBugFix

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

fh = logging.FileHandler("agent.log")
fh.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

MAX_ACTION_PREVIEW = 1200
MAX_PROMPT_CHARS = 1000

load_dotenv()
config = AgentConfig.from_env()
# logoin codex
codex_client = CodexClient(config.codex)
try:
    codex_client.login_codex()
    print("Codex CLI logged in successfully.")
except CodexCLIError as exc:
    logger.error("Failed to login to Codex CLI: %s", exc)
    print("Failed to login to Codex CLI. Check logs for details.")

app = FastAPI(title="AI Agent Demo Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
TOOLNAME_TO_STEP = {
    "fetch_jira": "JiraIntake",
    "pull_repo": "RepoPull",
    "exec_codex": "CodexCLI",
    "web_search": "WebSearch",
    "query_jira_rag": "RAG"
}

class ConversationState:
    def __init__(self) -> None:
        self.active_task: Optional[asyncio.Task] = None


conversations: Dict[str, ConversationState] = {}


def get_conversation_state(conversation_id: str) -> ConversationState:
    state = conversations.get(conversation_id)
    if not state:
        state = ConversationState()
        conversations[conversation_id] = state
    return state


@app.websocket("/ai-agent")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("Client connected from %s", websocket.client)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                command = json.loads(data)
            except json.JSONDecodeError as exc:
                logger.warning("Dropping invalid payload: %s", exc)
                continue

            cmd_type = command.get("type")
            if cmd_type == "user-message":
                await handle_user_message(websocket, command)
            elif cmd_type == "stop-response":
                await handle_stop_request(websocket, command)
            elif cmd_type == "new-session":
                await handle_new_session(command)
            else:
                logger.warning("Unsupported command: %s", cmd_type)
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        await cleanup_connection()


async def handle_user_message(websocket: WebSocket, command: dict) -> None:
    conversation_id = command.get("conversationId")
    prompt = command.get("prompt", "").strip()

    if not conversation_id or not prompt:
        logger.warning("Ignoring incomplete user message: %s", command)
        return

    state = get_conversation_state(conversation_id)
    if state.active_task and not state.active_task.done():
        logger.info("Conversation %s already streaming. Waiting for completion.", conversation_id)
        return

    task = asyncio.create_task(
        stream_agent_response(websocket, conversation_id, prompt),
    )
    state.active_task = task


async def handle_stop_request(websocket: WebSocket, command: dict) -> None:
    conversation_id = command.get("conversationId")
    if not conversation_id:
        return

    state = get_conversation_state(conversation_id)
    if state.active_task and not state.active_task.done():
        logger.info("Stopping response for conversation %s", conversation_id)
        state.active_task.cancel()
        try:
            await state.active_task
        except asyncio.CancelledError:
            await send_event(
                websocket,
                conversationId=conversation_id,
                responseId=command.get("responseId", "unknown"),
                type="response-stop",
                status="stopped",
            )
        finally:
            state.active_task = None


async def handle_new_session(command: dict) -> None:
    conversation_id = command.get("conversationId")
    if not conversation_id:
        return

    state = conversations.pop(conversation_id, None)
    if state and state.active_task and not state.active_task.done():
        state.active_task.cancel()
    logger.info("Started fresh session for %s", conversation_id)


async def stream_agent_response(
    websocket: WebSocket,
    conversation_id: str,
    prompt: str,
) -> None:
    print("Starting agent run loop for prompt:", prompt)
    
    bugFixerAgent = BugFixerAgent(config, websocket, conversation_id)
    
    try:
         await bugFixerAgent.run(prompt)
    except asyncio.CancelledError:
        await send_event(
            websocket,
            conversationId=conversation_id,
            responseId=bugFixerAgent._response_id,
            type="response-stop",
            status="stopped",
        )
        raise
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("Agent failed to process prompt")
        await send_event(
            websocket,
            conversationId=conversation_id,
            responseId=bugFixerAgent._response_id,
            type="response-error",
            status="error",
            metadata={"detail": str(exc)},
        )
    finally:
        state = conversations.get(conversation_id)
        if state:
            state.active_task = None


async def send_event(websocket: WebSocket, **payload: object) -> None:
    await websocket.send_text(json.dumps(payload))


async def cleanup_connection() -> None:
    for state in conversations.values():
        if state.active_task and not state.active_task.done():
            state.active_task.cancel()
    conversations.clear()
    
class AgentProtocolError(RuntimeError):
    pass

class BugFixerAgent:
    def __init__(self, config: AgentConfig, websocket: WebSocket, conversation_id: str) -> None:
        self._config = config
        self._openai = OpenAI(api_key=config.openai.api_key)
        self._codex = CodexClient(config.codex)
        self._git = GitClient(config.git)
        self._jira = JiraClient(config.jira)
        self._conversation: List[Dict[str, str]] = []
        self._current_issue_key: Optional[str] = None
        self._websocket = websocket
        self._conversation_id = conversation_id
        self._response_id = str(uuid.uuid4())
        self.fetch_jira = self._jira.fetch_jira
        self.pull_repo = self._git.pull
        self.exec_codex = self._codex.exec_codex
        self.web_search = web_search
        self.query_jira_rag = query_jira_rag    
        self._step = ""
        self._step_Responses: List[str] = []
        self._step_Done = False

    async def run(self, prompt: str):
        """Run the triage→reproduce→fix loop until exit or iteration limit."""
        print("Running BugFixerAgent with prompt:", prompt)
        # Sanitize user prompt
        clean_prompt = unicodedata.normalize("NFKC", prompt or "")
        clean_prompt = clean_prompt.replace("\r\n", "\n").replace("\r", "\n")
        # Remove control chars except tab/newline
        clean_prompt = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", clean_prompt)
        clean_prompt = clean_prompt.strip()

        if len(clean_prompt) > MAX_PROMPT_CHARS:
            logger.warning("User prompt exceeded max chars (%d); truncating.", MAX_PROMPT_CHARS)
            clean_prompt = clean_prompt[:MAX_PROMPT_CHARS]

        if not clean_prompt:
            await send_event(
                self._websocket,
                conversationId=self._conversation_id,
                responseId=self._response_id,
                type="response-error",
                status="error",
                metadata={"detail": "Empty or invalid prompt after sanitization."},
            )
            return
        
        prompt = clean_prompt
        
        # Notify client of response start
        self._step = "JiraIntake"
        self._step_Responses = []
        await send_event(
            self._websocket,
            conversationId=self._conversation_id,
            responseId=self._response_id,
            type="response-start",
            status="thinking",
            metadata={"promptPreview": prompt[:140]},
        )
        
        self._conversation = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        history: List[Dict[str, Any]] = []

        for iteration in range(self._config.max_iterations):
            logger.info("Agent iteration %s for %s", iteration + 1, prompt)
            print("Agent iteration", iteration + 1, "for prompt:", prompt)
            model_reply = await self._call_model()
            logger.info("Model reply: %s", model_reply)
            self._step_Responses = []
            self._step_Done = False
            try:
                if model_reply.content:
                    step_payload = self._parse_step_payload(model_reply.content)
                    # Append to history and conversation
                    history.append(step_payload)
                    
                    # Notify client of step start
                    stepStartResponse = "iteration:" + str(iteration + 1) + " Step: " + step_payload.get("step", "") + " Reasoning: "  + step_payload.get("reasoning", "")
                    logger.info("Agent Step started: %s", stepStartResponse)
                    print("Agent Step started:", stepStartResponse)
                    
                    self._step = step_payload.get("step", "")
                    if (self._step == "Summary"):
                        self._response_id = str(uuid.uuid4())
                        await send_event(
                            self._websocket,
                            conversationId=self._conversation_id,
                            responseId=self._response_id,
                            type="response-start",
                            status="thinking",
                            metadata={"promptPreview": stepStartResponse},
                        )                   
                    else:
                        # JiraIntake rejected responsed and ERROR step responses
                        async for token in self._stream_response(stepStartResponse):
                            self._step_Responses.append(token)
                            await send_event(
                                self._websocket,
                                conversationId=self._conversation_id,
                                responseId=self._response_id,
                                type="response-token",
                                status="streaming",
                                token = token,
                            )
                        self._step_Responses.append("\n")
                        # Notify client step is compeleted.
                        print("Agent Step completed:", "".join(self._step_Responses))
                        await send_event(
                            self._websocket,
                            conversationId=self._conversation_id,
                            responseId=self._response_id,
                            type="response-end",
                            status="completed",
                            content=step_payload.get("reasoning", "")
                        )
                        self._step_Done = True
                        break
                        
            except AgentProtocolError as exc:
                logger.warning("Bad payload: %s", exc)
                self._conversation.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was invalid JSON. "
                            "Respond with a single JSON object that follows the Output Schema."
                        ),
                    }
                )
                continue
            
            # Handle tool calls and feed results back to the model
            if getattr(model_reply, "tool_calls", None):
                # Append the assistant message that requested tools
                self._conversation.append(
                    {
                        "role": "assistant",
                        "content": model_reply.content or "",
                        "tool_calls": self._to_tool_calls_payload(model_reply),
                    }
                )

                # Execute tool calls
                for tc in model_reply.tool_calls:
                    await self._execute_tool_call(tc)
                
                # Notify client step is compeleted.
                print("Agent Step completed:", "".join(self._step_Responses))
                await send_event(
                    self._websocket,
                    conversationId=self._conversation_id,
                    responseId=self._response_id,
                    type="response-end",
                    status="completed",
                    content="".join(self._step_Responses),
                )
                self._step_Done = True
            else:
                self._conversation.append({"role": "assistant", "content": json.dumps(step_payload)})
    
                # Check for exit condition
                if step_payload.get("step") == "Summary":
                    # Stream summary reasoning to client
                    summary_message = "AI Agent has completed all steps, bug has been fixed. Summary: \n\n" + step_payload.get("reasoning", "")
                    async for token in self._stream_response(summary_message):
                        self._step_Responses.append(token)
                        await send_event(
                            self._websocket,
                            conversationId=self._conversation_id,
                            responseId=self._response_id,
                            type="response-token",
                            status="streaming",
                            token = token,
                        )

                    # Notify client step is compeleted.
                    print( "".join(self._step_Responses).strip())
                    await send_event(
                        self._websocket,
                        conversationId=self._conversation_id,
                        responseId=self._response_id,
                        type="response-end",
                        status="completed",
                        content="".join(self._step_Responses).strip(),
                    )
                    self._step_Done = True
                    
                    # Send celebration event
                    await send_event(
                        self._websocket,
                        conversationId=self._conversation_id,
                        responseId=self._response_id,
                        type="response-celebration",
                        status="celebrating",
                        metadata={"celebration": "fireworks"},
                    )

                    # exit the agent loop
                    break

        if (iteration == self._config.max_iterations - 1):
            # Notify client that max iterations reached without completion
            warning_message = f"Agent reached maximum iterations ({self._config.max_iterations}) without completing the task."
            logger.info(warning_message)
            if (self._step_Done):
                self._response_id = str(uuid.uuid4())
            await send_event(
                self._websocket,
                conversationId=self._conversation_id,
                responseId=self._response_id,
                type="response-end",
                status="completed",
                content=warning_message,
            )
        return

    async def _call_model(self) -> str:
        logger.info("Calling model with conversation: %s", self._conversation)
        response = self._openai.chat.completions.create(
            model=self._config.openai.model,
            messages=self._conversation,
            tools=toolsForBugFix,
            temperature=self._config.openai.temperature,
        )
        choice = response.choices[0].message
        return choice or "{}"

    def _parse_step_payload(self, content: str) -> Dict[str, Any]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AgentProtocolError(f"Model response is not valid JSON: {exc}") from exc

        if "step" not in payload:
            raise AgentProtocolError("Payload missing 'step' field.")
        return payload
    
    def _to_tool_calls_payload(self,reply) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []
        for tc in getattr(reply, "tool_calls", []) or []:
            func = getattr(tc, "function", None)
            payloads.append(
                {
                    "id": getattr(tc, "id", ""),
                    "type": getattr(tc, "type", "function"),
                    "function": {
                        "name": getattr(func, "name", ""),
                        "arguments": getattr(func, "arguments", "") or "{}",
                    },
                }
            )
        return payloads
    
    async def _execute_tool_call(self,tc) -> None:
        name = getattr(tc.function, "name", "")
        raw_args = getattr(tc.function, "arguments", "") or "{}"
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {"_raw": raw_args}

        # Tool calls present, content is None, notify client about tool calls
        self._step = TOOLNAME_TO_STEP.get(name, "")
        if (self._step == "CodexCLI"):
            prompt = args.get('prompt','')
            print(f"Model requested tool calls: tool: {name}, prompt: \n {prompt}")
            # Notify client of step start
            stepStartResponse = f"Model requested tool calls: tool: {name}, prompt: \n {prompt}"
        else:
            print(f"Model requested tool calls: tool: {name}, args: \n {json.dumps(args, indent=4, ensure_ascii=False)}")
            # Notify client of step start
            stepStartResponse = f"Model requested tool calls: tool: {name}, args: \n {json.dumps(args, indent=4, ensure_ascii=False)}"
        
        if (self._step != "JiraIntake"):
            self._response_id = str(uuid.uuid4())
            await send_event(
                self._websocket,
                conversationId=self._conversation_id,
                responseId=self._response_id,
                type="response-start",
                status="thinking",
                metadata={"promptPreview": stepStartResponse},
            )
            async for token in self._stream_response(stepStartResponse):
                self._step_Responses.append(token)
                await send_event(
                    self._websocket,
                    conversationId=self._conversation_id,
                    responseId=self._response_id,
                    type="response-token",
                    status="streaming",
                    token = token,
                )
            self._step_Responses.append("\n")
        else:
            async for token in self._stream_response(stepStartResponse):
                self._step_Responses.append(token)
                await send_event(
                    self._websocket,
                    conversationId=self._conversation_id,
                    responseId=self._response_id,
                    type="response-token",
                    status="streaming",
                    token = token,
                )
            self._step_Responses.append("\n")
        
        try:
            handler = getattr(self, f"tool_{name}", None) or getattr(self, name, None)
            if callable(handler):
                maybe = handler(**args)
                result = await maybe if asyncio.iscoroutine(maybe) else maybe
            else:
                call_method = getattr(self, "call_tool", None)
                if callable(call_method):
                    maybe = call_method(name, args)
                    result = await maybe if asyncio.iscoroutine(maybe) else maybe
                else:
                    result_obj = {"error": f"No tool handler found for {name}"}
        except Exception as exc:
            result = "error:" + str(exc)

        if (result is None):
            content = "No result returned."
        else:
            content = result
        if len(content) > MAX_ACTION_PREVIEW:
            content = content[:MAX_ACTION_PREVIEW] + "...[truncated]"
        self._conversation.append(
            {
                "role": "tool",
                "tool_call_id": getattr(tc, "id", ""),
                "content": content,
            }
        )
        
        # Notify client of tool call result
        toolResponse = f"\n\n Tool {name}, result:\n {content}"
        async for token in self._stream_response(toolResponse):
            self._step_Responses.append(token)
            await send_event(
                self._websocket,
                conversationId=self._conversation_id,
                responseId=self._response_id,
                type="response-token",
                status="streaming",
                token = token,
            )

    async def _stream_response(self, response: str) -> AsyncGenerator[str, None]:
        """Yield tokens with slight delay to simulate an AI response."""
        for token in response.split(" "):
            await asyncio.sleep(self._next_delay())
            yield f"{token} "

    def _next_delay(self) -> float:
        return max(0.02, random.gauss(0.08, 0.04))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)