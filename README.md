# OrionIntel
![OrionIntel logo](assets/project-logo.png)
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
## Run Docker Compose Services

```bash
$ cd docker
$ cp .env.example .env
```
Update .env with your credentials
```bash
$ cd docker
$  docker compose up -d
```

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
