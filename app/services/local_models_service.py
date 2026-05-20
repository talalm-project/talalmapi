from pathlib import Path

import yaml


class LocalModelsService:
    def __init__(self, manifest_path):
        self.manifest_path = Path(manifest_path)

    def list(self):
        if not self.manifest_path.exists():
            return []

        with self.manifest_path.open("r", encoding="utf-8") as handle:
            records = yaml.safe_load(handle) or []

        if not isinstance(records, list):
            return []

        return [
            {
                "name": record.get("name"),
                "path": record.get("path"),
            }
            for record in records
            if isinstance(record, dict)
        ]
