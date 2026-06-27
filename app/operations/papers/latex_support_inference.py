from app.operations.agentic.latex_support_inference import LatexSupportInference as AgentLatexSupportInference
from app.operations.papers.access import visible_paper
from app.operations.papers.validate_latex_support_inference import ValidateLatexSupportInference


class LatexSupportInference:
    def __init__(
        self,
        session,
        user,
        paper_id,
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
        self.paper_id = paper_id
        self.user_prompt = user_prompt
        self.connector_id = connector_id
        self.note_ids = [] if note_ids is None else note_ids
        self.document_ids = [] if document_ids is None else document_ids
        self.notebook_id = notebook_id
        self.notebook_note_ids = [] if notebook_note_ids is None else notebook_note_ids
        self.notebook_file_ids = [] if notebook_file_ids is None else notebook_file_ids
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

        validation = ValidateLatexSupportInference(
            session=self.session,
            user=self.user,
            paper=self.paper,
            user_prompt=self.user_prompt,
            connector_id=self.connector_id,
            note_ids=self.note_ids,
            document_ids=self.document_ids,
            notebook_id=self.notebook_id,
            notebook_note_ids=self.notebook_note_ids,
            notebook_file_ids=self.notebook_file_ids,
        )
        validation.execute()
        if not validation.valid():
            self.errors = validation.errors
            return

        self.connector = validation.connector
        self.document_references = validation.document_references
        self.notes_references = validation.notes_references
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
