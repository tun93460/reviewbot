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

### Commands

| Command | Description |
|---|---|
| `list <project>` | List open MRs |
| `info <project> <mr_iid>` | Fetch MR metadata as JSON |
| `diff <project> <mr_iid>` | Show raw unified diff |
| `post <project> <mr_iid> [body\|-]` | Post a comment (body or stdin) |

`<project>` accepts a namespace/repo path **or** a full GitLab MR URL. When a URL is given, `<mr_iid>` is parsed automatically.

### Examples

```bash
# List your assigned MRs as JSON
python rb.py list group/repo --assigned --json

# Get MR metadata
python rb.py info group/repo 42

# Show full diff
python rb.py diff group/repo 42

# Show diff for one file
python rb.py diff group/repo 42 --file src/auth.py

# Post a comment from stdin
echo "LGTM" | python rb.py post group/repo 42

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
