import uuid
from urllib.parse import quote

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from fastapi import UploadFile
from werkzeug.utils import secure_filename


_storage_s3_client = None


def init_storage(settings):
    if not settings.STORAGE_S3_BUCKET:
        raise ValueError("STORAGE_S3_BUCKET must be set")
    client = _get_s3_client(settings)
    if settings.STORAGE_S3_CREATE_BUCKET:
        ensure_bucket(settings, client=client)


def ensure_bucket(settings, client=None):
    if not settings.STORAGE_S3_BUCKET:
        raise ValueError("STORAGE_S3_BUCKET must be set")
    client = client or _get_s3_client(settings)
    return _ensure_s3_bucket(client, settings.STORAGE_S3_BUCKET, settings.STORAGE_S3_REGION)


def store_file(upload: UploadFile, settings, filename=None):
    return _store_s3(upload, settings, filename)


def store_file_at_key(upload: UploadFile, settings, key, filename=None):
    return _store_s3(upload, settings, filename=filename, key=key)


def delete_file(settings, key):
    bucket = settings.STORAGE_S3_BUCKET
    if not bucket:
        raise ValueError("STORAGE_S3_BUCKET must be set")

    client = _get_s3_client(settings)
    client.delete_object(Bucket=bucket, Key=key)


def get_file(settings, key):
    bucket = settings.STORAGE_S3_BUCKET
    if not bucket:
        raise ValueError("STORAGE_S3_BUCKET must be set")

    client = _get_s3_client(settings)
    return client.get_object(Bucket=bucket, Key=key)


def download_file_to_path(settings, key, destination_path):
    bucket = settings.STORAGE_S3_BUCKET
    if not bucket:
        raise ValueError("STORAGE_S3_BUCKET must be set")

    client = _get_s3_client(settings)
    client.download_file(bucket, key, str(destination_path))


def _store_s3(upload, settings, filename=None, key=None):
    bucket = settings.STORAGE_S3_BUCKET
    if not bucket:
        raise ValueError("STORAGE_S3_BUCKET must be set")

    safe_name = _build_filename(upload.filename, filename)
    key = _build_prefixed_key(key, settings.STORAGE_S3_PREFIX) if key else _build_key(safe_name, settings.STORAGE_S3_PREFIX)
    client = _get_s3_client(settings)

    extra_args = {}
    if upload.content_type:
        extra_args["ContentType"] = upload.content_type
    if settings.STORAGE_S3_ACL:
        extra_args["ACL"] = settings.STORAGE_S3_ACL

    upload.file.seek(0)
    if extra_args:
        client.upload_fileobj(upload.file, bucket, key, ExtraArgs=extra_args)
    else:
        client.upload_fileobj(upload.file, bucket, key)
    public_url = _build_s3_public_url(bucket, key, settings, client)
    return _file_result(key, safe_name, upload.content_type, None, public_url)


def _build_filename(original, override):
    name = override or original or "file"
    return secure_filename(name) or "file"


def _build_key(filename, prefix=""):
    prefix = (prefix or "").strip("/")
    unique = uuid.uuid4().hex
    key = f"{unique}-{filename}"
    return f"{prefix}/{key}" if prefix else key


def _build_prefixed_key(key, prefix=""):
    key = str(key).strip("/")
    prefix = (prefix or "").strip("/")
    return f"{prefix}/{key}" if prefix else key


def _build_s3_public_url(bucket, key, settings, client):
    if settings.STORAGE_S3_PUBLIC_URL:
        base = settings.STORAGE_S3_PUBLIC_URL.rstrip("/")
        return f"{base}/{quote(key)}"

    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=int(settings.STORAGE_S3_PRESIGNED_EXPIRES_IN),
    )


def _get_s3_client(settings):
    global _storage_s3_client
    if _storage_s3_client is not None:
        return _storage_s3_client

    region = settings.STORAGE_S3_REGION or None
    endpoint = settings.STORAGE_S3_ENDPOINT or None
    access_key_id = settings.STORAGE_S3_ACCESS_KEY_ID or None
    secret_access_key = settings.STORAGE_S3_SECRET_ACCESS_KEY or None
    session_token = settings.STORAGE_S3_SESSION_TOKEN or None
    client_config = BotoConfig(
        signature_version=settings.STORAGE_S3_SIGNATURE_VERSION or "s3v4",
        s3={"addressing_style": settings.STORAGE_S3_ADDRESSING_STYLE or "path"},
    )
    _storage_s3_client = boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=session_token,
        config=client_config,
    )
    return _storage_s3_client


def _ensure_s3_bucket(client, bucket, region=None):
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as error:
        status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        error_code = error.response.get("Error", {}).get("Code")
        if status_code == 404 or error_code in {"404", "NoSuchBucket", "NotFound"}:
            create_args = {"Bucket": bucket}
            if region and region != "us-east-1":
                create_args["CreateBucketConfiguration"] = {"LocationConstraint": region}
            client.create_bucket(**create_args)
            return True
        raise
    return False


def _file_result(key, filename, content_type, size, url):
    return {
        "key": key,
        "filename": filename,
        "content_type": content_type,
        "byte_size": size,
        "url": url,
    }
