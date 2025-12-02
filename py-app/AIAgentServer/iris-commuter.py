# intersystems iris connection
# using iris attelier api
# sending code using rest account instead of iris native api
import requests
import json
import time
import os
from dataclasses import dataclass
from typing import Optional

# Basic configuration from environment (override as needed)
IRIS_URL = os.getenv("IRIS_URL", "http://localhost:32773")
IRIS_USER = os.getenv("IRIS_USER", "superuser")
IRIS_PASSWORD = os.getenv("IRIS_PASSWORD", "fountain")

# Atelier API configuration
# The official Atelier endpoints (from the provided spec) use the pattern:
#   <IRIS_URL>/api/atelier/<version>/<namespace>/doc/<pDocName>    (PUT to save)
#   <IRIS_URL>/api/atelier/<version>/<namespace>/action/compile    (POST to compile)
IRIS_ATELIER_VERSION = os.getenv("IRIS_ATELIER_VERSION", "v1")
IRIS_NAMESPACE = os.getenv("IRIS_NAMESPACE", "USER")


def _doc_put_url(base: str, version: str, namespace: str, docname: str) -> str:
	# docname may contain characters that require safe quoting; requests will handle it
	return f"{base}/api/atelier/{version}/{namespace}/doc/{docname}"


def _compile_url(base: str, version: str, namespace: str) -> str:
	return f"{base}/api/atelier/{version}/{namespace}/action/compile"


@dataclass
class IrisClass:
	"""Representation of an InterSystems IRIS ObjectScript class to send/compile.

	Attributes:
		full_name: fully-qualified class name, e.g. 'TestNameSpace.TestCode.Run'
		source: full class source code as a string
		filename: optional filename to present to the server
	"""
	full_name: str
	source: str
	filename: Optional[str] = None

	@staticmethod
	def from_file(path: str, full_name: Optional[str] = None) -> "IrisClass":
		"""Load class source from a local file. Optionally provide the class full name."""
		with open(path, "r", encoding="utf-8") as f:
			src = f.read()
		name = full_name or os.path.splitext(os.path.basename(path))[0]
		return IrisClass(full_name=name, source=src, filename=os.path.basename(path))

	def to_payload(self) -> dict:
		"""Return a JSON-serializable payload suitable for a REST import/compile API.

		The exact shape may need adjusting depending on your IRIS REST endpoint.
		"""
		payload = {
			"className": self.full_name,
			"source": self.source,
		}
		if self.filename:
			payload["filename"] = self.filename
		return payload


class IrisCommuter:
	"""Helper to send class sources to an IRIS instance and request compilation.

	Assumptions:
	  - The IRIS instance exposes REST endpoints for source upload and compile.
	  - Endpoints are set in IRIS_SOURCE_ENDPOINT and IRIS_COMPILE_ENDPOINT.
	"""

	def __init__(self, url: str = IRIS_URL, user: str = IRIS_USER, password: str = IRIS_PASSWORD,
				 timeout: int = 30):
		self.url = url
		self.session = requests.Session()
		self.session.auth = (user, password)
		self.session.headers.update({"Accept": "application/json"})
		self.timeout = timeout

	def send_class(self, cls: IrisClass) -> requests.Response:
		"""Save the class source to the Atelier document API using PUT.

		The Atelier API expects text/plain content for text documents. We PUT the
		raw class source to the doc endpoint. Returns the Response object.
		"""
		# Best-effort: try to delete any existing document with the same name
		# before PUTing the new content. Deletion is non-fatal; a 404 is OK.
		self.delete_document(cls.filename or cls.full_name)

		# Many Atelier servers accept a JSON document object for PUT. Build the
		# object with enc=false and content as an array of lines.
		docname = cls.filename or cls.full_name
		url = _doc_put_url(self.url, IRIS_ATELIER_VERSION, IRIS_NAMESPACE, docname)
		lines = cls.source.splitlines()
		payload = {"enc": False, "content": lines}
		headers = {"Content-Type": "application/json"}
		resp = self.session.put(url, data=json.dumps(payload), headers=headers, timeout=self.timeout)
		return resp

	def import_class(self, cls: IrisClass) -> requests.Response:
		"""Import (save) the class source into IRIS storage.

		This is a clearer public name for clients: it saves the document to the
		Atelier document API. Returns the requests.Response object.
		"""
		return self.send_class(cls)

	def compile_class(self, class_name: str, wait: bool = True, retries: int = 3, delay: float = 1.0) -> requests.Response:
		"""Request compilation of class `class_name`.

		If `wait` is True this will retry on transient errors up to `retries` times.
		"""
		# Atelier compile API expects a JSON array of document names, e.g. ["My.Namespace.Class.cls"]
		payload = [class_name]
		headers = {"Content-Type": "application/json"}
		attempt = 0
		while True:
			attempt += 1
			url = _compile_url(self.url, IRIS_ATELIER_VERSION, IRIS_NAMESPACE)
			resp = self.session.post(url, data=json.dumps(payload), headers=headers, timeout=self.timeout)
			if resp.ok:
				return resp
			if not wait or attempt >= retries:
				return resp
			time.sleep(delay)

	def compile_document(self, docname: str, wait: bool = True, retries: int = 3, delay: float = 1.0) -> requests.Response:
		"""Compile a document already present on the server by document name.

		docname should be the filename used on the server (e.g. 'My.Class.cls').
		This is a clearer public wrapper for compile_class.
		"""
		return self.compile_class(docname, wait=wait, retries=retries, delay=delay)

	def delete_document(self, docname: str) -> requests.Response:
		"""Attempt to delete a document from the Atelier store by name.

		This performs a DELETE on the doc endpoint. Returns the Response.
		A 404 is considered non-fatal; the caller can inspect the response.
		"""
		url = _doc_put_url(self.url, IRIS_ATELIER_VERSION, IRIS_NAMESPACE, docname)
		headers = {"Accept": "application/json"}
		try:
			resp = self.session.delete(url, headers=headers, timeout=self.timeout)
		except Exception:
			# Best-effort: swallow any network errors and continue. The caller
			# (send_class) wants to proceed with the PUT regardless of delete
			# failures. We print a concise warning for visibility and return None.
			print(f"Warning: failed to delete existing document '{docname}' — continuing")
			return None
		return resp


