"""content_pipeline — SSID knowledge content extraction, transformation, and indexing.

Pipeline stages:
    1. ContentExtractor   — scan_sources() + extract_content()
    2. ContentTransformer — normalize() + enrich() + to_knowledge_artifact()
    3. ContentClassifier  — classify()
    4. ContentIndexer     — build_index() + search() + save_index() + load_index()
    5. ContentRegistryUpdater — update_registry()

Typical usage::

    from content_pipeline import (
        ContentExtractor,
        ContentTransformer,
        ContentClassifier,
        ContentIndexer,
        ContentRegistryUpdater,
    )

    extractor = ContentExtractor()
    transformer = ContentTransformer()
    classifier = ContentClassifier()
    indexer = ContentIndexer()
    updater = ContentRegistryUpdater()

    sources = extractor.scan_sources(["/path/to/docs"])
    artifacts = []
    for src in sources:
        extracted = extractor.extract_content(src)
        normalized = transformer.normalize(extracted)
        enriched = transformer.enrich(normalized)
        artifact = transformer.to_knowledge_artifact(enriched)
        artifacts.append(artifact)

    index = indexer.build_index(artifacts)
    indexer.save_index(index, "/path/to/index_dir")
    result = updater.update_registry(index, "/path/to/registry_dir")
"""

from .content_extractor import (
    ContentExtractor,
    SourceFile,
    ExtractedContent,
)
from .content_transformer import (
    ContentTransformer,
    NormalizedContent,
    EnrichedContent,
    KnowledgeArtifact,
)
from .content_classifier import (
    ContentClassifier,
    Classification,
    CategoryScore,
    CATEGORIES,
)
from .content_indexer import (
    ContentIndexer,
    KnowledgeIndex,
    SearchResult,
)
from .content_registry_updater import (
    ContentRegistryUpdater,
    RegistryEntry,
    RegistryUpdate,
)

__all__ = [
    # Extractor
    "ContentExtractor",
    "SourceFile",
    "ExtractedContent",
    # Transformer
    "ContentTransformer",
    "NormalizedContent",
    "EnrichedContent",
    "KnowledgeArtifact",
    # Classifier
    "ContentClassifier",
    "Classification",
    "CategoryScore",
    "CATEGORIES",
    # Indexer
    "ContentIndexer",
    "KnowledgeIndex",
    "SearchResult",
    # Registry
    "ContentRegistryUpdater",
    "RegistryEntry",
    "RegistryUpdate",
]
