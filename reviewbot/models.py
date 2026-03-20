from dataclasses import dataclass


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
    diff_truncated: bool = False
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


def _extract_position(pos: dict | None) -> dict | None:
    """Simplify a raw GitLab note position dict for output."""
    if not pos or pos.get("position_type") != "text":
        return None
    return {
        "file_path": pos.get("new_path") or pos.get("old_path"),
        "new_line": pos.get("new_line"),
        "old_line": pos.get("old_line"),
    }