# ---- Programmatic API for agentic tools ----
def create_commuter(url: str = None, user: str = None, password: str = None, timeout: int = 30) -> IrisCommuter:
	"""Factory to create a configured IrisCommuter instance."""
	return IrisCommuter(url=url or IRIS_URL, user=user or IRIS_USER, password=password or IRIS_PASSWORD, timeout=timeout)


def import_class_file(commuter: IrisCommuter, path: str) -> dict:
	"""Import (PUT) a class file into IRIS. Returns structured result dict.

	Returns: { 'ok': bool, 'status_code': int, 'response': parsed_json_or_text }
	"""
	cls = IrisClass.from_file(path)
	resp = commuter.import_class(cls)
	try:
		body = resp.json()
	except Exception:
		body = resp.text
	return {"ok": resp.ok, "status_code": resp.status_code, "response": body, "docname": cls.filename or cls.full_name}


def compile_document_name(commuter: IrisCommuter, docname: str) -> dict:
	"""Compile a document already present on server by name.

	Returns: { 'ok': bool, 'status_code': int, 'response': parsed_json }
	"""
	resp = commuter.compile_document(docname)
	try:
		body = resp.json()
	except Exception:
		body = resp.text
	return {"ok": resp.ok, "status_code": resp.status_code, "response": body}


def send_and_compile_file(commuter: IrisCommuter, path: str) -> dict:
	"""Helper to import a file then compile it. Returns combined result.

	Returns: { 'import': {...}, 'compile': {...} }
	"""
	imp = import_class_file(commuter, path)
	if not imp.get("ok"):
		return {"import": imp, "compile": None}
	docname = imp.get("docname")
	comp = compile_document_name(commuter, docname)
	return {"import": imp, "compile": comp}

	def send_and_compile(self, cls: IrisClass, compile_wait: bool = True) -> dict:
		"""Send a class and then request compilation. Returns parsed JSON result or raises on error.
		"""
		send_resp = self.send_class(cls)
		if not send_resp.ok:
			raise RuntimeError(f"Failed to send class: {send_resp.status_code} {send_resp.text}")
		# Use the document name (filename) for compilation if available; Atelier
		# compile API expects document names like 'MyClass.cls'
		docname = cls.filename or cls.full_name
		compile_resp = self.compile_class(docname, wait=compile_wait)
		if not compile_resp.ok:
			raise RuntimeError(f"Failed to compile class: {compile_resp.status_code} {compile_resp.text}")
		try:
			return compile_resp.json()
		except Exception:
			return {"status": "ok", "raw": compile_resp.text}


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="Send and/or compile ObjectScript classes via Atelier REST API")
	parser.add_argument("file", nargs="?", default=os.getenv("CLASS_FILE", "./TestCode.FromPythonCommuter.cls"), help="Path to the .cls file to send/compile")
	parser.add_argument("--send", action="store_true", help="Only send (PUT) the class to the server")
	parser.add_argument("--compile", action="store_true", help="Only compile the class on the server (requires class name or filename)")
	parser.add_argument("--name", help="Document name to use for compile (overrides filename) e.g. My.Namespace.Class.cls")
	args = parser.parse_args()

	try:
		iris_class = IrisClass.from_file(args.file, full_name=None)
	except FileNotFoundError:
		print(f"Class file not found: {args.file}")
		raise

	commuter = IrisCommuter()

	# If --compile only is requested, we don't need to send the file first.
	if args.compile and not args.send:
		docname = args.name or iris_class.filename or iris_class.full_name
		print(f"Requesting compile for {docname}")
		resp = commuter.compile_class(docname)
		print(json.dumps(resp.json(), indent=2))
		quit(0)

	# If send-only
	if args.send and not args.compile:
		doc_url = _doc_put_url(commuter.url, IRIS_ATELIER_VERSION, IRIS_NAMESPACE, iris_class.filename or iris_class.full_name)
		print(f"Sending class {iris_class.full_name} to {doc_url}")
		resp = commuter.send_class(iris_class)
		print(f"Send response: {resp.status_code} {resp.text}")
		quit(0)

	# Default: send then compile
	print(f"Sending class {iris_class.full_name} to server")
	send_resp = commuter.send_class(iris_class)
	print(f"Send response: {send_resp.status_code}")
	if not send_resp.ok:
		print("Send failed:", send_resp.text)
		quit(1)
	# compile
	docname = args.name or iris_class.filename or iris_class.full_name
	print(f"Requesting compile for {docname}")
	compile_resp = commuter.compile_class(docname)
	print(json.dumps(compile_resp.json(), indent=2))

