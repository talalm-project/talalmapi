# FastAPI API Starter

This repository is a FastAPI scaffold that keeps the same high-level shape as
`default_api_flask`: app factory, controller modules, operation objects,
database migrations, storage helpers, and domain-based request specs.

It adds three Rails-style developer affordances by default:
- `spec/` request specs powered by `pytest` and `factory_boy`
- PostgreSQL-first SQLAlchemy + Alembic setup
- namespaced command-line routines through `python -m app.cli`

## Quick Start

```bash
cp .env.example .env
python -m venv env
source env/bin/activate
pip install -r requirements.txt
python -m app.cli db:create
python -m app.cli db:upgrade
python -m app.cli system:seed
python -m app.cli server
```

Run specs with:

```bash
python -m app.cli spec
```

## High-Level Setup

## 1. Install dependencies
Create a virtual environment and install the project requirements:

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

## 2. Configure environment variables
Create your local environment file from the template:

```bash
cp .env.example .env
```

By default, the project reads:
- `.env` when `APP_ENV=development`
- `.env.test` when `APP_ENV=test`

Important variables:
- `APP_ENV`: active environment, usually `development` or `test`
- `SECRET_KEY`: JWT signing key
- `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: PostgreSQL settings
- `DATABASE_URL`: optional full database URL override
- `STORAGE_*`: RustFS file storage settings through the S3-compatible API
- `LOCAL_MODELS_MANIFEST_PATH`: path to the local GGUF model manifest
- `INFERENCE_SYSTEM_PROMPT`: global inference system prompt; defaults to Markdown answers
- `AWS_ENDPOINT`: set to `http://localhost:4566` when developing against MiniStack
- `SQS_QUEUE_URL`: queue URL for the SQS queue your app should use

With the default values, the app expects PostgreSQL databases named:
- `default_api_fast_development`
- `default_api_fast_test`

## 3. Create and migrate the database
Create the configured development database:

```bash
python -m app.cli db:create
python -m app.cli db:upgrade
```

Create the test database:

```bash
APP_ENV=test python -m app.cli db:create
APP_ENV=test python -m app.cli db:upgrade
```

## 4. Run specs
Run the full spec suite:

```bash
python -m app.cli spec
```

Run a single spec file:

```bash
python -m app.cli spec spec/users/test_create.py
```

Filter by keyword:

```bash
python -m app.cli spec --keyword create
```

Optional convenience wrapper:

```bash
./bin/spec
./bin/spec spec/users/test_create.py
```

## 5. Seed the default admin
Seed the default admin user for local development:

```bash
python -m app.cli system:seed
```

This creates or updates:
- `email`: `admin@example.com`
- `first_name`: `admin`
- `last_name`: `example`
- `role`: `admin`
- `password`: `password`

## 6. Start the development server
Run the local FastAPI server with reload enabled:

```bash
python -m app.cli server
```

This starts Uvicorn on `http://127.0.0.1:3000`.

If you need local SQS, start MiniStack in a separate terminal:

```bash
bin/start_ministack.sh
```

That script starts MiniStack on `http://localhost:4566`, creates a FIFO queue,
and prints the `AWS_ENDPOINT` and `SQS_QUEUE_URL` values to export into your
shell or `.env`.

Example:

```bash
export AWS_ENDPOINT=http://localhost:4566
export SQS_QUEUE_URL=http://localhost:4566/000000000000/tphlms.fifo
python -m app.cli server
```

Useful development endpoints:
- `GET /health`
- `POST /login`
- `/users` CRUD endpoints require an authenticated admin user
- `GET /system/local_models` returns local GGUF models from the local manifest
- `/connectors` CRUD endpoints manage local and OpenAI model connectors
- `POST /connectors/{id}/infer` runs inference through a connector
- `POST /uploads`

## Local GGUF Model Manifest

Local GGUF model files are not committed to the repository. Keep them under
`talalmapi/models/` and describe them in a local manifest file named
`manifest-local-models.yml`.

Create the local manifest from the example:

```bash
cp manifest-local-models.yml.example manifest-local-models.yml
```

Each manifest entry has a display `name`, a `type` (`inference`, `embedding`,
or `embeddings`), and a `path` relative to the backend application directory:

