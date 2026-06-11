# =============================================================================
# src/utils/exceptions.py — Custom exceptions for the pipeline
# =============================================================================
# Rule: Every pipeline failure raises a specific exception.
#       CLI catches these and prints clean error messages.
#       Never let raw Python errors reach the user.
# =============================================================================


class CSVAnalyzerError(Exception):
    """Base exception for all pipeline errors."""
    pass


# ── Load Stage ────────────────────────────────────────────────────────────────

class CSVFileNotFoundError(CSVAnalyzerError):
    """Raised when the input CSV file does not exist (do not shadow builtin FileNotFoundError)."""
    def __init__(self, filepath):
        self.filepath = filepath
        super().__init__(f"File not found: {filepath}")


class InvalidFileTypeError(CSVAnalyzerError):
    """Raised when the file is not a CSV."""
    def __init__(self, filepath):
        self.filepath = filepath
        super().__init__(f"Expected a .csv file, got: {filepath}")


class FileLoadError(CSVAnalyzerError):
    """Raised when the CSV cannot be parsed."""
    def __init__(self, filepath, reason):
        self.filepath = filepath
        self.reason = reason
        super().__init__(f"Failed to load '{filepath}': {reason}")


# ── Profile Stage ─────────────────────────────────────────────────────────────

class ProfilingError(CSVAnalyzerError):
    """Raised when profiling fails unexpectedly."""
    def __init__(self, reason):
        super().__init__(f"Profiling failed: {reason}")


# ── Quality Stage ─────────────────────────────────────────────────────────────

class QualityCheckError(CSVAnalyzerError):
    """Raised when a quality check crashes."""
    def __init__(self, check_name, reason):
        self.check_name = check_name
        super().__init__(f"Quality check '{check_name}' failed: {reason}")


# ── Clean Stage ───────────────────────────────────────────────────────────────

class CleaningError(CSVAnalyzerError):
    """Raised when a cleaning step fails."""
    def __init__(self, reason):
        super().__init__(f"Cleaning failed: {reason}")


# ── Report Stage ──────────────────────────────────────────────────────────────

class ReportGenerationError(CSVAnalyzerError):
    """Raised when the HTML report cannot be written."""
    def __init__(self, output_path, reason):
        self.output_path = output_path
        super().__init__(f"Report generation failed at '{output_path}': {reason}")


# ── Config ────────────────────────────────────────────────────────────────────

class ConfigurationError(CSVAnalyzerError):
    """Raised when config values are invalid."""
    def __init__(self, reason):
        super().__init__(f"Configuration error: {reason}")