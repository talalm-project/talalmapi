import json

from app.schemas.connector import ConnectorInfer
from app.operations.connectors.metadata import inference_context_window_tokens, inference_default_output_tokens

MAX_CONVERSATION_CONTEXT_CHARS = 1200
MAX_NOTE_CONTEXT_CHARS = 4000
CONVERSATION_CONTEXT_POLICY = (
    "Use this conversation context to resolve follow-up references like 'this' and to transform prior answers. "
    "Keep factual claims grounded in the notebook context."
)


class BuildRagPayload:
    def __init__(self, payload, chunks, connector=None, system_prompt=None, context_notes=None):
        self.payload = payload
        self.chunks = chunks or []
        self.connector = connector
        self.system_prompt = system_prompt or ""
        self.context_notes = context_notes or []
        self.rag_payload = None

    def execute(self):
        contextualized_prompt = self._contextualized_prompt()
        if self._local_connector():
            self.rag_payload = ConnectorInfer(
                prompt=contextualized_prompt,
                input=None,
                model=self.payload.model,
                options=self._options(),
                k=self.payload.k,
            )
            return

        self.rag_payload = ConnectorInfer(
            prompt=contextualized_prompt if self.payload.prompt is not None and self.payload.input is None else self.payload.prompt,
            input=self._contextualized_input(contextualized_prompt),
            model=self.payload.model,
            options=self._options(),
            k=self.payload.k,
        )

    def _contextualized_input(self, contextualized_prompt):
        if self.payload.input is None:
            return None

        if isinstance(self.payload.input, str):
            return contextualized_prompt

        if isinstance(self.payload.input, list):
            return self._contextualized_messages(contextualized_prompt)

        return self.payload.input

    def _contextualized_messages(self, contextualized_prompt):
        if self._local_connector():
            return [{"role": "user", "content": contextualized_prompt}]

        messages = list(self.payload.input)
        for index in range(len(messages) - 1, -1, -1):
            message = messages[index]
            if isinstance(message, dict) and message.get("role") == "user":
                messages[index] = {**message, "content": self._contextualized_content(message.get("content"))}
                return messages

        return [*messages, {"role": "user", "content": contextualized_prompt}]

    def _contextualized_content(self, content):
        if isinstance(content, str):
            return self._format_context(content)

        return self._contextualized_prompt()

    def _contextualized_prompt(self):
        query = self.payload.prompt
        if query is None and isinstance(self.payload.input, str):
            query = self.payload.input
        if query is None and isinstance(self.payload.input, list):
            query = _last_user_text(self.payload.input)

        return self._format_context(query or "")

    def _format_context(self, query):
        sections = []
        if self._local_connector() and self.system_prompt:
            sections.extend(["Instructions:", self.system_prompt])

        conversation_context = self._conversation_context()
        if conversation_context:
            sections.extend(["Conversation context policy:", CONVERSATION_CONTEXT_POLICY])
            sections.extend(["Conversation context:", conversation_context])

        formatted_notes = self._formatted_context_notes()
        if formatted_notes:
            sections.extend(["Notebook notes context:", formatted_notes])

        sections.extend(["Notebook context:", self._formatted_chunks(), "User question:", query])
        return "\n\n".join(sections)

    def _formatted_context_notes(self):
        if not self.context_notes:
            return ""

        formatted = []
        used_chars = 0
        for index, note in enumerate(self.context_notes, start=1):
            text = _note_text(note)
            if not text:
                continue

            name = getattr(note, "name", None) or f"Note {index}"
            prefix = f"[Note {index}: {name}] "
            separator = "\n\n" if formatted else ""
            remaining = MAX_NOTE_CONTEXT_CHARS - used_chars - len(separator) - len(prefix)
            if remaining <= 0:
                break

            if len(text) > remaining:
                text = text[: max(remaining - 14, 0)].rstrip() + " [truncated]"

            entry = f"{prefix}{text}"
            formatted.append(entry)
            used_chars += len(separator) + len(entry)

        return "\n\n".join(formatted)

    def _formatted_chunks(self):
        if not self.chunks:
            return "No relevant notebook context was retrieved."

        budget = self._context_char_budget()
        formatted = []
        used_chars = 0

        for index, chunk in enumerate(self.chunks, start=1):
            text = str(chunk["text"])
            prefix = f"[{index}] "
            separator = "\n\n" if formatted else ""
            remaining = budget - used_chars - len(separator) - len(prefix)
            if remaining <= 0:
                break

            if len(text) > remaining:
                text = text[: max(remaining - 14, 0)].rstrip() + " [truncated]"

            entry = f"{prefix}{text}"
            formatted.append(entry)
            used_chars += len(separator) + len(entry)

        if not formatted:
            return "No relevant notebook context fit within the model context window."

        return "\n\n".join(formatted)

    def _context_char_budget(self):
        if not self._local_connector():
            return 12000

        context_window = _local_context_window(self.connector)
        output_tokens = _safe_output_tokens(self.connector, self.payload.options)
        fixed_prompt = "\n\n".join(
            [
                "Notebook context:",
                "",
                "Conversation context:",
                CONVERSATION_CONTEXT_POLICY,
                self._conversation_context(),
                "Notebook notes context:",
                self._formatted_context_notes(),
                "User question:",
                self._query_text(),
                self.system_prompt,
            ]
        )
        fixed_tokens = _estimated_tokens(fixed_prompt)
        reserved_tokens = 128
        available_tokens = context_window - output_tokens - fixed_tokens - reserved_tokens
        return max(available_tokens, 16) * 2

    def _options(self):
        options = dict(self.payload.options)
        if not self._local_connector():
            return options

        safe_output_tokens = _safe_output_tokens(self.connector, options)
        if options.get("max_tokens") != safe_output_tokens:
            options["max_tokens"] = safe_output_tokens

        return options

    def _query_text(self):
        query = self.payload.prompt
        if query is None and isinstance(self.payload.input, str):
            query = self.payload.input
        if query is None and isinstance(self.payload.input, list):
            query = _last_user_text(self.payload.input)

        return query or ""

    def _conversation_context(self):
        if not isinstance(self.payload.input, list):
            return ""

        current_user_seen = False
        records = []
        for message in reversed(self.payload.input):
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            content = message.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
                continue

            if role == "user" and not current_user_seen:
                current_user_seen = True
                continue

            label = "User" if role == "user" else "Assistant"
            records.append(f"{label}: {_compact_text(content, 420)}")
            if len("\n".join(reversed(records))) >= MAX_CONVERSATION_CONTEXT_CHARS:
                break

        if not records:
            return ""

        context = "\n".join(reversed(records))
        if len(context) > MAX_CONVERSATION_CONTEXT_CHARS:
            context = context[:MAX_CONVERSATION_CONTEXT_CHARS].rstrip() + " [truncated]"

        return context

    def _local_connector(self):
        return self.connector is not None