```yaml
-
  name: "Mistral 3.5"
  type: "inference"
  path: "models/mistral.gguf"
```

The API reads this file for `GET /system/local_models`. To use a different
location, set `LOCAL_MODELS_MANIFEST_PATH` in `talalmapi/.env`.

## Connectors

Connectors store provider-specific runtime settings in the `data` JSON
attribute. Caller-provided keys are preserved, and the backend adds a normalized
`data.metadata` object during connector creation and update. Inference and
embedding generation read from this metadata first, while older top-level keys
such as `model_options` and `embedding_model_options` remain supported as
fallbacks.

Standard `data.metadata` shape:

```json
{
  "schema_version": 1,
  "provider": "local",
  "inference": {
    "model": {
      "name": "Mistral 3.5",
      "local_file_path": "models/mistral.gguf"
    },
    "model_options": {
      "n_ctx": 4096
    },
    "limits": {
      "context_window_tokens": 4096,
      "max_input_tokens": 4096,
      "default_output_tokens": 1024
    }
  },
  "embeddings": {
    "model": {
      "name": "Qwen Embedding",
      "local_file_path": "models/qwen-embedding.gguf",
      "embedding_size": 1024
    },
    "model_options": {
      "n_ctx": 65536,
      "n_batch": 512
    },
    "limits": {
      "context_window_tokens": 65536,
      "max_input_tokens": 256,
      "max_content_tokens": 255,
      "ideal_chunk_tokens": 191
    },
    "chunking": {
      "strategy": "text-with-token-safety",
      "unit": "characters",
      "chunk_size": 764,
      "chunk_overlap": 76
    }
  }
}
```

For `local` connectors:

- `inference.model.local_file_path` is copied from `local_file_path`.
- `embeddings.model.local_file_path` is copied from
  `embedding_local_file_path`.
- `embeddings.model.embedding_size` is read from GGUF metadata when the file is
  available; otherwise it is `null`.
- `inference.model_options` comes from top-level `data.model_options`.
- `embeddings.model_options` comes from top-level
  `data.embedding_model_options`.

For `openai` connectors:

- `provider` is `openai`.
- `*.model.local_file_path` is `null`.
- `embeddings.model.name` is copied from `embedding_name`.
- Known embedding sizes and token limits are populated for
  `text-embedding-3-small`, `text-embedding-3-large`, and
  `text-embedding-ada-002`; unknown embedding models use `null` for
  `embedding_size` and the default embedding input token limit.

Embedding chunking is stored in character units because file parsers extract
plain text before token-safe splitting. Local embedding generation still checks
the runtime llama token limit before embedding, and uses the smaller of the
metadata limit and the actual llama context capacity.

## Connector Inference

Connectors support two application-level `connection_type` values:

- `local`: uses `llama-cpp-python` against a local `.gguf` model file.
- `openai`: uses the OpenAI Python SDK against the Responses API.

Run inference with:

```bash
curl -X POST http://127.0.0.1:3000/connectors/<connector-id>/infer \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"input":[{"role":"user","content":"Explain vector databases"}]}'
```

Request body:

| Field | Type | Notes |
| --- | --- | --- |
| `prompt` | string | Convenience field for a single user prompt. |
| `input` | string or array | For local connectors, string input becomes a user chat message and array input is passed as chat messages. For OpenAI connectors, this is passed to `responses.create`. |
| `model` | string | Optional OpenAI model override. Defaults to the connector `name`. |
| `options` | object | Additional SDK options passed to `create_chat_completion` for local connectors or `responses.create` for OpenAI connectors. |

Local inference only accepts model paths ending in `.gguf`, case-insensitive.
Local connectors use `create_chat_completion`, so instruction/chat GGUF models
receive chat messages rather than raw completion prompts.

Local GGUF models are kept warm in an in-process cache keyed by model path and
model options. Calls against the same cached model are serialized because
`llama-cpp-python` model instances are not safe to use concurrently. Unless a
connector explicitly sets these llama.cpp options, local inference defaults to:

