"""
Embedding Service
==================
Local embedding generation using sentence-transformers.
Provides semantic similarity matching between JD and candidate profiles.

Design Decision: Using local embeddings (all-MiniLM-L6-v2) instead of
cloud APIs to:
  - Eliminate API costs during development
  - Keep candidate PII local (privacy by design)
  - Ensure zero-latency embedding without network dependency
"""

import logging
from functools import lru_cache

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        import config
        logger.info(f"Loading embedding model: {config.EMBEDDING_MODEL}")
        _model = SentenceTransformer(config.EMBEDDING_MODEL)
        logger.info("Embedding model loaded successfully")
    return _model


def get_embedding(text: str) -> np.ndarray:
    """
    Generate embedding vector for a text string.
    
    Args:
        text: Input text to embed
        
    Returns:
        Numpy array of the embedding vector
    """
    model = _get_model()
    # Truncate very long texts to prevent OOM
    truncated = text[:8000] if len(text) > 8000 else text
    embedding = model.encode(truncated, show_progress_bar=False)
    return np.array(embedding)


def compute_similarity(text_a: str, text_b: str) -> float:
    """
    Compute cosine similarity between two texts.
    
    Args:
        text_a: First text (typically JD summary)
        text_b: Second text (typically candidate profile)
        
    Returns:
        Cosine similarity score between 0 and 1
    """
    emb_a = get_embedding(text_a).reshape(1, -1)
    emb_b = get_embedding(text_b).reshape(1, -1)
    similarity = cosine_similarity(emb_a, emb_b)[0][0]
    return round(float(similarity), 4)


def batch_similarity(reference_text: str, candidate_texts: list[str]) -> list[float]:
    """
    Compute similarity of multiple candidates against a single reference.
    More efficient than individual calls due to batch encoding.
    
    Args:
        reference_text: The JD/reference text
        candidate_texts: List of candidate profile texts
        
    Returns:
        List of similarity scores
    """
    model = _get_model()
    
    # Truncate texts
    ref_truncated = reference_text[:8000]
    cand_truncated = [t[:8000] for t in candidate_texts]
    
    # Batch encode
    ref_emb = model.encode([ref_truncated], show_progress_bar=False)
    cand_embs = model.encode(cand_truncated, show_progress_bar=False)
    
    # Compute similarities
    similarities = cosine_similarity(ref_emb, cand_embs)[0]
    return [round(float(s), 4) for s in similarities]
