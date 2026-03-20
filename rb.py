#!/usr/bin/env python3
"""
ReviewBot CLI — GitLab MR data fetcher for use within Claude Code.

Usage:
  python rb.py list     <project> [--assigned] [--limit N] [--json]
  python rb.py info     <project> <mr_iid>
  python rb.py diff     <project> <mr_iid> [--file PATH] [--full]
  python rb.py comments <project> <mr_iid> [--system]
  python rb.py post     <project> <mr_iid> [body|-] [--file PATH --line N] [--old-line N]
  python rb.py file     <project> <file_path> [--ref REF]

<project> can be a namespace/repo path (e.g. group/repo) or a full GitLab MR URL.
When a URL is given, <mr_iid> is parsed from it automatically.

Data goes to stdout (JSON or raw text). Progress goes to stderr.
Exit code 0 on success, non-zero on error.
"""
import argparse
import json
import re
import sys
import traceback
from typing import NoReturn

from reviewbot.config import AppConfig
from reviewbot.gitlab_client import GitLabClient


_MR_URL_RE = re.compile(r"https?://[^/]+/(.+?)/-/merge_requests/(\d+)")

_debug = False


def err(msg: str) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def progress(msg: str) -> None:
    print(f">> {msg}", file=sys.stderr, flush=True)


def parse_mr_target(project_arg: str, iid_arg: int | None) -> tuple[str, int]:
    """Return (project_path, mr_iid) from either a URL or explicit args."""
    m = _MR_URL_RE.match(project_arg)
    if m:
        return m.group(1), int(m.group(2))
    if iid_arg is None:
        err("mr_iid is required when project is not a full GitLab MR URL")
    return project_arg, iid_arg


def build_client(config: AppConfig) -> GitLabClient:
    errors = config.validate()
    if errors:
        err("\n".join(errors))
    return GitLabClient(config.gitlab_url, config.gitlab_token, config.gitlab_username)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace, config: AppConfig) -> None:
    client = build_client(config)
    mrs = client.list_open_mrs(args.project, limit=args.limit, assigned_to_me=args.assigned)

    if args.json:
        print(json.dumps(
            [
                {
                    "iid": m.iid,
                    "title": m.title,
                    "author": m.author,
                    "source_branch": m.source_branch,
                    "target_branch": m.target_branch,
                    "web_url": m.web_url,
                    "pipeline_status": m.pipeline_status,
                    "updated_at": m.updated_at,
                }
                for m in mrs
            ],
            indent=2,
        ))
        return

    if not mrs:
        print("No open merge requests found.")
        return
    for m in mrs:
        pipe = f" [{m.pipeline_status}]" if m.pipeline_status else ""
        print(f"!{m.iid:<6} {m.author:<20} {m.title[:55]:<55}{pipe}")
        print(f"         {m.source_branch} → {m.target_branch}")
        print(f"         {m.web_url}")
        print()


def cmd_info(args: argparse.Namespace, config: AppConfig) -> None:
    project, mr_iid = parse_mr_target(args.project, getattr(args, "mr_iid", None))
    client = build_client(config)
    mr = client.get_merge_request(project, mr_iid)
    print(json.dumps(
        {
            "iid": mr.mr_iid,
            "title": mr.title,
            "author": mr.author,
            "source_branch": mr.source_branch,
            "target_branch": mr.target_branch,
            "web_url": mr.web_url,
            "description": mr.description,
            "total_changes": mr.total_changes,
            "diff_truncated": mr.diff_truncated,
            "file_count": len(mr.diff_files),
            "files": [
                {
                    "path": f["new_path"],
                    "old_path": f["old_path"],
                    "new_file": f.get("new_file", False),
                    "deleted_file": f.get("deleted_file", False),
                    "renamed_file": f.get("renamed_file", False),
                    "too_large": f.get("too_large", False),
                    "line_count": f.get("line_count", 0),
                }
                for f in mr.diff_files
            ],
            "pipeline_status": mr.pipeline_status,
            "pipeline_url": mr.pipeline_url,
        },
        indent=2,
    ))


def cmd_diff(args: argparse.Namespace, config: AppConfig) -> None:
    project, mr_iid = parse_mr_target(args.project, getattr(args, "mr_iid", None))
    client = build_client(config)
    mr = client.get_merge_request(
        project, mr_iid,
        include_full=getattr(args, "full", False),
        include_blame=getattr(args, "blame", False),
    )

    if mr.diff_truncated:
        progress("WARNING: diff is truncated — this MR exceeds GitLab's diff size limit. "
                 "Use --file to review individual files, or `rb.py file` for full content.")

    files = mr.diff_files
    if args.file:
        files = [f for f in files if args.file in (f["new_path"], f["old_path"])]
        if not files:
            err(f"file '{args.file}' not found in this MR")

    for f in files:
        label = f["new_path"]
        if f.get("renamed_file"):
            label = f"{f['old_path']} → {f['new_path']}"
        elif f.get("new_file"):
            label += "  (new file)"
        elif f.get("deleted_file"):
            label += "  (deleted)"
        if f.get("too_large"):
            label += "  [TRUNCATED — use --full or `rb.py file` for complete content]"
        print(f"\n=== {label} ===")
        if getattr(args, "full", False) and f.get("full_text"):
            print(f["full_text"])
        else:
            print(f["diff"])
        if getattr(args, "blame", False) and f.get("blame"):
            print(f"\n--- blame: {f['new_path']} ---")
            print("\n".join(f["blame"]))


