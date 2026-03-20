"""Shared fixtures for ReviewBot tests."""
import pytest
from unittest.mock import MagicMock, patch

from reviewbot.gitlab_client import GitLabClient


@pytest.fixture
def gl_mock():
    """Patch gitlab.Gitlab and return the mock instance.

    Tests that need a GitLabClient should use `make_client` which depends on
    this fixture.
    """
    with patch("reviewbot.gitlab_client.gitlab.Gitlab") as MockGitlab:
        gl = MagicMock()
        MockGitlab.return_value = gl
        yield gl


@pytest.fixture
def make_client(gl_mock):
    """Return a GitLabClient wired to the mock gitlab instance."""
    return GitLabClient("https://gitlab.example.com", "fake-token")


@pytest.fixture
def mock_mr():
    """A minimal mock MR with sensible defaults for diff_refs and attributes."""
    mr = MagicMock()
    mr.title = "Add feature"
    mr.description = "Some description"
    mr.author = {"username": "alice"}
    mr.source_branch = "feature/add-thing"
    mr.target_branch = "main"
    mr.web_url = "https://gitlab.example.com/group/repo/-/merge_requests/7"
    mr.attributes = {
        "head_pipeline": {"status": "passed", "web_url": "https://gitlab.example.com/pipelines/1"},
        "diff_refs": {
            "base_sha": "base000",
            "start_sha": "start000",
            "head_sha": "head000",
        },
    }
    mr.changes.return_value = {
        "overflow": False,
        "changes": [
            {
                "old_path": "src/foo.py",
                "new_path": "src/foo.py",
                "diff": "@@ -1,2 +1,3 @@\n line1\n line2\n+new line\n",
                "new_file": False,
                "deleted_file": False,
                "renamed_file": False,
                "too_large": False,
            }
        ],
    }
    return mr


@pytest.fixture
def mock_project(mock_mr):
    """A mock GitLab project with the mock_mr wired in."""
    project = MagicMock()
    project.mergerequests.get.return_value = mock_mr
    return project
