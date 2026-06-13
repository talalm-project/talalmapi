# 7) Command-line routines (`python -m app.cli`)

FastAPI does not ship with a built-in task runner, so this starter exposes a
small Python command runner through `app/cli.py`.

## 7.1 Run a command
```bash
python -m app.cli server
python -m app.cli spec spec/users/test_create.py
python -m app.cli system:create_backup --output /tmp/talalm-backup.zip
python -m app.cli system:seed
python -m app.cli system:restore_factory_settings
python -m app.cli services:create_bucket
python -m app.cli db:create
python -m app.cli db:upgrade
```

`system:seed` creates or updates the default admin user:
- `email`: `admin@example.com`
- `first_name`: `admin`
- `last_name`: `example`
- `role`: `admin`
- `password`: `password`

`services:create_bucket` creates the RustFS bucket configured by the backend
`.env` storage settings.

`system:create_backup` creates a local zip archive containing a PostgreSQL dump,
RustFS bucket objects, local model files, model manifest, nearby env files, and
`backup.json` metadata. PostgreSQL backups require `pg_dump` to be installed in
the environment running the command.

`system:restore_factory_settings` drops the configured database, recreates it,
runs all migrations, and seeds the default admin user. It is destructive and
should only be run against a database you intend to reset.

## 7.2 Where tasks live
- `app/cli.py`: command parsing and reusable helpers such as database creation
- `bin/spec`: optional thin wrapper around `python -m app.cli spec`

## 7.3 Template for new commands
```python
def run_seed(_args):
    print("seeded")
```

Then register the handler in `build_parser()` inside `app/cli.py`.