def cmd_comments(args: argparse.Namespace, config: AppConfig) -> None:
    project, mr_iid = parse_mr_target(args.project, getattr(args, "mr_iid", None))
    client = build_client(config)
    progress(f"Fetching comments for !{mr_iid} ...")
    comments = client.get_mr_comments(project, mr_iid, include_system=args.system)
    print(json.dumps(comments, indent=2))


def cmd_post(args: argparse.Namespace, config: AppConfig) -> None:
    project, mr_iid = parse_mr_target(args.project, getattr(args, "mr_iid", None))
    client = build_client(config)
    body = sys.stdin.read() if (args.body == "-" or not args.body) else args.body
    if not body.strip():
        err("comment body is empty")

    file_path = getattr(args, "file", None)
    new_line = getattr(args, "line", None)
    old_line = getattr(args, "old_line", None)

    if file_path is not None:
        if new_line is None and old_line is None:
            err("--file requires --line or --old-line")
        result = client.post_mr_inline_note(project, mr_iid, body, file_path, new_line, old_line)
        print(json.dumps(result))
    else:
        if new_line is not None or old_line is not None:
            err("--line and --old-line require --file")
        note_id = client.post_mr_note(project, mr_iid, body)
        print(json.dumps({"note_id": note_id, "project": project, "mr_iid": mr_iid}))


def cmd_file(args: argparse.Namespace, config: AppConfig) -> None:
    client = build_client(config)
    ref = args.ref or "HEAD"
    progress(f"Fetching {args.file_path} @ {ref} ...")
    content = client.get_file_content(args.project, args.file_path, ref=ref)
    sys.stdout.write(content)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rb",
        description="ReviewBot — GitLab MR data fetcher for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--debug", action="store_true", help="Show full tracebacks on error")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- list ---
    p_list = sub.add_parser("list", help="List open merge requests")
    p_list.add_argument("project", help="GitLab project path")
    p_list.add_argument("--assigned", action="store_true", help="Only MRs assigned/requested for review by me")
    p_list.add_argument("--limit", type=int, default=25, help="Max number of results (default: 25)")
    p_list.add_argument("--json", action="store_true", help="Output as JSON array")

    # --- info ---
    p_info = sub.add_parser("info", help="Fetch merge request metadata as JSON")
    p_info.add_argument("project", help="GitLab project path or full MR URL")
    p_info.add_argument("mr_iid", type=int, nargs="?", help="Merge request IID (omit when project is a URL)")

    # --- diff ---
    p_diff = sub.add_parser("diff", help="Show raw unified diff of a merge request")
    p_diff.add_argument("project", help="GitLab project path or full MR URL")
    p_diff.add_argument("mr_iid", type=int, nargs="?", help="Merge request IID (omit when project is a URL)")
    p_diff.add_argument("--file", metavar="PATH", help="Show diff for a single file only")
    p_diff.add_argument("--full", action="store_true", help="Show full file content instead of diff (useful for full context review)")
    p_diff.add_argument("--blame", action="store_true", help="Append git blame annotation for each changed file")

    # --- comments ---
    p_comments = sub.add_parser("comments", help="List existing notes/discussions on a merge request")
    p_comments.add_argument("project", help="GitLab project path or full MR URL")
    p_comments.add_argument("mr_iid", type=int, nargs="?", help="Merge request IID (omit when project is a URL)")
    p_comments.add_argument("--system", action="store_true", help="Include system notes (e.g. 'pushed commit X', 'approved')")

    # --- post ---
    p_post = sub.add_parser("post", help="Post a comment to a merge request")
    p_post.add_argument("project", help="GitLab project path or full MR URL")
    p_post.add_argument("mr_iid", type=int, nargs="?", help="Merge request IID (omit when project is a URL)")
    p_post.add_argument(
        "body",
        nargs="?",
        default="-",
        help="Comment body, or '-' to read from stdin (default: stdin)",
    )
    p_post.add_argument("--file", metavar="PATH", help="File path for an inline comment")
    p_post.add_argument("--line", metavar="N", type=int, help="New-side line number for an inline comment")
    p_post.add_argument("--old-line", metavar="N", type=int, dest="old_line", help="Old-side line number (use for removed lines)")

    # --- file ---
    p_file = sub.add_parser("file", help="Fetch a file from the repository at a given ref")
    p_file.add_argument("project", help="GitLab project path")
    p_file.add_argument("file_path", help="Path to the file within the repository")
    p_file.add_argument("--ref", default="HEAD", metavar="REF", help="Branch, tag, or commit SHA (default: HEAD)")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global _debug
    parser = build_parser()
    args = parser.parse_args()
    _debug = args.debug
    config = AppConfig()

    dispatch = {
        "list": cmd_list,
        "info": cmd_info,
        "diff": cmd_diff,
        "comments": cmd_comments,
        "post": cmd_post,
        "file": cmd_file,
    }
    try:
        dispatch[args.command](args, config)
    except KeyboardInterrupt:
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        if _debug:
            traceback.print_exc()
        err(str(e))


if __name__ == "__main__":
    main()
