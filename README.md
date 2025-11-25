# AgenticBugFix

This repository contains helper code and Docker build contexts for working with an InterSystems IRIS test image and a small Python utility to send and compile ObjectScript classes via the Atelier REST API.

## Top-level folders

- `image-iris/` — Docker build context and buildsource for an IRIS image.
- `py-app/` — Python helper CLI and programmatic API (`iris-commuter.py`, `iris_agent_tools.py`) to send and compile `.cls` files.

## Quick start with docker-compose

1. Build and run services with docker-compose (this file includes a `python-runner` service):

   ```powershell
   docker compose up --build -d
   ```

2. Check services and logs:

   ```powershell
   docker compose ps
   docker compose logs -f
   ```

## image-iris notes

- Build the IRIS image locally (optional):

  ```powershell
  docker build -t iris-sample:local ./image-iris
  ```

- Start a container manually:

  ```powershell
  docker run --name iris-sample -d -p 52773:52773 iris-sample:local
  ```

## py-app usage

- Build the python image (if using the `py-app` Dockerfile):

  ```powershell
  docker build -t iris-commuter:local ./py-app
  ```

- Run the CLI locally (PowerShell example):

  ```powershell
  #$env:IRIS_URL='http://localhost:32773'; $env:IRIS_USER='superuser'; $env:IRIS_PASSWORD='fountain'
  python .\py-app\iris-commuter.py .\py-app\TestCode.FromPythonCommuter.cls
  ```

- Send-only:

  ```powershell
  python .\py-app\iris-commuter.py .\py-app\TestCode.FromPythonCommuter.cls --send
  ```

- Compile-only (document already on server):

  ```powershell
  python .\py-app\iris-commuter.py .\py-app\TestCode.FromPythonCommuter.cls --compile --name TestCode.FromPythonCommuter.cls
  ```

## Agentic integration

- Use `py-app/iris_agent_tools.py` in automation. Example:

  ```python
  from iris_agent_tools import create_commuter, send_and_compile_file
  commuter = create_commuter()
  print(send_and_compile_file(commuter, './TestCode.FromPythonCommuter.cls'))
  ```


## License

MIT