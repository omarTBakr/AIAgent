from exceptions.base import AIAgentError


class ParsingError(AIAgentError):
    """Anything that went wrong turning a PDF into Markdown."""


class PdfNotFoundError(ParsingError, FileNotFoundError):
    """The PDF to parse is not on disk. Also a FileNotFoundError."""


class InvalidPdfError(ParsingError):
    """The bytes are not a PDF, or the document is corrupt."""
