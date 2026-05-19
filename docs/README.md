# Documentation

For local SQS development, use `bin/start_ministack.sh`. It starts MiniStack on
`http://localhost:4566`, creates a queue, and prints the `AWS_ENDPOINT` and
`SQS_QUEUE_URL` values to use in your shell or `.env`.

- [1) Create a new project from this codebase](step-1-create-project.md)
- [2) Configure the environment](step-2-configure-environment.md)
- [3) Run the server](step-3-run-server.md)
- [4) Run with Gunicorn](step-4-gunicorn.md)
- [5) Database setup and migrations (Alembic)](step-5-database-migrations.md)
- [6) Specs](step-6-tests.md)
- [7) Command-line routines (`python -m app.cli`)](step-7-cli.md)
- [8) Create a new model (example: Project)](step-8-create-model.md)
- [9) Create a controller (example: Project)](step-9-create-controller.md)
- [10) File uploads with RustFS](step-10-file-uploads.md)
