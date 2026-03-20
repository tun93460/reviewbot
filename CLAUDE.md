# ReviewBot

GitLab MR data fetcher for Claude Code. Claude does the reviewing — these scripts handle all GitLab API interaction.

## Commands

```bash
python rb.py list  <project> [--assigned] [--limit N] [--json]
python rb.py info  <project> [mr_iid]
python rb.py diff  <project> [mr_iid] [--file PATH]
python rb.py post  <project> [mr_iid] [body|-]
```

`<project>` is either a namespace/repo path (e.g. `group/repo`) or a **full GitLab MR URL** — when a URL is given, `mr_iid` is parsed from it automatically.

Add `--debug` to any command for full tracebacks.

## Typical workflow

1. **List MRs** — find what needs reviewing
   ```bash
   python rb.py list cca/edio/cca-lms --assigned --json
   ```

2. **Get metadata** — check scope before pulling the diff
   ```bash
   python rb.py info cca/edio/cca-lms 42
   ```
   Returns: title, author, branches, file list with line counts, pipeline status.

3. **Get the diff** — read the actual changes
   ```bash
   python rb.py diff cca/edio/cca-lms 42
   python rb.py diff cca/edio/cca-lms 42 --file src/foo.py   # single file
   ```

4. **Post a comment** — submit the review back to GitLab
   ```bash
   echo "review text" | python rb.py post cca/edio/cca-lms 42
   ```

## Output conventions

| Stream | Content |
|--------|---------|
| stdout | JSON (`list`, `info`, `post`) or raw diff text (`diff`) |
| stderr | Progress lines prefixed with `>>` |
| exit 0 | Success |
| exit 1 | Error message on stderr |

## Config (via `.env`)

| Variable | Required | Notes |
|----------|----------|-------|
| `GITLAB_TOKEN` | yes | Personal access token with `api` scope |
| `GITLAB_URL` | no | Defaults to `https://gitlab.com` |
| `GITLAB_USERNAME` | no | Used for `--assigned` filtering |

## Codebase

```
rb.py                   # CLI entry point — all subcommands
reviewbot/
  config.py             # AppConfig dataclass — loads .env
  gitlab_client.py      # GitLabClient, MRData, MRSummary
```
