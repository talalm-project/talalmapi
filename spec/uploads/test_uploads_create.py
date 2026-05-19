def test_create_upload_stores_file_in_rustfs(client, monkeypatch):
    captured = {}

    def fake_store_file(upload, settings, filename=None):
        captured["upload_filename"] = upload.filename
        captured["content_type"] = upload.content_type
        captured["filename"] = filename
        captured["bucket"] = settings.STORAGE_S3_BUCKET
        return {
            "key": "avatars/example.png",
            "filename": "profile.png",
            "content_type": "image/png",
            "byte_size": None,
            "url": "http://localhost:9000/talalm-test/avatars/example.png",
        }

    monkeypatch.setattr("app.controllers.uploads_controller.store_file", fake_store_file)

    response = client.post(
        "/uploads",
        files={"file": ("avatar.png", b"image-bytes", "image/png")},
        data={"filename": "profile.png"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "file": {
            "key": "avatars/example.png",
            "filename": "profile.png",
            "content_type": "image/png",
            "byte_size": None,
            "url": "http://localhost:9000/talalm-test/avatars/example.png",
        }
    }
    assert captured == {
        "upload_filename": "avatar.png",
        "content_type": "image/png",
        "filename": "profile.png",
        "bucket": "talalm-test",
    }


def test_local_file_route_is_not_registered(client):
    response = client.get("/files/example.png")

    assert response.status_code == 404
