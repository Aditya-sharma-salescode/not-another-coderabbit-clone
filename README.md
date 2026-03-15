# PR Reviewer

AI-powered PR review tool for the channelkart-flutter codebase. Reviews PRs against Jira tickets, Figma designs, LOB-specific behavior history, and git diffs using Claude.

## Architecture

```
reviewer/
├── main.py              ← Click CLI: `review` + `update-registry`
├── config.py             ← Env var loader + validator
├── git_analyzer.py       ← Unified diff parser → ChangedFile objects
├── github_client.py      ← GitHub REST API (PR data, post comments)
├── jira_client.py        ← Jira Cloud REST v3 + ADF→text + JQL
├── figma_client.py       ← Figma REST v1 + node tree → specs
├── lob_mapper.py         ← File paths → features → LOBs
├── registry.py           ← Read/write registry JSONs
├── prompt_builder.py     ← Assemble 6-section Claude prompt
└── ai_reviewer.py        ← Anthropic API call + response parser
```

## Setup

1. Clone and install:
```bash
git clone <repo-url> && cd pr-reviewer
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Fill in your API keys
```

3. Bootstrap the registry (one-time, requires Flutter repo):
```bash
python scripts/bootstrap_registry.py --flutter-repo-path /path/to/channelkart-flutter
```

## Usage

### Review a PR
```bash
python -m reviewer.main review \
  --pr-number 123 \
  --repo your-org/channelkart-flutter \
  --branch "CSLC-235-van-loadout"
```

### Update registry after merge
```bash
python -m reviewer.main update-registry \
  --registry-path registry \
  --flutter-repo-path /path/to/flutter-repo \
  --changed-files "lib/features/cart/model/cart.dart" \
  --jira-key COCA-850 \
  --commit-sha abc123
```

### Docker
```bash
docker build -t pr-reviewer .
docker run --env-file .env pr-reviewer review --pr-number 123 --repo org/repo
```

## GitHub Actions

Template workflows for the Flutter repo are in `github-actions-templates/`:

- **pr-lint-check.yml** — Runs `flutter analyze` + `dart format` on changed files
- **pr-ai-reviewer.yml** — Runs AI review on every PR (opened/updated)
- **registry-update.yml** — Updates feature registry on merge to master
- **PULL_REQUEST_TEMPLATE.md** — PR template with checklists

Copy these to your Flutter repo's `.github/workflows/` and `.github/` directories.

## How It Works

1. **Extract Jira ticket** from branch name → fetch AC, description, epic, open bugs
2. **Detect Figma URLs** in Jira/PR body → fetch design specs via Figma API
3. **Map changed files** to features via registry index (longest prefix match)
4. **Load historical context** — LOB overrides, past Jira tickets, git file history
5. **Build 6-section prompt** with token budgeting (<100k tokens)
6. **Send to Claude** (claude-sonnet-4-6) → structured review
7. **Post review comment** on GitHub PR with `<!-- AI-REVIEWER-v1 -->` marker

## Review Output Sections

- Summary
- Critical Issues (file + line + fix)
- Warnings
- LOB Impact (SAFE / AT RISK / UNKNOWN per LOB)
- Figma Compliance (Expected vs Found vs Fix)
- Test Coverage
- Positive Observations
- Merge Recommendation (APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `GITHUB_TOKEN` | Yes | GitHub PAT with repo + PR write |
| `JIRA_BASE_URL` | No | Jira Cloud base URL |
| `JIRA_EMAIL` | No | Jira auth email |
| `JIRA_API_TOKEN` | No | Jira API token |
| `FIGMA_ACCESS_TOKEN` | No | Figma personal access token |
| `GITHUB_REPO` | CI | owner/repo format |
| `PR_NUMBER` | CI | PR number to review |
| `REGISTRY_PATH` | No | Path to registry dir (default: `registry`) |

## Tests

```bash
pip install -e ".[dev]"
pytest tests/
```
