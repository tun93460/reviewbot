"""Tests for reviewbot/gitlab_client.py — GitLabClient methods."""
import pytest
from unittest.mock import MagicMock, call


class TestGetMergeRequest:
    def test_basic_fields(self, make_client, gl_mock, mock_project, mock_mr):
        gl_mock.projects.get.return_value = mock_project
        mr = make_client.get_merge_request("group/repo", 7)

        assert mr.mr_iid == 7
        assert mr.title == "Add feature"
        assert mr.author == "alice"
        assert mr.source_branch == "feature/add-thing"
        assert mr.diff_truncated is False
        assert len(mr.diff_files) == 1

    def test_diff_truncated_when_overflow(self, make_client, gl_mock, mock_project, mock_mr):
        mock_mr.changes.return_value["overflow"] = True
        gl_mock.projects.get.return_value = mock_project

        mr = make_client.get_merge_request("group/repo", 7)
        assert mr.diff_truncated is True

    def test_per_file_too_large(self, make_client, gl_mock, mock_project, mock_mr):
        mock_mr.changes.return_value["changes"][0]["too_large"] = True
        gl_mock.projects.get.return_value = mock_project

        mr = make_client.get_merge_request("group/repo", 7)
        assert mr.diff_files[0]["too_large"] is True

    def test_pipeline_status_from_head_pipeline(self, make_client, gl_mock, mock_project, mock_mr):
        gl_mock.projects.get.return_value = mock_project

        mr = make_client.get_merge_request("group/repo", 7)
        assert mr.pipeline_status == "passed"
        assert mr.pipeline_url == "https://gitlab.example.com/pipelines/1"

    def test_pipeline_status_fallback_to_pipelines_api(self, make_client, gl_mock, mock_project, mock_mr):
        mock_mr.attributes["head_pipeline"] = {}
        pipe = MagicMock(status="running", web_url="https://gitlab.example.com/pipelines/2", url=None)
        mock_mr.pipelines.list.return_value = [pipe]
        gl_mock.projects.get.return_value = mock_project

        mr = make_client.get_merge_request("group/repo", 7)
        assert mr.pipeline_status == "running"

    def test_pipeline_status_none_when_no_pipeline(self, make_client, gl_mock, mock_project, mock_mr):
        mock_mr.attributes["head_pipeline"] = {}
        mock_mr.pipelines.list.return_value = []
        gl_mock.projects.get.return_value = mock_project

        mr = make_client.get_merge_request("group/repo", 7)
        assert mr.pipeline_status is None

    def test_include_full_fetches_file_content(self, make_client, gl_mock, mock_project, mock_mr):
        file_obj = MagicMock()
        file_obj.decode.return_value = "full file content"
        mock_project.files.get.return_value = file_obj
        gl_mock.projects.get.return_value = mock_project

        mr = make_client.get_merge_request("group/repo", 7, include_full=True)
        assert mr.diff_files[0]["full_text"] == "full file content"
        mock_project.files.get.assert_called_once_with(
            file_path="src/foo.py", ref=mock_mr.source_branch
        )

    def test_include_full_ignores_deleted_files(self, make_client, gl_mock, mock_project, mock_mr):
        mock_mr.changes.return_value["changes"][0]["deleted_file"] = True
        mock_mr.changes.return_value["changes"][0]["new_path"] = None
        gl_mock.projects.get.return_value = mock_project

        mr = make_client.get_merge_request("group/repo", 7, include_full=True)
        mock_project.files.get.assert_not_called()

    def test_include_blame(self, make_client, gl_mock, mock_project, mock_mr):
        blame_chunks = [
            {"commit": {"id": "abc12345abcd", "author_name": "Bob"}, "lines": ["line one", "line two"]},
        ]
        mock_project.repository.blame.return_value = blame_chunks
        gl_mock.projects.get.return_value = mock_project

        mr = make_client.get_merge_request("group/repo", 7, include_blame=True)
        blame = mr.diff_files[0]["blame"]
        assert blame == ["abc12345 Bob: line one", "abc12345 Bob: line two"]


