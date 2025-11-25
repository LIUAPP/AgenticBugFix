# IRIS Commuter (py-app)

Small helper to send ObjectScript class files to an InterSystems IRIS instance using the Atelier REST API and optionally request compilation.

Features
- Save a .cls file to IRIS via Atelier PUT /api/atelier/<version>/<namespace>/doc/<name>
- Request compilation via POST /api/atelier/<version>/<namespace>/action/compile
- CLI supports separate operations: send-only, compile-only, or send-and-compile

Requirements
- Python 3.8+
- requests (pip install requests)

Environment variables
- IRIS_URL: base URL of the IRIS HTTP service (default: http://localhost:32773)
- IRIS_USER: basic-auth username (default: superuser)
- IRIS_PASSWORD: basic-auth password (default: fountain)
- IRIS_ATELIER_VERSION: Atelier API version (default: v1)
- IRIS_NAMESPACE: target namespace (default: USER)
- CLASS_FILE: default class file path used when CLI file arg is omitted

Usage examples (PowerShell)

# Send then compile (default)
$env:IRIS_URL='http://localhost:32773'; $env:IRIS_USER='superuser'; $env:IRIS_PASSWORD='fountain'
python .\iris-commuter.py .\TestCode.FromPythonCommuter.cls

# Send only
python .\iris-commuter.py .\TestCode.FromPythonCommuter.cls --send

# Compile only (document already present on server)
python .\iris-commuter.py .\TestCode.FromPythonCommuter.cls --compile --name TestCode.FromPythonCommuter.cls

Notes and troubleshooting
- The document name used for compilation must match how the server stores the class (e.g. 'My.Namespace.Class.cls'). If you get a 5351 "Class does not exist" error, ensure the class declaration inside the .cls matches the document name and namespace.
- Some Atelier endpoints accept PUT as raw text, others expect a JSON document object {"enc": false, "content": ["line1","line2",...]}. This script uses the JSON object form for compatibility.
- If authentication differs in your deployment (token, cookies), update the session auth in the script.

Extension ideas
- Auto-derive document name from class declaration inside .cls
- Support for multipart/binary uploads for non-text documents
- Health check / wait-for-IRIS before sending

License: MIT

## Agentic tool integration

This project exposes a small importable helper module `iris_agent_tools.py` that wraps the programmatic API in `iris-commuter.py`. It's intended for use by automation, bots, or agentic tools that need to programmatically send and compile ObjectScript classes.

Provided functions (import from `py-app/iris_agent_tools`):

- `create_commuter(url=None, user=None, password=None)`
	- Returns an `IrisCommuter` configured to talk to the target IRIS instance. Uses environment defaults when arguments are omitted.
- `import_class_file(commuter, path)`
	- Imports (PUT) the file at `path` to the IRIS Atelier documents. Returns a dict: `{ 'ok': bool, 'status_code': int, 'response': parsed_json_or_text, 'docname': str }`.
- `compile_document_name(commuter, docname)`
	- Requests compilation for a document currently on the server. Returns `{ 'ok': bool, 'status_code': int, 'response': parsed_json_or_text }`.
- `send_and_compile_file(commuter, path)`
	- Convenience helper that imports then compiles the given file. Returns `{ 'import': {...}, 'compile': {...} }`.

Example usage from Python (agent code):

```python
from iris_agent_tools import create_commuter, import_class_file, compile_document_name, send_and_compile_file

# Create commuter (optional override of environment variables)
commuter = create_commuter(url='http://localhost:32773', user='superuser', password='fountain')

# Import only
result = import_class_file(commuter, './TestCode.FromPythonCommuter.cls')
print(result)

# Compile only (document name already on server)
comp = compile_document_name(commuter, 'TestCode.FromPythonCommuter.cls')
print(comp)

# Send then compile
combined = send_and_compile_file(commuter, './TestCode.FromPythonCommuter.cls')
print(combined)
```

PowerShell example (calling the Python module from a runner):

```powershell
#$env:IRIS_URL='http://localhost:32773'; $env:IRIS_USER='superuser'; $env:IRIS_PASSWORD='fountain'
#python -c "from iris_agent_tools import create_commuter, send_and_compile_file; c=create_commuter(); print(send_and_compile_file(c, './TestCode.FromPythonCommuter.cls'))"
```

Notes for agent integrators
- The helper returns plain Python dicts and does not raise on HTTP errors — your agent should inspect the `ok` and `status_code` fields.
- `docname` in the responses is the filename used on the server; pass that to the compile call if you request compile-only actions.
- If your orchestration prefers JSON-over-stdout, the Python agent can easily `print(json.dumps(result))` to surface structured results.



