# 2) Configure the environment

## 2.1 Create your virtual environment
```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

## 2.2 Create `.env`
```bash
cp .env.example .env
```

Key settings:
- `APP_ENV`: `development`, `test`, or `production`
- `DATABASE_URL`: optional full override
- `DB_*`: component-based PostgreSQL settings used by `database.yaml`
- `SECRET_KEY`: JWT signing key
- `STORAGE_*`: RustFS file storage through the S3-compatible API

## 2.3 Default database names
With the supplied defaults, `database.yaml` resolves to:
- development: `default_api_fast_development`
- test: `default_api_fast_test`
- production: `default_api_fast`
