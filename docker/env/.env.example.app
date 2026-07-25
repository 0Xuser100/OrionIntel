APP_NAME="OrionIntel"
APP_VENDOR="Virello"
APP_VERSION="0.1"

FILE_ALLOWED_TYPES=["text/plain","application/pdf"]
FILE_MAX_SIZE=10
FILE_DEFAULT_CHUNK_SIZE=512000

# ========================= MongoDB (UNUSED) =========================
# The app does NOT use MongoDB (only Postgres + Qdrant at runtime), but
# config.py still declares MONGODB_URL / MONGODB_DATABASE as required.
# These dummy values just let the app boot. Once you make those two fields
# Optional in src/helpers/config.py, you can delete these two lines.
MONGODB_URL="mongodb://unused:unused@localhost:27017"
MONGODB_DATABASE="unused"

# ========================= Postgres =========================
# host = compose service "pgvector", internal port 5432.
# Values MUST match ./env/.env.postgres (and docker/orionintel/alembic.ini).
POSTGRES_USERNAME="orionintel"
POSTGRES_PASSWORD="orionintel_pass"
POSTGRES_HOST="pgvector"
POSTGRES_PORT=5432
POSTGRES_MAIN_DATABASE="orionintel"

# ========================= LLM Config =========================
GENERATION_BACKEND="OPENAI"
EMBEDDING_BACKEND="COHERE"

OPENAI_API_KEY="key___"
OPENAI_API_URL=
COHERE_API_KEY="key___"

GENERATION_MODEL_ID_LITERAL=["gpt-4o-mini","gpt-4o","gpt-4.1-mini-2025-04-14"]
GENERATION_MODEL_ID="gpt-4o-mini"
EMBEDDING_MODEL_ID="text-embedding-3-small"
EMBEDDING_MODEL_SIZE=384

INPUT_DAFAULT_MAX_CHARACTERS=1024
GENERATION_DAFAULT_MAX_TOKENS=200
GENERATION_DAFAULT_TEMPERATURE=0.1

# ========================= Vector DB Config =========================
# Server mode: point at the qdrant container (this WINS over VECTOR_DB_PATH).
VECTOR_DB_BACKEND_LITERAL=["QDRANT","PGVECTOR"]
VECTOR_DB_BACKEND="QDRANT"
VECTOR_DB_DISTANCE_METHOD="cosine"
VECTOR_DB_PATH="qdrant_db"
VECTOR_DB_URL="http://qdrant:6333"
VECTOR_DB_PGVEC_INDEX_THRESHOLD=100

# ========================= Template Config =========================
PRIMARY_LANG="en"
DEFAULT_LANG="en"
