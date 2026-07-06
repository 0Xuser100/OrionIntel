# OrionIntel
![OrionIntel logo](project-logo.png)
AI-powered RAG platform for analyzing company files, finance reports, and books.

## Setup
Install `uv`, then run `uv sync`.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Alternatively, you can use `pip`:

```bash
pip install uv
```

Then install dependencies:

```bash
uv sync
```

### Activate the virtual environment (Windows)
```cmd
.venv\Scripts\activate
```
### Setup the environment variables
```bash
$ cp .env.example .env
```
Set your environment variables in the `.env` file. Like `OPENAI_API_KEY` value.

## Running the Project

To run the project in development mode, use the following command:

```bash
uv run fastapi dev main.py
```

To run on a specific port (e.g., 7070):

```bash
uv run fastapi dev main.py --port 7070
```
## Run with Docker (fully containerized)

The whole stack — **app + MongoDB + Qdrant** — runs in Docker. The app talks to
MongoDB and Qdrant by their compose service names over a private network; all
state is kept in named volumes.

### 1. Configure environment

```bash
# Mongo credentials for the mongodb container
$ cd docker
$ cp .env.example .env        # set MONGO_INITDB_ROOT_USERNAME / PASSWORD

# App settings
$ cd ../src
$ cp .env.example .env
```

In `src/.env`, set the Docker-internal addresses:

```ini
MONGODB_URL="mongodb://<user>:<pass>@mongodb:27017"   # service name + internal port
VECTOR_DB_URL="http://qdrant:6333"                    # connect to the qdrant container
```

The `<user>`/`<pass>` in `MONGODB_URL` must match `docker/.env`.

### 2. Build and run

```bash
$ cd docker
$ docker compose up --build        # add -d to run in the background
```

App → http://localhost:8000/docs

### Notes
- `VECTOR_DB_URL` set → Qdrant **server** mode (the container). Leave it empty to
  fall back to **embedded** Qdrant for local, non-Docker development.
- Persisted data lives in the `mongodata`, `qdrantdata`, and `app_files` volumes.
- Studio 3T still connects from your host at `localhost:27007`.

See `docs/docker-changes-and-run.md` for the full design and what changed.

## Linting and Code Cleaning

### Ruff (Linting)
To install Ruff:
```bash
uv tool install ruff@latest
```

To run the check:
```bash
uv run ruff check
```

To format code:
```bash
uv run ruff format
```

### Autoflake (Removing Unused Imports)
To add autoflake to the project:
```bash
uv add autoflake
```

To remove unused imports:
```bash
uv run autoflake --in-place --recursive --remove-all-unused-imports .
```

To remove autoflake from the project:
```bash
uv remove autoflake
```

### Black (Formatting)
```bash
uv run black .
```

### isort (Import Sorting)
```bash
uv run isort .
```

## Docker Cleanup (Windows CMD)

If you need to wipe your Docker environment clean, use these commands in your Windows Command Prompt (CMD).

### Stop all running containers
```cmd
FOR /f "tokens=*" %i IN ('docker ps -aq') DO docker stop %i
```
*Stops every active container currently running on your system.*

### Remove all containers
```cmd
FOR /f "tokens=*" %i IN ('docker ps -aq') DO docker rm %i
```
*Deletes all containers (they must be stopped first).*

### Remove all images
```cmd
FOR /f "tokens=*" %i IN ('docker images -q') DO docker rmi %i
```
*Deletes all downloaded or built Docker images.*

### Remove all volumes
```cmd
FOR /f "tokens=*" %i IN ('docker volume ls -q') DO docker volume rm %i
```
*Deletes all persistent data volumes managed by Docker.*

### System Prune (Deep Clean)
```cmd
docker system prune --all
```
*A built-in Docker command that removes all unused containers, networks, and images (dangling and unreferenced) in one go.*
