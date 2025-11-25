# IRIS Image (image-iris)

This folder contains Docker build context and helper scripts to produce an InterSystems IRIS image preloaded with sample buildsource.

Contents
- `Dockerfile` — Dockerfile to build the image.
- `buildsource/` — files that will be imported into IRIS during build or first-run. Contains loader scripts and sample namespaces.

Quick overview
- The `buildsource` directory contains structure and scripts used to load code into the image at build or startup time. Adjust the loader scripts if you need a different import behavior.

Build the image (local)

Open a terminal in the repository root and run:

```powershell
docker build -t iris-sample:local ./image-iris
```

Run the image

Start a container (basic):

```powershell
docker run --name iris-sample -d -p 52773:52773 iris-sample:local
```

If the image exposes management ports, map them as required.

Using the provided `buildsource`
- `buildsource/loader.sh` is a small helper that demonstrates how the buildsource is applied. It calls the project-specific merge/import commands and can be adapted.
- `buildsource/merge/merge.cpf` contains CPF-style merge instructions (translated comments are in the repository).

Troubleshooting
- If the image fails to start, check container logs with `docker logs <container>`.
- If imports don't apply, inspect `buildsource/loader.sh` and ensure file permissions allow execution.

Notes
- This module is an example scaffolding to bootstrap an IRIS image. For production images follow InterSystems packaging and licensing requirements.

