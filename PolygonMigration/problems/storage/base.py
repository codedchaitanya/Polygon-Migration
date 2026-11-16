"""
Provider-independent storage interface for test-case files.

The migration flow only talks to `TestCaseStorage`. Each cloud provider lives in
its own module and implements the three primitive operations below. File naming
is defined here, once, so every provider produces the same layout:

    test_cases/{problem_id}/{test_number}      input file
    test_cases/{problem_id}/{test_number}.a    output file
"""
from abc import ABC, abstractmethod


class StorageError(Exception):
    """Raised when a storage operation fails or the provider is misconfigured."""


def problem_prefix(problem_id):
    """Folder that holds every file of one problem."""
    return f"test_cases/{problem_id}/"


def test_input_path(problem_id, test_number):
    return f"{problem_prefix(problem_id)}{test_number:02d}"


def test_output_path(problem_id, test_number):
    return f"{problem_prefix(problem_id)}{test_number:02d}.a"


def checker_path(problem_id, filename):
    return f"{problem_prefix(problem_id)}{filename}"


class TestCaseStorage(ABC):
    """What a storage provider must implement."""

    #: Human-readable provider name, used in log messages.
    name = "storage"

    @abstractmethod
    def upload_file(self, path, data):
        """Create or overwrite the file at `path` with `data` (bytes)."""

    @abstractmethod
    def list_files(self, prefix):
        """Return the paths of all files whose path starts with `prefix`."""

    @abstractmethod
    def delete_file(self, path):
        """Delete the file at `path`."""

    # ------------------------------------------------------------------
    # Shared behaviour built on the primitives above.
    # ------------------------------------------------------------------

    def upload_test_case(self, problem_id, test_number, input_data, output_data):
        """Upload one test case as an input file and an output (.a) file."""
        self.upload_file(test_input_path(problem_id, test_number), _to_bytes(input_data))
        self.upload_file(test_output_path(problem_id, test_number), _to_bytes(output_data))

    def upload_checker(self, problem_id, filename, data):
        """Upload a custom checker (source or compiled binary) next to the tests."""
        path = checker_path(problem_id, filename)
        self.upload_file(path, _to_bytes(data))
        return path

    def delete_problem_files(self, problem_id):
        """Delete every stored file of a problem. Returns how many were deleted."""
        paths = self.list_files(problem_prefix(problem_id))
        for path in paths:
            self.delete_file(path)
        return len(paths)


def _to_bytes(data):
    return data.encode("utf-8") if isinstance(data, str) else data
