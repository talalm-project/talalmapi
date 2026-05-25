from app.models.notebook_file import ALLOWED_NOTEBOOK_FILE_STATUSES, NotebookFile
from spec.factories import NotebookFactory, NotebookFileFactory


def test_notebook_file_factory_creates_notebook_file(db_session):
    notebook = NotebookFactory()
    notebook_file = NotebookFileFactory(
        notebook=notebook,
        name="Policy Notes",
        filename="policy.pdf",
        content_type="application/pdf",
        byte_size=2048,
        checksum="abc123",
        data={"pages": 10},
    )

    assert notebook_file.id is not None
    assert notebook_file.notebook_id == notebook.id
    assert notebook_file.notebook == notebook
    assert notebook_file.name == "Policy Notes"
    assert notebook_file.filename == "policy.pdf"
    assert notebook_file.content_type == "application/pdf"
    assert notebook_file.byte_size == 2048
    assert notebook_file.object_key
    assert notebook_file.object_key != notebook_file.filename
    assert notebook_file.checksum == "abc123"
    assert notebook_file.status == "pending"
    assert notebook_file.error_message is None
    assert notebook_file.data == {"pages": 10}
    assert notebook_file.created_at is not None
    assert notebook_file.updated_at is not None


def test_notebook_file_defaults(db_session):
    notebook = NotebookFactory()
    notebook_file = NotebookFile(
        notebook=notebook,
        name="Defaulted File",
        filename="defaulted.txt",
    )

    db_session.add(notebook_file)
    db_session.commit()

    assert notebook_file.object_key
    assert notebook_file.status == "pending"
    assert notebook_file.data == {}


def test_notebook_file_to_dict_returns_public_fields(db_session):
    notebook_file = NotebookFileFactory(
        name="Research",
        filename="research.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        byte_size=4096,
        checksum="checksum",
        status="active",
        error_message=None,
        data={"paragraphs": 12},
    )

    assert notebook_file.to_dict() == {
        "id": notebook_file.id,
        "notebook_id": notebook_file.notebook_id,
        "name": "Research",
        "filename": "research.docx",
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "byte_size": 4096,
        "object_key": notebook_file.object_key,
        "checksum": "checksum",
        "status": "active",
        "error_message": None,
        "data": {"paragraphs": 12},
    }


def test_notebook_has_many_files(db_session):
    notebook = NotebookFactory()
    first_file = NotebookFileFactory(notebook=notebook)
    second_file = NotebookFileFactory(notebook=notebook)

    assert {notebook_file.id for notebook_file in notebook.files} == {first_file.id, second_file.id}


def test_allowed_notebook_file_statuses():
    assert ALLOWED_NOTEBOOK_FILE_STATUSES == {
        "pending",
        "uploading",
        "uploaded",
        "processing",
        "active",
        "failed",
    }
