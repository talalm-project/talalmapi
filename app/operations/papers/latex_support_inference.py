from sqlalchemy import select

from app.models.connector import Connector
from app.models.paper_file import PaperFile
from app.operations.agentic.latex_support_inference import LatexSupportInference as AgentLatexSupportInference
from app.operations.papers.access import visible_paper


class LatexSupportInference:
    def __init__(self, session, user, paper_id, user_prompt, note_ids=None, document_ids=None):
        self.session = session
        self.user = user
        self.paper_id = paper_id
        self.user_prompt = user_prompt
        self.note_ids = note_ids or []
        self.document_ids = document_ids or []
        self.paper = None
        self.connector = None
        self.document_references = []
        self.notes_references = []
        self.payload = None
        self.errors = {}

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        self.connector = self._connector()
        self.document_references = self._document_references()
        self.notes_references = self._notes_references()
        self.errors = self._validation_errors()
        if self.errors:
            return

        operation = AgentLatexSupportInference(
            connector=self.connector,
            document_references=self.document_references,
            notes_references=self.notes_references,
            user_prompt=self.user_prompt,
        )
        operation.execute()
        if not operation.valid():
            self.errors = operation.errors
            return

        self.payload = operation.payload

    def found(self):
        return self.paper is not None

    def valid(self):
        return not self.errors

    def _validation_errors(self):
        errors = {}
        if self.connector is None:
            errors["connector"] = ["required"]
        if not isinstance(self.user_prompt, str) or not self.user_prompt.strip():
            errors["user_prompt"] = ["required"]
        if not isinstance(self.document_ids, list):
            errors["document_ids"] = ["invalid"]
        elif len(self.document_references) != len(set(self.document_ids)):
            errors["document_ids"] = ["invalid"]
        if not isinstance(self.note_ids, list):
            errors["note_ids"] = ["invalid"]
        elif len(self.notes_references) != len(set(self.note_ids)):
            errors["note_ids"] = ["invalid"]

        return errors

    def _connector(self):
        connector_id = (self.paper.data or {}).get("connector_id")
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

    def _document_references(self):
        if not self.document_ids or not isinstance(self.document_ids, list):
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
        if not self.note_ids or not isinstance(self.note_ids, list):
            return []

        notes_by_id = {}
        for note in (self.paper.data or {}).get("notes", []):
            if isinstance(note, dict) and note.get("id"):
                notes_by_id[str(note["id"])] = note

        return [notes_by_id[note_id] for note_id in self.note_ids if note_id in notes_by_id]
