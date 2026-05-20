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
- `POST /uploads`

## Local GGUF Model Manifest

Local GGUF model files are not committed to the repository. Keep them under
`talalmapi/models/` and describe them in a local manifest file named
`manifest-local-models.yml`.

Create the local manifest from the example:

```bash
cp manifest-local-models.yml.example manifest-local-models.yml
```

Each manifest entry has a display `name` and a `path` relative to the backend
application directory:

```yaml
-
  name: "Mistral 3.5"
  path: "models/mistral.gguf"
```

The API reads this file for `GET /system/local_models`. To use a different
location, set `LOCAL_MODELS_MANIFEST_PATH` in `talalmapi/.env`.

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