| Option | Default | Override |
| --- | --- | --- |
| `n_threads` | half of available CPU threads | `LLAMA_CPP_N_THREADS` |
| `n_threads_batch` | all available CPU threads | `LLAMA_CPP_N_THREADS_BATCH` |
| `n_ctx` | `4096` unless explicitly configured | `LLAMA_CPP_N_CTX` |
| `n_batch` | `1024` | `LLAMA_CPP_N_BATCH` |
| `no_perf` | `true` | `LLAMA_CPP_NO_PERF` |
| `verbose` | `false` | `LLAMA_CPP_VERBOSE` |

Use a larger explicit connector `model_options.n_ctx`, or set
`LLAMA_CPP_N_CTX`, only when the request needs a larger prompt window.

Response body:

| Field | Type | Notes |
| --- | --- | --- |
| `response` | object | The complete SDK response returned by `llama-cpp-python` or the OpenAI SDK. |
| `details` | object | Derived inference metrics. |

`details` contains:

| Field | Type | Notes |
| --- | --- | --- |
| `prompt_tokens` | integer or null | Prompt/input token count when reported by the SDK. |
| `completion_tokens` | integer or null | Completion/output token count when reported by the SDK. |
| `total_tokens` | integer or null | Total token count when reported or derivable from prompt and completion counts. |
| `finish_reason` | string or null | SDK finish reason when reported, such as `stop` or `length`. |
| `elapsed_seconds` | number | Wall-clock time spent inside the SDK inference call. |
| `tokens_per_second` | number or null | Completion tokens per second when completion tokens are known; otherwise total tokens per second when total tokens are known. |

When local connector inference does not specify `options.max_tokens`, the API
defaults to `1024` output tokens to reduce accidental mid-answer truncation.

The global inference system prompt is configured through
`INFERENCE_SYSTEM_PROMPT`. By default it is:

```text
You are a helpful assistant. Answer in Markdown. Keep the response complete and concise enough to fit within the configured maximum output tokens.
```

For local connectors, this prompt is prepended as a `system` message unless the
request already includes a `system` or `developer` message. For OpenAI
connectors, it is sent as `instructions` unless `options.instructions` is
provided.

## File Uploads with RustFS

The root `docker-compose.yml` provides RustFS for local S3-compatible object
storage. Start it from the repository root before running the API with S3
storage enabled:

```bash
docker compose up -d
```

Then create the bucket from the backend directory so the command reads
`talalmapi/.env`:

```bash
python -m app.cli services:create_bucket
```

RustFS defaults:
- S3 API: `http://localhost:9000`
- Console: `http://localhost:9001`
- Access key: `rustfsadmin`
- Secret key: `rustfsadmin`

Set these values in `talalmapi/.env`:

```bash
STORAGE_S3_BUCKET=talalm-local
STORAGE_S3_REGION=us-east-1
STORAGE_S3_ENDPOINT=http://localhost:9000
STORAGE_S3_ACCESS_KEY_ID=rustfsadmin
STORAGE_S3_SECRET_ACCESS_KEY=rustfsadmin
STORAGE_S3_PUBLIC_URL=http://localhost:9000/talalm-local
STORAGE_S3_SIGNATURE_VERSION=s3v4
STORAGE_S3_ADDRESSING_STYLE=path
STORAGE_S3_CREATE_BUCKET=true
```

`python -m app.cli services:create_bucket` creates the bucket from the backend
`.env` configuration. `STORAGE_S3_CREATE_BUCKET=true` can also create it during
API startup when it is missing. Upload through the API with:

```bash
curl -F file=@avatar.png http://127.0.0.1:3000/uploads
```

## Steps
- [1) Create a new project from this codebase](docs/step-1-create-project.md)
- [2) Configure the environment](docs/step-2-configure-environment.md)
- [3) Run the server](docs/step-3-run-server.md)
- [4) Run with Gunicorn](docs/step-4-gunicorn.md)
- [5) Database setup and migrations (Alembic)](docs/step-5-database-migrations.md)
- [6) Specs](docs/step-6-tests.md)
- [7) Command-line routines (`python -m app.cli`)](docs/step-7-cli.md)
- [8) Create a new model (example: Project)](docs/step-8-create-model.md)
- [9) Create a controller (example: Project)](docs/step-9-create-controller.md)
- [10) File uploads with RustFS](docs/step-10-file-uploads.md)

## Examples
- [Example test stubs](docs/example-test-stubs.md)
- [Controller example](docs/example-controller.md)