def _last_user_text(messages):
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]

    return ""


def _local_context_window(connector):
    return inference_context_window_tokens(connector)


def _safe_output_tokens(connector, options):
    context_window = _local_context_window(connector)
    requested = options.get("max_tokens")
    if isinstance(requested, int) and requested > 0:
        return min(requested, max(context_window // 4, 1))

    default_tokens = inference_default_output_tokens(connector, 1024)
    return min(default_tokens, max(context_window // 4, 1))


def _estimated_tokens(text):
    return max(len(text) // 4, 1)


def _compact_text(value, max_chars=None):
    compacted = " ".join(value.split())
    if max_chars is not None and len(compacted) > max_chars:
        return compacted[: max(max_chars - 14, 0)].rstrip() + " [truncated]"

    return compacted


def _note_text(note):
    data = getattr(note, "data", None) or {}
    if isinstance(data.get("content"), str):
        return _compact_text(data["content"])

    blocks = data.get("blocks")
    if isinstance(blocks, list):
        texts = []
        for block in blocks:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                texts.append(block["text"])
        if texts:
            return _compact_text("\n".join(texts))

    response = data.get("response")
    if isinstance(response, str):
        return _compact_text(response)

    if response is not None:
        return _compact_text(json.dumps(response, sort_keys=True))

    if data:
        return _compact_text(json.dumps(data, sort_keys=True))

    return ""
