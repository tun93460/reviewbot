"""Tests for rb.py — argument parsing and command logic."""
import json
import sys
import pytest
from unittest.mock import MagicMock, patch

from rb import build_parser, parse_mr_target


class TestParseMrTarget:
    def test_explicit_path_and_iid(self):
        project, iid = parse_mr_target("group/repo", 42)
        assert project == "group/repo"
        assert iid == 42

    def test_full_url_extracts_path_and_iid(self):
        url = "https://gitlab.example.com/group/sub/repo/-/merge_requests/99"
        project, iid = parse_mr_target(url, None)
        assert project == "group/sub/repo"
        assert iid == 99

    def test_url_overrides_iid_arg(self):
        url = "https://gitlab.example.com/group/repo/-/merge_requests/7"
        project, iid = parse_mr_target(url, 999)
        assert iid == 7

    def test_missing_iid_without_url_exits(self):
        with pytest.raises(SystemExit):
            parse_mr_target("group/repo", None)


class TestArgumentParser:
    def setup_method(self):
        self.parser = build_parser()

    def _parse(self, argv):
        return self.parser.parse_args(argv)

    def test_all_subcommands_registered(self):
        # Each subcommand needs its minimum required positionals
        cases = [
            ("list", ["list", "group/repo"]),
            ("info", ["info", "group/repo", "42"]),
            ("diff", ["diff", "group/repo", "42"]),
            ("comments", ["comments", "group/repo", "42"]),
            ("post", ["post", "group/repo", "42", "body"]),
            ("file", ["file", "group/repo", "src/foo.py"]),
        ]
        for cmd, argv in cases:
            args = self._parse(argv)
            assert args.command == cmd

    def test_diff_full_and_blame_flags(self):
        args = self._parse(["diff", "group/repo", "42", "--full", "--blame"])
        assert args.full is True
        assert args.blame is True

    def test_post_inline_flags(self):
        args = self._parse(["post", "group/repo", "42", "body", "--file", "src/foo.py", "--line", "10", "--old-line", "9"])
        assert args.file == "src/foo.py"
        assert args.line == 10
        assert args.old_line == 9  # dest= mapping

    def test_comments_system_flag(self):
        args = self._parse(["comments", "group/repo", "42", "--system"])
        assert args.system is True

    def test_file_subcommand_ref(self):
        args = self._parse(["file", "group/repo", "src/foo.py", "--ref", "v2.0"])
        assert args.file_path == "src/foo.py"
        assert args.ref == "v2.0"

    def test_list_assigned_and_limit(self):
        args = self._parse(["list", "group/repo", "--assigned", "--limit", "10"])
        assert args.assigned is True
        assert args.limit == 10


class TestCmdPost:
    def _run(self, argv, stdin_text=""):
        from rb import cmd_post, AppConfig
        args = build_parser().parse_args(argv)
        client = MagicMock()
        config = MagicMock(spec=AppConfig)

        with patch("rb.build_client", return_value=client), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = stdin_text
            return args, client

    def test_top_level_note(self, capsys):
        from rb import cmd_post, AppConfig
        args = build_parser().parse_args(["post", "group/repo", "42", "hello"])
        client = MagicMock()
        client.post_mr_note.return_value = "101"

        with patch("rb.build_client", return_value=client):
            cmd_post(args, MagicMock())

        client.post_mr_note.assert_called_once_with("group/repo", 42, "hello")
        out = json.loads(capsys.readouterr().out)
        assert out["note_id"] == "101"

    def test_inline_note(self, capsys):
        from rb import cmd_post
        args = build_parser().parse_args([
            "post", "group/repo", "42", "bad contrast",
            "--file", "src/Button.vue", "--line", "15",
        ])
        client = MagicMock()
        client.post_mr_inline_note.return_value = {
            "note_id": 55, "discussion_id": "d1", "project": "group/repo",
            "mr_iid": 42, "file_path": "src/Button.vue",
        }

        with patch("rb.build_client", return_value=client):
            cmd_post(args, MagicMock())

        client.post_mr_inline_note.assert_called_once_with(
            "group/repo", 42, "bad contrast", "src/Button.vue", 15, None
        )

    def test_file_without_line_errors(self):
        from rb import cmd_post
        args = build_parser().parse_args(["post", "group/repo", "42", "body", "--file", "src/foo.py"])
        with patch("rb.build_client", return_value=MagicMock()):
            with pytest.raises(SystemExit):
                cmd_post(args, MagicMock())

    def test_line_without_file_errors(self):
        from rb import cmd_post
        args = build_parser().parse_args(["post", "group/repo", "42", "body", "--line", "5"])
        with patch("rb.build_client", return_value=MagicMock()):
            with pytest.raises(SystemExit):
                cmd_post(args, MagicMock())


class TestCmdDiff:
    def test_truncation_warning_on_stderr(self, capsys):
        from rb import cmd_diff
        from reviewbot.models import MRData

        mr_data = MRData(
            project_path="group/repo", mr_iid=7, title="T", description="",
            author="alice", source_branch="feat", target_branch="main",
            diff_files=[], total_changes=0, diff_truncated=True,
        )
        args = build_parser().parse_args(["diff", "group/repo", "7"])
        client = MagicMock()
        client.get_merge_request.return_value = mr_data

        with patch("rb.build_client", return_value=client):
            cmd_diff(args, MagicMock())

        assert "WARNING" in capsys.readouterr().err

    def test_too_large_label_in_output(self, capsys):
        from rb import cmd_diff
        from reviewbot.models import MRData

        diff_file = {
            "old_path": "src/big.py", "new_path": "src/big.py",
            "diff": "", "new_file": False, "deleted_file": False,
            "renamed_file": False, "too_large": True, "line_count": 0,
        }
        mr_data = MRData(
            project_path="group/repo", mr_iid=7, title="T", description="",
            author="alice", source_branch="feat", target_branch="main",
            diff_files=[diff_file], total_changes=0, diff_truncated=False,
        )
        args = build_parser().parse_args(["diff", "group/repo", "7"])
        client = MagicMock()
        client.get_merge_request.return_value = mr_data

        with patch("rb.build_client", return_value=client):
            cmd_diff(args, MagicMock())

        assert "truncated" in capsys.readouterr().out
