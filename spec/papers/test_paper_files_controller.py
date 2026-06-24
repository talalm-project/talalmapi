from app.helpers.api_helpers import build_jwt_header, generate_jwt
from app.models.paper_file import PaperFile
from spec.factories import PaperFactory, PaperFileFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_upload_paper_file_stores_file_in_rustfs(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    captured = {}

    def fake_store_file_at_key(upload, settings, key, filename=None):
        captured["upload_filename"] = upload.filename
        captured["content_type"] = upload.content_type
        captured["key"] = key
        captured["filename"] = filename
        captured["bucket"] = settings.STORAGE_S3_BUCKET
        return {
            "key": key,
            "filename": filename,
            "content_type": upload.content_type,
            "byte_size": None,
            "url": f"http://localhost:9000/talalm-test/{key}",
        }

    monkeypatch.setattr("app.operations.papers.create_file.store_file_at_key", fake_store_file_at_key)

    response = client.post(
        f"/papers/{paper.id}/files/upload",
        headers=_headers(app, user),
        data={"path": "source/sections/introduction.tex"},
        files={"file": ("introduction.tex", b"\\section{Introduction}", "application/x-tex")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["paper_id"] == paper.id
    assert payload["path"] == "source/sections/introduction.tex"
    assert payload["filename"] == "introduction.tex"
    assert payload["content_type"] == "application/x-tex"
    assert payload["size"] == len(b"\\section{Introduction}")
    assert payload["storage_key"] == f"papers/{paper.id}/source/sections/introduction.tex"
    assert captured == {
        "upload_filename": "introduction.tex",
        "content_type": "application/x-tex",
        "key": f"papers/{paper.id}/source/sections/introduction.tex",
        "filename": "introduction.tex",
        "bucket": "talalm-test",
    }


def test_upload_paper_file_preserves_nested_relative_path(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    monkeypatch.setattr(
        "app.operations.papers.create_file.store_file_at_key",
        lambda upload, settings, key, filename=None: {
            "key": key,
            "filename": filename,
            "content_type": upload.content_type,
            "byte_size": None,
            "url": "http://localhost/object",
        },
    )

    response = client.post(
        f"/papers/{paper.id}/files/upload",
        headers=_headers(app, user),
        data={"path": "source/sections/methodology.tex"},
        files={"file": ("methodology.tex", b"Method", "application/x-tex")},
    )

    assert response.status_code == 201
    assert response.json()["path"] == "source/sections/methodology.tex"
    assert response.json()["storage_key"] == f"papers/{paper.id}/source/sections/methodology.tex"


def test_upload_paper_file_infers_source_path_for_tex_files(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    monkeypatch.setattr(
        "app.operations.papers.create_file.store_file_at_key",
        lambda upload, settings, key, filename=None: {
            "key": key,
            "filename": filename,
            "content_type": upload.content_type,
            "byte_size": None,
            "url": "http://localhost/object",
        },
    )

    response = client.post(
        f"/papers/{paper.id}/files/upload",
        headers=_headers(app, user),
        files={"file": ("main.tex", b"hello", "application/x-tex")},
    )

    assert response.status_code == 201
    assert response.json()["path"] == "source/main.tex"
    assert response.json()["storage_key"] == f"papers/{paper.id}/source/main.tex"


def test_upload_paper_file_infers_assets_path_for_images(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    monkeypatch.setattr(
        "app.operations.papers.create_file.store_file_at_key",
        lambda upload, settings, key, filename=None: {
            "key": key,
            "filename": filename,
            "content_type": upload.content_type,
            "byte_size": None,
            "url": "http://localhost/object",
        },
    )

    response = client.post(
        f"/papers/{paper.id}/files/upload",
        headers=_headers(app, user),
        files={"file": ("figure 1.png", b"png", "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["path"] == "assets/figure_1.png"
    assert response.json()["filename"] == "figure_1.png"


def test_upload_paper_file_rejects_path_traversal(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    stored = {"called": False}
    monkeypatch.setattr(
        "app.operations.papers.create_file.store_file_at_key",
        lambda upload, settings, key, filename=None: stored.update({"called": True}),
    )

    response = client.post(
        f"/papers/{paper.id}/files/upload",
        headers=_headers(app, user),
        data={"path": "../main.tex"},
        files={"file": ("main.tex", b"hello", "application/x-tex")},
    )

    assert response.status_code == 422
    assert response.json()["path"] == ["invalid"]
    assert stored == {"called": False}


def test_upload_paper_file_rejects_too_large_file(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    app.state.settings.STORAGE_MAX_CONTENT_LENGTH_MB = 1
    stored = {"called": False}
    monkeypatch.setattr(
        "app.operations.papers.create_file.store_file_at_key",
        lambda upload, settings, key, filename=None: stored.update({"called": True}),
    )

    response = client.post(
        f"/papers/{paper.id}/files/upload",
        headers=_headers(app, user),
        files={"file": ("main.tex", b"x" * (1024 * 1024 + 1), "application/x-tex")},
    )

    assert response.status_code == 422
    assert response.json()["file"] == ["too large"]
    assert stored == {"called": False}


def test_upload_paper_file_hides_other_users_paper(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory()
    stored = {"called": False}
    monkeypatch.setattr(
        "app.operations.papers.create_file.store_file_at_key",
        lambda upload, settings, key, filename=None: stored.update({"called": True}),
    )

    response = client.post(
        f"/papers/{paper.id}/files/upload",
        headers=_headers(app, user),
        files={"file": ("main.tex", b"hello", "application/x-tex")},
    )

    assert response.status_code == 404
    assert stored == {"called": False}


def test_list_paper_files_returns_current_users_files(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    first = PaperFileFactory(paper=paper, path="source/main.tex")
    second = PaperFileFactory(paper=paper, path="source/references.bib")
    PaperFileFactory(path="source/other.tex")

    response = client.get(f"/papers/{paper.id}/files", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [second.id, first.id]


def test_show_paper_file_returns_metadata(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(paper=paper, path="source/main.tex")

    response = client.get(f"/papers/{paper.id}/files/{paper_file.id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["id"] == paper_file.id
    assert response.json()["path"] == "source/main.tex"


def test_show_paper_file_rejects_file_from_different_paper(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    other_file = PaperFileFactory()

    response = client.get(f"/papers/{paper.id}/files/{other_file.id}", headers=_headers(app, user))

    assert response.status_code == 404


def test_delete_paper_file_removes_rustfs_object(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(paper=paper, storage_key=f"papers/{paper.id}/source/main.tex")
    paper_file_id = paper_file.id
    deleted = {}

    def fake_delete_file(settings, key):
        deleted["bucket"] = settings.STORAGE_S3_BUCKET
        deleted["key"] = key

    monkeypatch.setattr("app.operations.papers.destroy_file.delete_file", fake_delete_file)

    response = client.delete(f"/papers/{paper.id}/files/{paper_file.id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert deleted == {"bucket": "talalm-test", "key": f"papers/{paper.id}/source/main.tex"}
    db_session.expire_all()
    assert db_session.get(PaperFile, paper_file_id) is None


def test_delete_paper_folder_removes_nested_files(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    first = PaperFileFactory(paper=paper, path="source/sections/intro.tex", storage_key=f"papers/{paper.id}/source/sections/intro.tex")
    second = PaperFileFactory(paper=paper, path="source/sections/method.tex", storage_key=f"papers/{paper.id}/source/sections/method.tex")
    sibling = PaperFileFactory(paper=paper, path="source/main.tex", storage_key=f"papers/{paper.id}/source/main.tex")
    first_id = first.id
    second_id = second.id
    sibling_id = sibling.id
    deleted_keys = []
    monkeypatch.setattr(
        "app.operations.papers.destroy_folder.delete_file",
        lambda settings, key: deleted_keys.append(key),
    )

    response = client.delete(
        f"/papers/{paper.id}/folders",
        headers=_headers(app, user),
        params={"path": "source/sections"},
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "deleted_count": 2}
    assert sorted(deleted_keys) == sorted([first.storage_key, second.storage_key])
    db_session.expire_all()
    assert db_session.get(PaperFile, first_id) is None
    assert db_session.get(PaperFile, second_id) is None
    assert db_session.get(PaperFile, sibling_id) is not None


def test_delete_paper_folder_rejects_path_traversal(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    deleted_keys = []
    monkeypatch.setattr(
        "app.operations.papers.destroy_folder.delete_file",
        lambda settings, key: deleted_keys.append(key),
    )

    response = client.delete(
        f"/papers/{paper.id}/folders",
        headers=_headers(app, user),
        params={"path": "../source"},
    )

    assert response.status_code == 422
    assert response.json()["path"] == ["invalid"]
    assert deleted_keys == []


def test_get_paper_file_content_returns_editable_text(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(paper=paper, path="source/main.tex", storage_key="papers/paper/source/main.tex")

    class Body:
        def read(self):
            return b"\\documentclass{article}"

    monkeypatch.setattr(
        "app.operations.papers.file_content.get_file",
        lambda settings, key: {"Body": Body(), "ContentType": "application/x-tex"},
    )

    response = client.get(f"/papers/{paper.id}/files/{paper_file.id}/content", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {
        "file": paper_file.to_dict(),
        "editable": True,
        "content": "\\documentclass{article}",
        "message": None,
    }


def test_get_paper_file_content_returns_binary_metadata_without_content(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(
        paper=paper,
        path="assets/figure.png",
        filename="figure.png",
        content_type="image/png",
    )
    fetched = {"called": False}
    monkeypatch.setattr(
        "app.operations.papers.file_content.get_file",
        lambda settings, key: fetched.update({"called": True}),
    )

    response = client.get(f"/papers/{paper.id}/files/{paper_file.id}/content", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["editable"] is False
    assert response.json()["content"] is None
    assert response.json()["message"] == "This file type cannot be edited."
    assert fetched == {"called": False}


def test_update_paper_file_content_persists_to_rustfs(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(paper=paper, path="source/main.tex", storage_key="papers/paper/source/main.tex")
    captured = {}

    def fake_store_file_at_key(upload, settings, key, filename=None):
        captured["body"] = upload.file.read()
        captured["key"] = key
        captured["filename"] = filename
        captured["content_type"] = upload.content_type
        return {
            "key": key,
            "filename": filename,
            "content_type": upload.content_type,
            "byte_size": None,
            "url": "http://localhost/object",
        }

    monkeypatch.setattr("app.operations.papers.file_content.store_file_at_key", fake_store_file_at_key)

    response = client.put(
        f"/papers/{paper.id}/files/{paper_file.id}/content",
        headers=_headers(app, user),
        json={"content": "\\section{Updated}"},
    )

    assert response.status_code == 200
    assert response.json()["content"] == "\\section{Updated}"
    assert response.json()["editable"] is True
    assert captured == {
        "body": b"\\section{Updated}",
        "key": "papers/paper/source/main.tex",
        "filename": "main.tex",
        "content_type": "application/x-tex",
    }
    db_session.expire_all()
    assert db_session.get(PaperFile, paper_file.id).size == len(b"\\section{Updated}")


def test_update_paper_file_content_rejects_stale_updated_at(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(paper=paper, path="source/main.tex")
    stored = {"called": False}
    monkeypatch.setattr(
        "app.operations.papers.file_content.store_file_at_key",
        lambda upload, settings, key, filename=None: stored.update({"called": True}),
    )

    response = client.put(
        f"/papers/{paper.id}/files/{paper_file.id}/content",
        headers=_headers(app, user),
        json={
            "content": "\\section{Updated}",
            "last_known_updated_at": "2000-01-01T00:00:00",
        },
    )

    assert response.status_code == 409
    assert response.json()["message"] == "This file was changed elsewhere. Please reload before saving."
    assert stored == {"called": False}


def test_update_paper_file_content_rejects_binary_file(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(paper=paper, path="assets/figure.png", filename="figure.png")
    stored = {"called": False}
    monkeypatch.setattr(
        "app.operations.papers.file_content.store_file_at_key",
        lambda upload, settings, key, filename=None: stored.update({"called": True}),
    )

    response = client.put(
        f"/papers/{paper.id}/files/{paper_file.id}/content",
        headers=_headers(app, user),
        json={"content": "not image bytes"},
    )

    assert response.status_code == 422
    assert response.json()["file"] == ["not editable"]
    assert stored == {"called": False}


def test_update_paper_file_content_rejects_too_large_content(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(paper=paper, path="source/main.tex")
    app.state.settings.STORAGE_MAX_CONTENT_LENGTH_MB = 1
    stored = {"called": False}
    monkeypatch.setattr(
        "app.operations.papers.file_content.store_file_at_key",
        lambda upload, settings, key, filename=None: stored.update({"called": True}),
    )

    response = client.put(
        f"/papers/{paper.id}/files/{paper_file.id}/content",
        headers=_headers(app, user),
        json={"content": "x" * (1024 * 1024 + 1)},
    )

    assert response.status_code == 422
    assert response.json()["content"] == ["too large"]
    assert stored == {"called": False}


def test_get_paper_file_content_hides_other_users_paper(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory()
    paper_file = PaperFileFactory(paper=paper)
    fetched = {"called": False}
    monkeypatch.setattr(
        "app.operations.papers.file_content.get_file",
        lambda settings, key: fetched.update({"called": True}),
    )

    response = client.get(f"/papers/{paper.id}/files/{paper_file.id}/content", headers=_headers(app, user))

    assert response.status_code == 404
    assert fetched == {"called": False}
