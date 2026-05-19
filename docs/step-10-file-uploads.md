# 10) File uploads with RustFS

The upload controller stores files through `app/storage.py`. RustFS is the only
supported backend, using its S3-compatible API through `boto3`.

The root `docker-compose.yml` starts a local RustFS server with:
- S3 API: `http://localhost:9000`
- Console: `http://localhost:9001`
- Access key: `rustfsadmin`
- Secret key: `rustfsadmin`

Start RustFS from the repository root:

```bash
docker compose up -d
```

Then create the bucket from the backend directory so the command reads
`talalmapi/.env`:

```bash
python -m app.cli services:create_bucket
```

Configure the API:

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
API startup if it does not already exist.

Upload a file through the API:

```bash
curl -F file=@avatar.png http://127.0.0.1:3000/uploads
```

The response includes the RustFS object key and public URL. You can verify
uploads in the RustFS console at `http://localhost:9001`.

Optional settings:
- `STORAGE_S3_SESSION_TOKEN`
- `STORAGE_S3_PREFIX`
- `STORAGE_S3_ACL`
- `STORAGE_S3_PRESIGNED_EXPIRES_IN`
