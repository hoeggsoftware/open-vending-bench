"""
Simple key-value store with JSON file persistence
"""
import json
import os


class KVStore:
    def __init__(self, persist_path: str = "kv_store.json", skip_file_load: bool = False):
        self.persist_path = persist_path
        self.data = {}
        if not skip_file_load:
            self._load()

    def _load(self):
        if os.path.exists(self.persist_path):
            with open(self.persist_path, "r") as f:
                self.data = json.load(f)

    def _save(self):
        with open(self.persist_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def get(self, key: str) -> str:
        if key not in self.data:
            return f"Key '{key}' not found."
        return str(self.data[key])

    def set(self, key: str, value: str) -> str:
        self.data[key] = value
        self._save()
        return f"Set '{key}' = '{value}'"

    def delete(self, key: str) -> str:
        if key not in self.data:
            return f"Key '{key}' not found."
        del self.data[key]
        self._save()
        return f"Deleted key '{key}'"
