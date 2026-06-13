# 3) Run the server

Start the development server:
```bash
python -m app.cli server
```

This runs:
```bash
uvicorn main:app --host 127.0.0.1 --port 3000 --reload
```

Useful endpoints:
- `GET /health`
- `POST /login`
- `/users` CRUD endpoints require an authenticated admin user
- `POST /uploads`
