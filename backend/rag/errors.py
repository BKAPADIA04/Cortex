class RagError(Exception):
    """Base class for all RAG pipeline errors."""


class UnsupportedFileTypeError(RagError):
    """Raised when an uploaded file's extension isn't supported."""


class FileTooLargeError(RagError):
    """Raised when an uploaded file exceeds the configured size limit."""


class EmptyDocumentError(RagError):
    """Raised when a file contains no extractable text."""


class DocumentParsingError(RagError):
    """Raised when a file can't be parsed (corrupt, wrong format, etc.)."""


class EmbeddingError(RagError):
    """Raised when the embedding provider fails."""
