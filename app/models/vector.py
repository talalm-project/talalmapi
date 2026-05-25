from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw):
        return "vector"

    def bind_processor(self, _dialect):
        def process(value):
            if value is None or isinstance(value, str):
                return value
            return "[" + ",".join(str(float(entry)) for entry in value) + "]"

        return process

    def result_processor(self, _dialect, _coltype):
        def process(value):
            if value is None or isinstance(value, list):
                return value
            if isinstance(value, memoryview):
                value = value.tobytes().decode("utf-8")
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            if isinstance(value, str):
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    content = value[1:-1].strip()
                    if not content:
                        return []
                    return [float(entry) for entry in content.split(",")]
            return value

        return process
