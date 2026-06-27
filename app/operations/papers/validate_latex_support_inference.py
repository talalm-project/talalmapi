from sqlalchemy import select

from app.models.connector import Connector
from app.models.notebook_file import NotebookFile
from app.models.notebook_note import NotebookNote
from app.models.paper_file import PaperFile
from app.operations.notebooks.access import visible_notebook


class ValidateLatexSupportInference:
    def __init__(
        self,
        session,
        user,
        paper,
        user_prompt,
        connector_id=None,
        note_ids=None,
        document_ids=None,
        notebook_id=None,
        notebook_note_ids=None,
        notebook_file_ids=None,
    ):
        self.session = session
        self.user = user
        self.paper = paper
        self.user_prompt = user_prompt
        self.connector_id = connector_id
        self.note_ids = [] if note_ids is None else note_ids
        self.document_ids = [] if document_ids is None else document_ids
        self.notebook_id = notebook_id
        self.notebook_note_ids = [] if notebook_note_ids is None else notebook_note_ids
        self.notebook_file_ids = [] if notebook_file_ids is None else notebook_file_ids
        self.notebook = None
        self.connector = None
        self.document_references = []
        self.notes_references = []
        self.errors = {}

    def execute(self):
        self.errors = self._input_errors()
        if self.errors:
            return

        self.connector = self._connector()
        self.notebook = self._notebook()
        self.document_references = [*self._document_references(), *self._notebook_file_references()]
        self.notes_references = [*self._notes_references(), *self._notebook_note_references()]
        self.errors = self._reference_errors()

    def valid(self):
        return not self.errors

    def _input_errors(self):
        errors = {}
        if self.paper is None:
            errors["paper"] = ["required"]
        if self.connector_id is not None and (not isinstance(self.connector_id, str) or not self.connector_id.strip()):
            errors["connector_id"] = ["invalid"]
        if not isinstance(self.user_prompt, str) or not self.user_prompt.strip():
            errors["user_prompt"] = ["required"]
        if not _valid_id_list(self.document_ids):
            errors["document_ids"] = ["invalid"]
        if not _valid_id_list(self.note_ids):
            errors["note_ids"] = ["invalid"]
        if self.notebook_id is not None and (not isinstance(self.notebook_id, str) or not self.notebook_id.strip()):
            errors["notebook_id"] = ["invalid"]
        if not _valid_id_list(self.notebook_file_ids):
            errors["notebook_file_ids"] = ["invalid"]
        if not _valid_id_list(self.notebook_note_ids):
            errors["notebook_note_ids"] = ["invalid"]

        return errors

    def _reference_errors(self):
        errors = {}
        explicit_connector_id = self.connector_id is not None
        if explicit_connector_id and self.connector is None:
            errors["connector_id"] = ["not found"]
        elif self.connector is None:
            errors["connector"] = ["required"]

        document_references_count = _matching_reference_count(self.document_references, self.document_ids)
        notes_references_count = _matching_reference_count(self.notes_references, self.note_ids)
        if document_references_count != len(set(self.document_ids)):
            errors["document_ids"] = ["invalid"]
        if notes_references_count != len(set(self.note_ids)):
            errors["note_ids"] = ["invalid"]
        if self.notebook_id is None and (self.notebook_file_ids or self.notebook_note_ids):
            errors["notebook_id"] = ["required"]
        elif self.notebook_id is not None and self.notebook is None:
            errors["notebook_id"] = ["not found"]

        notebook_file_references_count = _matching_reference_count(self.document_references, self.notebook_file_ids)
        notebook_note_references_count = _matching_reference_count(self.notes_references, self.notebook_note_ids)
        if notebook_file_references_count != len(set(self.notebook_file_ids)):
            errors["notebook_file_ids"] = ["invalid"]
        if notebook_note_references_count != len(set(self.notebook_note_ids)):
            errors["notebook_note_ids"] = ["invalid"]

        return errors

    def _connector(self):
        connector_id = self.connector_id if self.connector_id is not None else (self.paper.data or {}).get("connector_id")
        if connector_id:
            return self.session.scalar(
                select(Connector).where(
                    Connector.id == connector_id,
                    Connector.user_id == self.user.id,
                )
            )

        return self.session.scalar(
            select(Connector)
            .where(Connector.user_id == self.user.id)
            .order_by(Connector.created_at.desc())
        )

    def _notebook(self):
        if self.notebook_id is None or not isinstance(self.notebook_id, str):
            return None

        return visible_notebook(self.session, self.notebook_id, self.user, admin_allowed=False)

    def _document_references(self):
        if not self.document_ids:
            return []

        rows = (
            self.session.execute(
                select(PaperFile).where(
                    PaperFile.paper_id == self.paper.id,
                    PaperFile.id.in_(self.document_ids),
                )
            )
            .scalars()
            .all()
        )
        files_by_id = {paper_file.id: paper_file for paper_file in rows}
        return [
            files_by_id[document_id].to_dict()
            for document_id in self.document_ids
            if document_id in files_by_id
        ]

    def _notes_references(self):
        if not self.note_ids:
            return []

        notes_by_id = {}
        for note in (self.paper.data or {}).get("notes", []):
            if isinstance(note, dict) and note.get("id"):
                notes_by_id[str(note["id"])] = note

        return [notes_by_id[note_id] for note_id in self.note_ids if note_id in notes_by_id]

    def _notebook_file_references(self):
        if not self.notebook_file_ids or self.notebook is None:
            return []

        rows = (
            self.session.execute(
                select(NotebookFile).where(
                    NotebookFile.notebook_id == self.notebook.id,
                    NotebookFile.id.in_(self.notebook_file_ids),
                )
            )
            .scalars()
            .all()
        )
        files_by_id = {notebook_file.id: notebook_file for notebook_file in rows}
        return [
            files_by_id[notebook_file_id].to_dict()
            for notebook_file_id in self.notebook_file_ids
            if notebook_file_id in files_by_id
        ]

    def _notebook_note_references(self):
        if not self.notebook_note_ids or self.notebook is None:
            return []

        rows = (
            self.session.execute(
                select(NotebookNote).where(
                    NotebookNote.notebook_id == self.notebook.id,
                    NotebookNote.id.in_(self.notebook_note_ids),
                )
            )
            .scalars()
            .all()
        )
        notes_by_id = {notebook_note.id: notebook_note for notebook_note in rows}
        return [
            notes_by_id[notebook_note_id].to_dict()
            for notebook_note_id in self.notebook_note_ids
            if notebook_note_id in notes_by_id
        ]


def _valid_id_list(value):
    if not isinstance(value, list):
        return False

    return all(isinstance(entry, str) and entry.strip() for entry in value)


def _matching_reference_count(references, ids):
    target_ids = set(ids)
    return len([
        reference
        for reference in references
        if isinstance(reference, dict) and reference.get("id") in target_ids
    ])
