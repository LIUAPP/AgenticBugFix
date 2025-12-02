"""Minimal Jira client used by the BugFixer agent."""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from config import JiraConfig
import os
import sys
import json


class JiraError(RuntimeError):
    pass


class JiraClient:
    def __init__(self, config: JiraConfig, session: Optional[requests.Session] = None) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._session.auth = (config.email, config.api_token)
        self._session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    def _url(self, path: str) -> str:
        base = self._config.base_url.rstrip("/")
        return f"{base}/rest/api/3/{path.lstrip('/')}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._session.request(method.upper(), self._url(path), **kwargs)
        if not response.ok:
            raise JiraError(f"Jira API {method} {path} failed: {response.status_code} {response.text}")
        if response.text:
            return response.json()
        return None

    async def fetch_issue(self, issue_key: str, fields:str) -> Dict[str, Any]:
        params = {"fields": fields} if fields else None
        return await self._request("GET", f"issue/{issue_key}", params=params)

    async def add_comment(self, issue_key: str, comment: str) -> Dict[str, Any]:
        payload = {"body": comment}
        return await self._request("POST", f"issue/{issue_key}/comment", json=payload)
    
    def extract_text(self,node):
        """Recursively extract text from ProseMirror-style content structure."""
        if isinstance(node, dict):
            if node.get('type') == 'text':
                return node.get('text', '')
            elif 'content' in node:
                return '\n'.join(self.extract_text(child) for child in node['content'])
        elif isinstance(node, list):
            return '\n'.join(self.extract_text(item) for item in node)
        return ''      
    
    async def fetch_jira(self, jiraNo: str) -> Dict[str, Any]:
        try:
            issue= await self.fetch_issue(jiraNo,"summary,description,customfield_10076")
            
            Jira_json=f"""
{{
    "summary": {issue["fields"]["summary"]},
    "description": {self.extract_text(issue["fields"]["description"])},
    "reproduce procedures": {self.extract_text(issue["fields"]["customfield_10076"])}
}}"""

            # return json.dumps(Jira_json, indent=2, ensure_ascii=False)
            return Jira_json
        except JiraError as exc:
            raise JiraError(f"Failed to fetch Jira issue {jiraNo}: {exc}")

if __name__ == "__main__":

    import os
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()
    issue_key = os.environ.get("JIRA_ISSUE", "AI-5")  # Default issue key
    client = JiraClient(JiraConfig.from_env())

    async def main():
        try:
            issue = await client.fetch_issue(issue_key, "summary,description,customfield_10076")
            Jira_json=f"""
{{
    "summary": {issue["fields"]["summary"]},
    "description": {client.extract_text(issue["fields"]["description"])},
    "reproduce procedures": {client.extract_text(issue["fields"]["customfield_10076"])}
}}"""
            print(Jira_json)
            # print(json.dumps(
            #     {
            #         "key": issue['key'],
            #         "summary": issue['fields']['summary'],
            #         "description": client.extract_text(issue['fields']['description']),
            #         "reproduce procedures": client.extract_text(issue['fields']['customfield_10076'])
            #     },
            #     indent=4,
            #     ensure_ascii=False,
            # ))
        except JiraError as exc:
            print(f"Error: {exc}")
            sys.exit(2)

    asyncio.run(main())