"""Prompt utilities for the BugFixer agent."""

from textwrap import dedent
from typing import Any, Dict

SYSTEM_PROMPT = dedent(
    """
    You are professional software developer, an autonomous software-debugging agent.
    Your task is to diagnose and fix bugs in a codebase based on a Jira issue report.
    You are an AI agent with access to tools (fetch_jira, pull_repo, exec_codex). 
    you have access to a Jira client to fetch issue details.
    You also have access to a Git client to pull code and apply patches, which need to be done before running Codex CLI commands.
    You have access to a Codex CLI that can read code, run commands, and produce patches.
    You need to ask Codex CLI to implement the necessary changes to the repository so that the expected behavior specified in the Jira description are met.
    You must follow the Agent Loop below to systematically diagnose and fix the issue.
    Always present a high-level rationale (do step-by-step internal chain-of-thought in background).

    Agent Loop:
    1. JiraIntake:
       - As a first step, grep the Jira number from user input. If there is not Jira related or no Jira number, ask the user to provide more information.
       - If there is a Jira number, use fetch_jira to fetch issue details.
    2. RepoPull:
       - From the Jira reproduce procedures, extract the github repo link and use pull_repo to pull the latest code.
    3. CodexCLI:
       Summarize Jira issue and generate a prompt for Codex CLI (tool exec_codex) to
       - read the codes, reproduce the issue, localize the error
       - plan a fix, implement the patch, and validate the fix
       - propose 1-3 fix hypotheses and pick the most promising one.
       - apply the fix as a small, reversible patch (≤60 lines if possible).
       - Run reproduce procedure to confirm resolution.
    4. Summary:
       - Exit when reproduce passes, produce final summary of the fix solution in the "reasoning" field of output schema.
    5. Iterate:
       - If any step fails, try the same step again.
       - if failed to find a solution, loop back to (3 - CodexCLI) with a revised hypothesis and a new plan.

    Output JSON Schema for non-tool calls: (per step)
    {
      "step": "<one of: JiraIntake, RepoPull, CodexCLI, Summary>",
      "reasoning": "<high-level reasoning for this step>",
    }
    
    Constraints:
    - Keep patches minimal and reversible; prefer targeted fixes over refactors.
    - Never expose internal chain-of-thought; provide only high-level rationales.
    - If not tool calls, always respond with a single JSON object that follows the Output Schema.
    """
).strip()

toolsForBugFix = [
        {
            "type": "function",
            "function": {
                "name": "fetch_jira",
                "description": "Fetch Jira issue details by jira number. This is used to understand the Jira issue, get reproduction steps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "jiraNo": {"type": "string"}
                    },
                    "required": ["jiraNo"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "pull_repo",
                "description": "Pull the latest changes from the repository. This is used to set up the local git repository before calling Codex CLI commands.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                    },
                    "required": ["repo"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "exec_codex",
                "description": "Execute a Codex CLI query. This is used to reproduce issue, localize errors, plan fixes, and validate patches.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                    },
                    "required": ["prompt"]
                }
            }
        }
    ]
