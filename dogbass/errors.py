from __future__ import annotations


class AppError(RuntimeError):
    """Known application error that can be shown to the user as-is."""

    exit_code = 1


class ConfigurationError(AppError):
    """Invalid or missing application configuration."""


class ValidationError(AppError):
    """Invalid user input or document content."""


class FileConflictError(AppError):
    """A requested file operation would overwrite existing data."""


class DocBaseRequestError(AppError):
    """The DocBase API rejected the request."""


class DocBaseResponseError(AppError):
    """The DocBase API returned an invalid response."""
