"""Tests for reviewbot/models.py — pure functions and dataclasses."""
import pytest

from reviewbot.models import MRData, MRSummary, _extract_position


class TestExtractPosition:
    def test_none_input(self):
        assert _extract_position(None) is None

    def test_empty_dict(self):
        assert _extract_position({}) is None

    def test_non_text_position_type(self):
        assert _extract_position({"position_type": "image"}) is None

    def test_text_position_with_new_path(self):
        pos = {
            "position_type": "text",
            "new_path": "src/foo.py",
            "old_path": "src/foo.py",
            "new_line": 42,
            "old_line": None,
        }
        result = _extract_position(pos)
        assert result == {"file_path": "src/foo.py", "new_line": 42, "old_line": None}

    def test_falls_back_to_old_path_when_new_path_absent(self):
        pos = {
            "position_type": "text",
            "new_path": None,
            "old_path": "src/deleted.py",
            "new_line": None,
            "old_line": 10,
        }
        result = _extract_position(pos)
        assert result["file_path"] == "src/deleted.py"

    def test_both_lines_none(self):
        pos = {"position_type": "text", "new_path": "src/foo.py", "new_line": None, "old_line": None}
        result = _extract_position(pos)
        assert result["new_line"] is None
        assert result["old_line"] is None


class TestMRDataDefaults:
    def test_diff_truncated_defaults_false(self):
        mr = MRData(
            project_path="group/repo",
            mr_iid=1,
            title="T",
            description="",
            author="alice",
            source_branch="feat",
            target_branch="main",
            diff_files=[],
            total_changes=0,
        )
        assert mr.diff_truncated is False
        assert mr.pipeline_status is None
        assert mr.pipeline_url is None
        assert mr.web_url == ""
