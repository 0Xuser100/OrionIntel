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


