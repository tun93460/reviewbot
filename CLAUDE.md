# ReviewBot

GitLab MR data fetcher for Claude Code. Claude does the reviewing — these scripts handle all GitLab API interaction.

## Commands

```bash
python rb.py list  <project> [--assigned] [--limit N] [--json]
python rb.py info  <project> [mr_iid]
python rb.py diff  <project> [mr_iid] [--file PATH] [--full]
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
   python rb.py diff cca/edio/cca-lms 42 --file src/foo.py --full  # full file text (best for accessibility/context review)
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

---

## WCAG Accessibility Review

This team is actively reviewing MRs for WCAG 2.1 AA compliance. When reviewing any MR that touches HTML, templates, CSS, or UI components, check the following.

### Images & media
- Every `<img>` has an `alt` attribute. Decorative images use `alt=""`. Informative images have meaningful, concise alt text (describe the content/function, not "image of…").
- `<svg>` used as icons: either `aria-hidden="true"` (decorative) or has accessible name via `<title>` + `aria-labelledby`.
- Video/audio has captions or transcripts where applicable.

### Keyboard & focus
- All interactive elements (`button`, `a`, `input`, custom widgets) are reachable and operable by keyboard alone (Tab, Enter, Space, arrow keys where expected).
- No positive `tabindex` values (≥1) — these break natural tab order.
- `tabindex="-1"` is only used to programmatically manage focus (e.g., modals, skip links), not to remove naturally focusable elements.
- Focus is never lost or trapped unexpectedly. Modals/dialogs trap focus while open and restore it on close.
- Visible focus indicator is present — check that CSS doesn't globally remove `outline` without a replacement style.
- Skip navigation link present if page has repeated navigation.

### Semantics & structure
- Heading hierarchy is logical (`h1` → `h2` → `h3`, no skipped levels). Headings convey structure, not just styling.
- Lists use `<ul>`/`<ol>` + `<li>`, not `<div>`/`<span>` styled to look like lists.
- Interactive elements are real `<button>` or `<a>` (with `href`), not `<div>`/`<span>` with click handlers.
- `<a>` tags used for navigation, `<button>` for actions — not interchangeable.
- Form inputs have associated `<label>` (via `for`/`id` or wrapping) — not just placeholder text.
- Error messages are programmatically associated with their input (`aria-describedby`) and describe how to fix the problem.
- `<table>` has `<caption>` and `<th>` with `scope` attribute for data tables.

### ARIA
- ARIA is used to supplement semantics, not replace them. Prefer native HTML elements.
- `role` values are valid and appropriate. No overriding native semantics unnecessarily (e.g., `<button role="button">` is redundant; `<div role="button">` is a smell).
- Every interactive ARIA widget has an accessible name (`aria-label`, `aria-labelledby`, or visible label).
- ARIA states are toggled correctly in JS: `aria-expanded`, `aria-selected`, `aria-checked`, `aria-disabled` kept in sync with visual state.
- Dynamic content updates use `aria-live` regions where users need to be notified of changes (form errors, status messages, loading indicators).
- `aria-hidden="true"` is not applied to elements that are focusable or contain focusable children.

### Color & visual
- Information is not conveyed by color alone (e.g., error states also use an icon or text, required fields aren't only marked red).
- Text contrast ≥ 4.5:1 for normal text, ≥ 3:1 for large text (18pt / 14pt bold) and UI components.
- When reviewing CSS changes, flag any new color combinations for contrast. (Exact values require a tool, but note obviously low-contrast combinations.)

### Language & page
- `<html lang="...">` is set correctly. If a page contains a passage in a different language, it has `lang` on that element.
- Page `<title>` is present and descriptive.

### Common patterns to flag immediately
- `onClick` on a non-interactive element (`<div>`, `<span>`, `<p>`) with no `role`, `tabindex`, or keyboard handler
- `placeholder` as the only label for an input
- Icon-only buttons with no `aria-label` and no visually hidden text
- `display:none` / `visibility:hidden` replaced with opacity/transform to "hide" content (still accessible to AT)
- Autoplaying media with no controls
- Form submission errors that only change visual styling with no associated text feedback
