from app.models.notebook_note import NotebookNote
from spec.factories import NotebookFactory, NotebookNoteFactory


def test_notebook_note_factory_creates_notebook_note(db_session):
    notebook = NotebookFactory()
    notebook_note = NotebookNoteFactory(
        notebook=notebook,
        name="Saved Response",
        data={"response": "Model answer", "prompt": "Question"},
        is_context=True,
    )

    assert notebook_note.id is not None
    assert notebook_note.notebook_id == notebook.id
    assert notebook_note.notebook == notebook
    assert notebook_note.name == "Saved Response"
    assert notebook_note.data == {"response": "Model answer", "prompt": "Question"}
    assert notebook_note.is_context is True
    assert notebook_note.created_at is not None
    assert notebook_note.updated_at is not None


def test_notebook_note_defaults(db_session):
    notebook = NotebookFactory()
    notebook_note = NotebookNote(notebook=notebook, name="Defaulted Note")

    db_session.add(notebook_note)
    db_session.commit()

    assert notebook_note.data == {}
    assert notebook_note.is_context is None


def test_notebook_note_to_dict_returns_public_fields(db_session):
    notebook_note = NotebookNoteFactory(
        name="Saved Summary",
        data={"content": "Summary"},
        is_context=True,
    )

    assert notebook_note.to_dict() == {
        "id": notebook_note.id,
        "notebook_id": notebook_note.notebook_id,
        "name": "Saved Summary",
        "data": {"content": "Summary"},
        "is_context": True,
    }


def test_notebook_has_many_notes(db_session):
    notebook = NotebookFactory()
    first_note = NotebookNoteFactory(notebook=notebook)
    second_note = NotebookNoteFactory(notebook=notebook)

    assert {note.id for note in notebook.notes} == {first_note.id, second_note.id}
