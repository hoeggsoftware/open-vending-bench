"""
Simple in-memory vector database using term-frequency cosine similarity.
No external dependencies required.
"""
import math
from collections import Counter


class SimpleVectorDB:
    def __init__(self):
        self.documents = []  # List of {"id": int, "text": str, "terms": Counter}
        self.next_id = 0

    def _tokenize(self, text: str) -> list:
        """Simple whitespace + lowercase tokenization"""
        return text.lower().split()

    def _cosine_similarity(self, a: Counter, b: Counter) -> float:
        """Compute cosine similarity between two term-frequency vectors"""
        common = set(a.keys()) & set(b.keys())
        if not common:
            return 0.0
        dot = sum(a[k] * b[k] for k in common)
        mag_a = math.sqrt(sum(v * v for v in a.values()))
        mag_b = math.sqrt(sum(v * v for v in b.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def add(self, text: str) -> str:
        """Add a document to the vector database"""
        terms = Counter(self._tokenize(text))
        doc_id = self.next_id
        self.next_id += 1
        self.documents.append({"id": doc_id, "text": text, "terms": terms})
        return f"Added document {doc_id} to vector DB ({len(self.documents)} total)"

    def search(self, query: str, top_k: int = 3) -> str:
        """Search for documents similar to the query"""
        if not self.documents:
            return "Vector DB is empty."
        query_terms = Counter(self._tokenize(query))
        scored = []
        for doc in self.documents:
            sim = self._cosine_similarity(query_terms, doc["terms"])
            scored.append((sim, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = scored[:top_k]
        lines = []
        for sim, doc in results:
            if sim > 0:
                lines.append(f"[Score: {sim:.3f}] {doc['text']}")
        if not lines:
            return "No relevant results found."
        return "\n".join(lines)
