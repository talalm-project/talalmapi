from time import perf_counter

from app.operations.connectors.metadata import (
    inference_default_output_tokens,
    inference_local_file_path,
    inference_model_name,
    inference_model_options,
)
from app.services.llama_model_cache import llama_model_cache


DEFAULT_LOCAL_MAX_TOKENS = 1024


class Infer:
    def __init__(self, connector, payload, system_prompt=None):
        self.connector = connector
        self.payload = payload
        self.system_prompt = system_prompt
        self.errors = {}
        self.response = None

    def execute(self):
        self.errors = self._validation_errors()
        if self.errors:
            return

        if self.connector.connection_type == "local":
            self.response = self._infer_local()
            return

        if self.connector.connection_type == "openai":
            self.response = self._infer_openai()
            return

        self.errors = {"connection_type": ["unsupported"]}

    def valid(self):
        return not self.errors

    def _validation_errors(self):
        errors = {}

        if not isinstance(self.payload.options, dict):
            errors["options"] = ["invalid"]

        if self.connector.connection_type == "local":
            local_file_path = inference_local_file_path(self.connector)
            if not local_file_path:
                errors["local_file_path"] = ["required"]
            elif not local_file_path.lower().endswith(".gguf"):
                errors["local_file_path"] = ["must be a .gguf model"]
            if self.payload.input is not None and not isinstance(self.payload.input, (str, list)):
                errors["input"] = ["invalid"]
            if self.payload.input is not None and isinstance(self.payload.input, list) and not self.payload.input:
                errors["input"] = ["required"]
            if self.payload.input is None and (not isinstance(self._local_prompt(), str) or not self._local_prompt().strip()):
                errors["prompt"] = ["required"]

        if self.connector.connection_type == "openai":
            if not self.connector.api_key:
                errors["api_key"] = ["required"]
            if self._openai_input() is None:
                errors["input"] = ["required"]

        return errors

    def _infer_local(self):
        model_options = inference_model_options(self.connector)
        llama_class = _llama_class()
        cached_model = llama_model_cache.get(llama_class, inference_local_file_path(self.connector), model_options)
        options = {"max_tokens": inference_default_output_tokens(self.connector, DEFAULT_LOCAL_MAX_TOKENS), **self.payload.options}
        started_at = perf_counter()
        try:
            with cached_model.lock:
                response = cached_model.llm.create_chat_completion(messages=self._local_messages(), **options)
        except ValueError as error:
            self.errors = {"inference": [str(error)]}
            return None
        return _response_with_details(response, perf_counter() - started_at)

    def _infer_openai(self):
        openai_client_class = _openai_client_class()
        client = openai_client_class(api_key=self.connector.api_key)
        options = dict(self.payload.options)
        if self.system_prompt and "instructions" not in options:
            options["instructions"] = self.system_prompt

        started_at = perf_counter()
        response = _serialize_response(
            client.responses.create(model=self.payload.model or inference_model_name(self.connector), input=self._openai_input(), **options)
        )
        return _response_with_details(response, perf_counter() - started_at)

    def _local_prompt(self):
        if self.payload.prompt is not None:
            return self.payload.prompt

        if isinstance(self.payload.input, str):
            return self.payload.input

        return None

    def _local_messages(self):
        if isinstance(self.payload.input, list):
            messages = self.payload.input
        else:
            messages = [{"role": "user", "content": self._local_prompt()}]

        if self.system_prompt and not _has_system_message(messages):
            return [{"role": "system", "content": self.system_prompt}, *messages]

        return messages

    def _openai_input(self):
        if self.payload.input is not None:
            return self.payload.input

        return self.payload.prompt


def _serialize_response(response):
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")

    if hasattr(response, "dict"):
        return response.dict()

    return response


def _response_with_details(response, elapsed_seconds):
    details = _response_details(response, elapsed_seconds)
    return {
        "response": response,
        "details": details,
    }


def _response_details(response, elapsed_seconds):
    usage = _get_value(response, "usage") or {}
    prompt_tokens = _first_present(usage, ["prompt_tokens", "input_tokens"])
    completion_tokens = _first_present(usage, ["completion_tokens", "output_tokens"])
    total_tokens = _first_present(usage, ["total_tokens"])
    if total_tokens is None:
        total_tokens = _sum_tokens(prompt_tokens, completion_tokens)

    measured_tokens = completion_tokens if completion_tokens is not None else total_tokens
    tokens_per_second = None
    if measured_tokens is not None and elapsed_seconds > 0:
        tokens_per_second = measured_tokens / elapsed_seconds

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "finish_reason": _finish_reason(response),
        "elapsed_seconds": elapsed_seconds,
        "tokens_per_second": tokens_per_second,
    }


def _first_present(source, keys):
    for key in keys:
        value = _get_value(source, key)
        if value is not None:
            return value

    return None


def _get_value(source, key):
    if isinstance(source, dict):
        return source.get(key)

    return getattr(source, key, None)


def _sum_tokens(*values):
    numeric_values = [value for value in values if isinstance(value, int)]
    if not numeric_values:
        return None

    return sum(numeric_values)


def _finish_reason(response):
    choices = _get_value(response, "choices") or []
    if not choices:
        return None

    return _get_value(choices[0], "finish_reason")


def _has_system_message(messages):
    return any(message.get("role") in {"system", "developer"} for message in messages if isinstance(message, dict))


def _llama_class():
    from llama_cpp import Llama

    return Llama


def _openai_client_class():
    from openai import OpenAI

    return OpenAI
