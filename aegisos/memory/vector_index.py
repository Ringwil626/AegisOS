"""Vector Index - Phase 7: Persistent Intelligence Layer.

Builds embeddings ONLY from engineering_memory.
Do NOT embed source code or logs.

Uses simple deterministic hashing for Phase 7 baseline.
Production would use proper embedding model.
"""
import hashlib
import json
import sys
import os
from typing import List, Tuple

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(_current_dir)
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import get_all_memories, DB_PATH


class VectorIndex:
    """Simple vector index for engineering memory.
    
    For Phase 7 baseline, uses deterministic text hashing.
    Production would use sentence-transformers or similar.
    """
    
    def __init__(self):
        self.embeddings = {}  # memory_id -> vector
        self.dimension = 128  # Fixed dimension for hashing
    
    def _text_to_vector(self, text: str) -> List[float]:
        """Convert text to deterministic vector using hashing.
        
        This is a simple baseline for Phase 7.
        Production would use: model.encode(text)
        """
        # Normalize text
        text = text.lower().strip()
        
        # Create hash
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        
        # Convert to fixed-dimension vector
        vector = []
        for i in range(self.dimension):
            # Use bytes from hash to create float values
            byte_val = hash_bytes[i % len(hash_bytes)]
            # Normalize to -1 to 1 range
            vector.append((byte_val / 128.0) - 1.0)
        
        return vector
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)
    
    def build_index(self):
        """Build vector index from all engineering memory records."""
        memories = get_all_memories(limit=1000)
        
        for memory in memories:
            memory_id = memory[0]
            context = memory[2] or ""
            change_summary = memory[3] or ""
            
            # Combine fields for embedding
            text = f"{context} {change_summary}"
            
            if text.strip():
                vector = self._text_to_vector(text)
                self.embeddings[memory_id] = vector
        
        print(f"[VectorIndex] Built index with {len(self.embeddings)} memories")
    
    def add_memory(self, memory_id: int, context: str, change_summary: str):
        """Add single memory to index."""
        text = f"{context} {change_summary}"
        vector = self._text_to_vector(text)
        self.embeddings[memory_id] = vector
    
    def search_similar(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        """Search for similar memories.
        
        Args:
            query: Search query text
            top_k: Number of results to return
        
        Returns:
            List of (memory_id, similarity_score) tuples
        """
        query_vector = self._text_to_vector(query)
        
        scores = []
        for memory_id, vector in self.embeddings.items():
            similarity = self._cosine_similarity(query_vector, vector)
            scores.append((memory_id, similarity))
        
        # Sort by similarity (highest first)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:top_k]


# Global index instance
_global_index = None


def get_vector_index() -> VectorIndex:
    """Get or create global vector index."""
    global _global_index
    if _global_index is None:
        _global_index = VectorIndex()
        _global_index.build_index()
    return _global_index


def refresh_index():
    """Rebuild vector index from database."""
    global _global_index
    _global_index = VectorIndex()
    _global_index.build_index()
    return _global_index


def compute_embedding_id(text: str) -> str:
    """Compute embedding ID for a text.
    
    This provides a stable identifier for the embedding.
    """
    hash_obj = hashlib.sha256(text.encode())
    return hash_obj.hexdigest()[:16]
