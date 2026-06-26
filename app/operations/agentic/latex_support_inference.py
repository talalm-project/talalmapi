import json
import re

from app.operations.connectors.infer import Infer as ConnectorInferOperation
from app.schemas.connector import ConnectorInfer


SYSTEM_PROMPT = (
    "You are a LaTeX support agent. Given the user prompt and the provided reference context, "
    "create a LaTeX snippet only. Return exactly one markdown fenced code block containing only LaTeX. "
    "Do not include explanations, prose, citations, analysis, or any text before or after the fenced code block."
)
DEFAULT_OPTIONS = {"temperature": 0}


class LatexSupportInference:
    def __init__(self, connector, document_references, notes_references, user_prompt, options=None):
        self.connector = connector
        self.document_references = document_references or []
        self.notes_references = notes_references or []
        self.user_prompt = user_prompt
        self.options = {} if options is None else options
        self.payload = None
        self.response = None
        self.errors = {}

    def execute(self):
        self.errors = self._validation_errors()
        if self.errors:
            return

        operation = ConnectorInferOperation(
            self.connector,
            ConnectorInfer(
                prompt=self.user_prompt.strip(),
                options={**DEFAULT_OPTIONS, **self.options},
            ),
            system_prompt=self._system_prompt(),
        )
        operation.execute()
        if not operation.valid():
            self.errors = operation.errors
            return

        self.response = operation.response
        message = _extract_assistant_text(self.response)
        content = _extract_latex_content(message)
        self.payload = {
            "message": _markdown_latex_block(content),
            "content": content,
        }

    def valid(self):
        return not self.errors

    def _validation_errors(self):
        errors = {}
        if self.connector is None:
            errors["connector"] = ["required"]
        if not isinstance(self.user_prompt, str) or not self.user_prompt.strip():
            errors["user_prompt"] = ["required"]
        if not isinstance(self.options, dict):
            errors["options"] = ["invalid"]

        return errors

    def _system_prompt(self):
        return "\n\n".join(
            [
                SYSTEM_PROMPT,
                "Document references:",
                _format_references(self.document_references),
                "Notes references:",
                _format_references(self.notes_references),
            ]
        )


def _format_references(references):
    if not references:
        return "None provided."

    formatted = []
    for index, reference in enumerate(references, start=1):
        formatted.append(f"[{index}] {_reference_text(reference)}")

    return "\n".join(formatted)


def _reference_text(reference):
    if hasattr(reference, "to_dict"):
        reference = reference.to_dict()
    elif not isinstance(reference, dict):
        reference = {
            key: getattr(reference, key)
            for key in ("id", "name", "title", "filename", "content", "data")
            if hasattr(reference, key)
        }

    if isinstance(reference, dict):
        return json.dumps(reference, ensure_ascii=True, sort_keys=True, default=str)

    return str(reference)


def _extract_assistant_text(response):
    response_body = _get_value(response, "response")
    if response_body is None:
        response_body = response

    choices = _get_value(response_body, "choices") or []
    if choices:
        message = _get_value(choices[0], "message") or {}
        content = _get_value(message, "content")
        if isinstance(content, str):
            return content.strip()

        text = _get_value(choices[0], "text")
        if isinstance(text, str):
            return text.strip()

    content = _get_value(response_body, "content")
    if isinstance(content, str):
        return content.strip()

    if isinstance(response_body, str):
        return response_body.strip()

    return ""


def _extract_latex_content(message):
    match = re.search(r"```(?:latex|tex)?\s*(.*?)```", message, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    return message.strip()


def _markdown_latex_block(content):
    return f"```latex\n{content}\n```"


def _get_value(source, key):
    if isinstance(source, dict):
        return source.get(key)

    return getattr(source, key, None)
