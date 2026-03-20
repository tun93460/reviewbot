from dataclasses import dataclass
from typing import Any

import gitlab


@dataclass
class MRData:
    project_path: str
    mr_iid: int
    title: str
    description: str
    author: str
    source_branch: str
    target_branch: str
    diff_files: list[dict]
    total_changes: int
    web_url: str = ""
    pipeline_status: str | None = None
    pipeline_url: str | None = None


@dataclass
class MRSummary:
    iid: int
    title: str
    author: str
    source_branch: str
    target_branch: str
    created_at: str
    updated_at: str
    web_url: str
    pipeline_status: str | None = None


class GitLabClient:
    def __init__(self, url: str, token: str, username: str | None = None):
        self.gl = gitlab.Gitlab(url=url, private_token=token)
        self.gl.auth()
        self._username_override = username or ""

    def get_merge_request(
        self,
        project_path: str,
        mr_iid: int,
        include_full: bool = False,
        include_blame: bool = False,
    ) -> MRData:
        project = self.gl.projects.get(project_path)
        mr = project.mergerequests.get(mr_iid)
        changes: Any = mr.changes()

        diff_files = []
        total_changes = 0
        for change in changes.get("changes", []):
            diff_text = change.get("diff", "")
            line_count = diff_text.count("\n")
            total_changes += line_count
            file_entry: dict = {
                "old_path": change.get("old_path"),
                "new_path": change.get("new_path"),
                "diff": diff_text,
                "new_file": change.get("new_file", False),
                "deleted_file": change.get("deleted_file", False),
                "renamed_file": change.get("renamed_file", False),
                "line_count": line_count,
            }
            if include_full and file_entry.get("new_path"):
                try:
                    file_obj = project.files.get(
                        file_path=file_entry["new_path"],
                        ref=mr.source_branch,
                    )
                    file_entry["full_text"] = file_obj.decode()
                except Exception:
                    file_entry["full_text"] = ""
            if include_blame and file_entry.get("new_path"):
                try:
                    blame_data = project.repository.blame(
                        file_path=file_entry["new_path"],
                        ref=mr.source_branch,
                    )
                    lines = []
                    for chunk in blame_data:
                        commit = chunk.get("commit", {})
                        sha = commit.get("id", "")[:8]
                        author = commit.get("author_name", "")
                        for line in chunk.get("lines", []):
                            lines.append(f"{sha} {author}: {line}")
                    file_entry["blame"] = lines
                except Exception:
                    file_entry["blame"] = []
            diff_files.append(file_entry)

        # Extract pipeline status — prefer head_pipeline attribute, fall back to pipelines API
        pipeline_status = None
        pipeline_url = None
        attrs = getattr(mr, "attributes", {})
        head = attrs.get("head_pipeline") or {}
        if isinstance(head, dict):
            pipeline_status = head.get("status")
            pipeline_url = head.get("web_url") or head.get("url")
        if pipeline_status is None:
            try:
                latest = mr.pipelines.list(order_by="id", sort="desc", per_page=1)
                if latest:
                    pipe = latest[0]
                    pipeline_status = getattr(pipe, "status", None)
                    pipeline_url = getattr(pipe, "web_url", None) or getattr(pipe, "url", None)
            except Exception:
                pass

        return MRData(
            project_path=project_path,
            mr_iid=mr_iid,
            title=mr.title,
            description=mr.description or "",
            author=mr.author["username"],
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            diff_files=diff_files,
            total_changes=total_changes,
            web_url=mr.web_url,
            pipeline_status=pipeline_status,
            pipeline_url=pipeline_url,
        )

    def list_open_mrs(
        self,
        project_path: str,
        limit: int = 25,
        assigned_to_me: bool = False,
    ) -> list[MRSummary]:
        """Return summary objects for open merge requests.

        If ``assigned_to_me`` is True, filters client-side to MRs where the
        authenticated user is assignee or reviewer (API AND semantics prevent
        doing this server-side in one query).
        """
        project = self.gl.projects.get(project_path)
        params: dict[str, Any] = dict(state="opened", order_by="updated_at", sort="desc", per_page=limit, get_all=False)
        mrs = project.mergerequests.list(**params)  # type: ignore[call-arg]

        if assigned_to_me:
            user = self.gl.user
            if user:
                uname = user.username or ""
                uid = getattr(user, "id", None)
                if uname or uid is not None:
                    filtered = []
                    for mr in mrs:
                        added = False
                        assignee = getattr(mr, "assignee", None)
                        if assignee and isinstance(assignee, dict):
                            if uname and assignee.get("username") == uname:
                                filtered.append(mr)
                                continue
                            if uid is not None and assignee.get("id") == uid:
                                filtered.append(mr)
                                continue
                        for a in getattr(mr, "assignees", []) or []:
                            if uname and a.get("username") == uname:
                                filtered.append(mr)
                                added = True
                                break
                            if uid is not None and a.get("id") == uid:
                                filtered.append(mr)
                                added = True
                                break
                        if added:
                            continue
                        for r in getattr(mr, "reviewers", []) or []:
                            if uname and r.get("username") == uname:
                                filtered.append(mr)
                                break
                            if uid is not None and r.get("id") == uid:
                                filtered.append(mr)
                                break
                    mrs = filtered

        summaries: list[MRSummary] = []
        for mr in mrs:
            status = None
            attrs = getattr(mr, "attributes", {})
            head = attrs.get("head_pipeline") or {}
            if isinstance(head, dict):
                status = head.get("status")
            if status is None:
                try:
                    latest = project.pipelines.list(
                        merge_request_iid=mr.iid,
                        order_by="id",
                        sort="desc",
                        per_page=1,
                        get_all=False,
                    )
                    if latest:
                        status = getattr(latest[0], "status", None)
                except Exception:
                    pass
            summaries.append(
                MRSummary(
                    iid=mr.iid,
                    title=mr.title,
                    author=mr.author["username"],
                    source_branch=mr.source_branch,
                    target_branch=mr.target_branch,
                    created_at=mr.created_at,
                    updated_at=mr.updated_at,
                    web_url=mr.web_url,
                    pipeline_status=status,
                )
            )
        return summaries

    def post_mr_note(self, project_path: str, mr_iid: int, body: str) -> str:
        project = self.gl.projects.get(project_path)
        mr = project.mergerequests.get(mr_iid)
        note = mr.notes.create({"body": body})
        return note.attributes.get("id", "")
