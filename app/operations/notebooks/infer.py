from app.models.notebook import DEFAULT_NOTEBOOK_SYSTEM_PROMPT
from app.models.notebook_file import NotebookFile
from app.models.notebook_note import NotebookNote
from app.operations.connectors.infer import Infer as ConnectorInfer
from app.operations.notebooks.access import visible_notebook
from app.operations.notebooks.build_rag_payload import BuildRagPayload
from app.operations.notebooks.retrieve_context import RetrieveContext


class Infer:
    def __init__(self, session, user, notebook_id, payload):
        self.session = session
        self.user = user
        self.notebook_id = notebook_id
        self.payload = payload
        self.notebook = None
        self.response = None
        self.errors = {}

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        if self.notebook is None:
            return

        current_question = _current_question_from_payload(self.payload)
        query = _query_from_payload(self.payload, current_question=current_question)
        retrieve_operation = RetrieveContext(
            session=self.session,
            notebook=self.notebook,
            query=query,
            k=self.payload.k,
            target_query=current_question,
        )
        retrieve_operation.execute()
        if not retrieve_operation.valid():
            self.errors = retrieve_operation.errors
            return

        system_prompt = self.notebook.system_prompt or DEFAULT_NOTEBOOK_SYSTEM_PROMPT
        payload_operation = BuildRagPayload(
            self.payload,
            retrieve_operation.chunks,
            connector=self.notebook.connector,
            system_prompt=system_prompt,
            context_notes=self._context_notes(),
        )
        payload_operation.execute()

        operation = ConnectorInfer(self.notebook.connector, payload_operation.rag_payload)
        operation.execute()
        if not operation.valid():
            self.errors = operation.errors
            return

        self.response = operation.response
        if isinstance(self.response, dict):
            self.response["sources"] = self._sources_from_chunks(retrieve_operation.chunks)

    def found(self):
        return self.notebook is not None

    def valid(self):
        return not self.errors

    def _sources_from_chunks(self, chunks):
        notebook_file_ids = []
        for chunk in chunks:
            notebook_file_id = chunk.get("notebook_file_id")
            if notebook_file_id and notebook_file_id not in notebook_file_ids:
                notebook_file_ids.append(notebook_file_id)

        if not notebook_file_ids:
            return []

        notebook_files = self.session.query(NotebookFile).filter(NotebookFile.id.in_(notebook_file_ids)).all()
        notebook_files_by_id = {notebook_file.id: notebook_file for notebook_file in notebook_files}

        return [
            _source_payload(notebook_files_by_id[notebook_file_id])
            for notebook_file_id in notebook_file_ids
            if notebook_file_id in notebook_files_by_id
        ]

    def _context_notes(self):
        return (
            self.session.query(NotebookNote)
            .filter(NotebookNote.notebook_id == self.notebook.id, NotebookNote.is_context.is_(True))
            .order_by(NotebookNote.created_at.desc())
            .all()
        )


def _query_from_payload(payload, current_question=None):
    if isinstance(payload.prompt, str):
        return payload.prompt

    if isinstance(payload.input, str):
        return payload.input

    if isinstance(payload.input, list):
        current_question = current_question or _current_question_from_payload(payload)
        previous_messages = []
        current_user_seen = False
        for message in reversed(payload.input):
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            content = message.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
                continue

            if role == "user" and not current_user_seen and content == current_question:
                current_user_seen = True
                continue

            label = "User" if role == "user" else "Assistant"
            previous_messages.append(f"{label}: {content}")
            if len(previous_messages) >= 4:
                break

        if current_question and previous_messages:
            return "\n\n".join(
                [
                    "Current question:",
                    current_question,
                    "Recent conversation:",
                    "\n".join(reversed(previous_messages)),
                ]
            )

        if current_question:
            return current_question

    return ""


def _current_question_from_payload(payload):
    if isinstance(payload.prompt, str):
        return payload.prompt

    if isinstance(payload.input, str):
        return payload.input

    if isinstance(payload.input, list):
        for message in reversed(payload.input):
            if isinstance(message, dict) and message.get("role") == "user" and isinstance(message.get("content"), str):
                return message["content"]

    return ""


def _source_payload(notebook_file):
    data = notebook_file.data or {}
    return {
        "id": notebook_file.id,
        "name": notebook_file.name,
        "filename": notebook_file.filename,
        "content_type": notebook_file.content_type,
        "byte_size": notebook_file.byte_size,
        "url": data.get("url"),
    }
