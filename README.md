# ReviewBot

GitLab MR data fetcher designed for use within Claude Code. Claude does the reviewing — these scripts handle all GitLab API interaction.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GITLAB_TOKEN
```

## Usage

```
python rb.py <command> [options]
```

`<project>` accepts a namespace/repo path **or** a full GitLab MR URL. When a URL is given, `<mr_iid>` is parsed automatically.

### Commands

| Command | Description |
|---|---|
| `list <project>` | List open MRs |
| `info <project> <mr_iid>` | Fetch MR metadata as JSON |
| `diff <project> <mr_iid>` | Show unified diff |
| `comments <project> <mr_iid>` | List existing notes/discussions |
| `post <project> <mr_iid> [body\|-]` | Post a top-level or inline comment |
| `file <project> <file_path>` | Fetch any file from the repo |

### Options

**`diff`**
- `--file PATH` — show diff for a single file only
- `--full` — show full file content instead of diff
- `--blame` — append git blame annotation for each file

**`comments`**
- `--system` — include system notes (push events, approvals, etc.)

**`post`**
- `--file PATH --line N` — post an inline comment on a new-side line
- `--old-line N` — target an old-side (removed) line instead

**`file`**
- `--ref REF` — branch, tag, or commit SHA (default: HEAD)

**all commands**
- `--debug` — show full tracebacks on error

### Examples

```bash
# List your assigned MRs as JSON
python rb.py list group/repo --assigned --json

# Get MR metadata (includes diff_truncated, per-file too_large flags)
python rb.py info group/repo 42

# Show full diff; if large, warns on stderr and flags truncated files
python rb.py diff group/repo 42

# Show diff for one file with blame
python rb.py diff group/repo 42 --file src/auth.py --blame

# Fetch a file for full context (useful when diff is truncated)
python rb.py file group/repo src/base_component.py

# Read existing review comments before posting
python rb.py comments group/repo 42

# Post a top-level comment from stdin
echo "LGTM" | python rb.py post group/repo 42

# Post an inline comment on a specific line
echo "missing alt text" | python rb.py post group/repo 42 --file src/Modal.vue --line 34

# Use a full MR URL instead of project + IID
python rb.py diff https://gitlab.com/group/repo/-/merge_requests/42
```

## Config

Via `.env` or environment variables:

| Variable | Required | Notes |
|---|---|---|
| `GITLAB_TOKEN` | yes | Personal access token with `api` scope |
| `GITLAB_URL` | no | Defaults to `https://gitlab.com` |
| `GITLAB_USERNAME` | no | Used for `--assigned` filtering in `list` |

## Testing

```bash
pip install pytest pytest-mock
python -m pytest tests/
```
