import hashlib
import json

from sqlalchemy import select

from app.models.embedding_config import EmbeddingConfig
from app.operations.connectors.metadata import embedding_local_file_path, embedding_model_name, embedding_model_options, embedding_size
from app.operations.validator import Validator


class Resolve(Validator):
    def __init__(self, session, connector, distance_metric="cosine"):
        super().__init__()
        self.session = session
        self.connector = connector
        self.distance_metric = distance_metric
        self.embedding_config = None
        self.payload = {
            "connector_id": [],
            "embedding_name": [],
            "embedding_dimensions": [],
        }

    def execute(self):
        self._validate()
        if self.invalid():
            return

        attrs = self._attrs()
        existing = self.session.scalar(
            select(EmbeddingConfig).where(EmbeddingConfig.config_hash == attrs["config_hash"])
        )
        if existing is not None:
            self.embedding_config = existing
            return

        self.embedding_config = EmbeddingConfig(**attrs)
        self.session.add(self.embedding_config)
        self.session.flush()

    def _validate(self):
        if self.connector is None:
            self.payload["connector_id"].append("required")
            self.count_errors()
            return

        if not embedding_model_name(self.connector):
            self.payload["embedding_name"].append("required")
        if not embedding_size(self.connector):
            self.payload["embedding_dimensions"].append("required")

        self.count_errors()

    def _attrs(self):
        options = embedding_model_options(self.connector)
        provider = "local"
        model_name = embedding_model_name(self.connector)
        model_path = embedding_local_file_path(self.connector)
        dimensions = embedding_size(self.connector)
        config_hash = _config_hash(
            {
                "connector_id": self.connector.id,
                "provider": provider,
                "model_name": model_name,
                "model_path": model_path,
                "dimensions": dimensions,
                "distance_metric": self.distance_metric,
                "options": options,
            }
        )

        return {
            "connector_id": self.connector.id,
            "provider": provider,
            "model_name": model_name,
            "model_path": model_path,
            "dimensions": dimensions,
            "distance_metric": self.distance_metric,
            "options": options,
            "config_hash": config_hash,
        }


def _config_hash(payload):
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