class TestGetMrComments:
    def _make_discussion(self, disc_id, notes):
        disc = MagicMock()
        disc.attributes = {"id": disc_id, "notes": notes}
        return disc

    def test_returns_flat_list_of_notes(self, make_client, gl_mock, mock_project):
        disc = self._make_discussion("disc-1", [
            {
                "id": 101, "author": {"username": "alice"}, "body": "Looks good",
                "created_at": "2024-01-01T00:00:00Z", "system": False,
                "resolvable": True, "resolved": False, "position": None,
            }
        ])
        mock_project.mergerequests.get.return_value.discussions.list.return_value = [disc]
        gl_mock.projects.get.return_value = mock_project

        comments = make_client.get_mr_comments("group/repo", 7)
        assert len(comments) == 1
        assert comments[0]["author"] == "alice"
        assert comments[0]["discussion_id"] == "disc-1"
        assert comments[0]["body"] == "Looks good"

    def test_filters_system_notes_by_default(self, make_client, gl_mock, mock_project):
        disc = self._make_discussion("disc-1", [
            {"id": 1, "author": {"username": "gitlab"}, "body": "pushed commit abc",
             "created_at": "2024-01-01T00:00:00Z", "system": True,
             "resolvable": False, "resolved": False, "position": None},
            {"id": 2, "author": {"username": "alice"}, "body": "Please fix this",
             "created_at": "2024-01-01T00:00:00Z", "system": False,
             "resolvable": True, "resolved": False, "position": None},
        ])
        mock_project.mergerequests.get.return_value.discussions.list.return_value = [disc]
        gl_mock.projects.get.return_value = mock_project

        comments = make_client.get_mr_comments("group/repo", 7)
        assert len(comments) == 1
        assert comments[0]["id"] == 2

    def test_includes_system_notes_when_requested(self, make_client, gl_mock, mock_project):
        disc = self._make_discussion("disc-1", [
            {"id": 1, "author": {"username": "gitlab"}, "body": "pushed commit",
             "created_at": "2024-01-01T00:00:00Z", "system": True,
             "resolvable": False, "resolved": False, "position": None},
        ])
        mock_project.mergerequests.get.return_value.discussions.list.return_value = [disc]
        gl_mock.projects.get.return_value = mock_project

        comments = make_client.get_mr_comments("group/repo", 7, include_system=True)
        assert len(comments) == 1

    def test_fetches_all_pages(self, make_client, gl_mock, mock_project):
        mock_project.mergerequests.get.return_value.discussions.list.return_value = []
        gl_mock.projects.get.return_value = mock_project

        make_client.get_mr_comments("group/repo", 7)
        mock_project.mergerequests.get.return_value.discussions.list.assert_called_once_with(get_all=True)

    def test_inline_position_extracted(self, make_client, gl_mock, mock_project):
        pos = {
            "position_type": "text", "new_path": "src/foo.py", "old_path": "src/foo.py",
            "new_line": 10, "old_line": None,
        }
        disc = self._make_discussion("disc-1", [
            {"id": 1, "author": {"username": "alice"}, "body": "fix this",
             "created_at": "2024-01-01T00:00:00Z", "system": False,
             "resolvable": True, "resolved": False, "position": pos},
        ])
        mock_project.mergerequests.get.return_value.discussions.list.return_value = [disc]
        gl_mock.projects.get.return_value = mock_project

        comments = make_client.get_mr_comments("group/repo", 7)
        assert comments[0]["position"] == {"file_path": "src/foo.py", "new_line": 10, "old_line": None}


class TestPostMrInlineNote:
    def test_posts_with_correct_position(self, make_client, gl_mock, mock_project, mock_mr):
        discussion = MagicMock()
        discussion.attributes = {
            "id": "disc-new",
            "notes": [{"id": 999}],
        }
        mock_mr.discussions.create.return_value = discussion
        gl_mock.projects.get.return_value = mock_project

        result = make_client.post_mr_inline_note("group/repo", 7, "bad aria", "src/foo.py", new_line=34, old_line=None)

        assert result["note_id"] == 999
        assert result["discussion_id"] == "disc-new"
        assert result["file_path"] == "src/foo.py"

        _, kwargs = mock_mr.discussions.create.call_args
        pos = mock_mr.discussions.create.call_args[0][0]["position"]
        assert pos["base_sha"] == "base000"
        assert pos["head_sha"] == "head000"
        assert pos["new_line"] == 34
        assert "old_line" not in pos

    def test_raises_when_diff_refs_missing(self, make_client, gl_mock, mock_project, mock_mr):
        mock_mr.attributes["diff_refs"] = None
        gl_mock.projects.get.return_value = mock_project

        with pytest.raises(ValueError, match="diff_refs"):
            make_client.post_mr_inline_note("group/repo", 7, "comment", "src/foo.py", new_line=1, old_line=None)

    def test_old_line_only_for_removed_lines(self, make_client, gl_mock, mock_project, mock_mr):
        discussion = MagicMock()
        discussion.attributes = {"id": "disc-x", "notes": [{"id": 1}]}
        mock_mr.discussions.create.return_value = discussion
        gl_mock.projects.get.return_value = mock_project

        make_client.post_mr_inline_note("group/repo", 7, "removed line comment", "src/foo.py", new_line=None, old_line=5)

        pos = mock_mr.discussions.create.call_args[0][0]["position"]
        assert pos["old_line"] == 5
        assert "new_line" not in pos


class TestGetFileContent:
    def test_returns_decoded_string(self, make_client, gl_mock, mock_project):
        file_obj = MagicMock()
        file_obj.decode.return_value = "print('hello')\n"
        mock_project.files.get.return_value = file_obj
        gl_mock.projects.get.return_value = mock_project

        content = make_client.get_file_content("group/repo", "src/foo.py")
        assert content == "print('hello')\n"
        mock_project.files.get.assert_called_once_with(file_path="src/foo.py", ref="HEAD")

    def test_decodes_bytes(self, make_client, gl_mock, mock_project):
        file_obj = MagicMock()
        file_obj.decode.return_value = b"byte content"
        mock_project.files.get.return_value = file_obj
        gl_mock.projects.get.return_value = mock_project

        content = make_client.get_file_content("group/repo", "src/foo.py")
        assert content == "byte content"

    def test_passes_ref(self, make_client, gl_mock, mock_project):
        file_obj = MagicMock()
        file_obj.decode.return_value = ""
        mock_project.files.get.return_value = file_obj
        gl_mock.projects.get.return_value = mock_project

        make_client.get_file_content("group/repo", "src/foo.py", ref="v1.2.3")
        mock_project.files.get.assert_called_once_with(file_path="src/foo.py", ref="v1.2.3")
