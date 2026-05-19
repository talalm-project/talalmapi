# 5) Database setup and migrations (Alembic)

## 5.1 Create the configured database
```bash
python -m app.cli db:create
```

For the test database:
```bash
APP_ENV=test python -m app.cli db:create
```

## 5.2 Apply migrations
```bash
python -m app.cli db:upgrade
```

## 5.3 Generate a new migration from your models
```bash
python -m app.cli db:migrate --message "add projects"
python -m app.cli db:upgrade
```

## 5.4 Roll back migrations
```bash
python -m app.cli db:downgrade
python -m app.cli db:history
python -m app.cli db:current
```

This starter uses SQLAlchemy 2.0 models with Alembic autogeneration. The
database URL comes from `DATABASE_URL` or the active section in `database.yaml`.
