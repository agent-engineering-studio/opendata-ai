# Template: Ollama pre-built image

Reusable files for projects that need an Ollama image with a model **baked in** at build time, published to ghcr.io via GitHub Actions.

## Files

| File | Destination in your project | Purpose |
|---|---|---|
| `Dockerfile` | `infra/ollama/Dockerfile` | Builds the image: pulls the base model, creates a modelfile with extended `num_ctx`, stops the server |
| `publish-ollama.yml` | `.github/workflows/publish-ollama.yml` | GitHub Actions workflow: builds and pushes to ghcr.io on tag push or manual dispatch |
| `docker-compose.snippet.yml` | Merge into `docker-compose.yml` | CPU/GPU profiles, healthcheck, volume |
| `Makefile.snippet` | Paste into `Makefile` | `build-ollama`, `pull-models` (fallback), `rebuild-all` |

## Quick start

1. Copy the four files to the paths above.
2. Search for every `MY-ORG` / `MY-PROJECT` / `my-project` placeholder and replace with your values.
3. Configure variables (model name, context size) in the `env:` section of the workflow and in the Makefile variables block.
4. Enable write permissions for GitHub Actions:
   **Settings → Actions → General → Workflow permissions → Read and write**
5. Push a tag (`v1.0.0`) or run the workflow manually — the image will appear at `ghcr.io/<your-org>/<image-name>:latest`.

## Makefile targets added

| Target | What it does |
|---|---|
| `build-ollama` | Local build of the Ollama image (~7 GB, slow — use only for testing) |
| `pull-models` | Fallback: pulls model directly into a running container (no pre-built image needed) |
| `rebuild-all` | Full rebuild: `build-ollama` + app images without cache |

## Tradeoffs

| Approach | Pro | Con |
|---|---|---|
| Pre-built image (this template) | Fast startup, reproducible, no model pull at runtime | Large image (~7 GB), slow CI build, one image per model variant |
| `pull-models` fallback | Small base image, flexible | Slow first start, requires internet access at runtime |

## Disk space note

GitHub-hosted runners have ~14 GB free. The workflow frees space by removing unused toolchains before the Docker build step. If you switch to a larger model, you may need to free additional space.
