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
