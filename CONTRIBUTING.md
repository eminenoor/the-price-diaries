# Contributing

This is a personal project, but it follows the same workflow a team would. This file describes how changes are made.

## Setup

```bash
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..
uvx pre-commit install --hook-type pre-commit --hook-type commit-msg
```

The pre-commit hooks format Python code and check commit messages before each commit.

## Branches

`main` always works. Every change happens on a short-lived branch and is merged with a pull request, even when working alone, so CI runs before anything reaches `main`.

| Prefix | Use for | Example |
| --- | --- | --- |
| `feat/` | New features | `feat/telegram-alerts` |
| `fix/` | Bug fixes | `fix/trendyol-price-selector` |
| `docs/` | Documentation only | `docs/setup-windows` |
| `refactor/` | Code changes with no behaviour change | `refactor/split-checker` |
| `chore/` | Tooling, dependencies, CI | `chore/update-deps` |

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <what changed, imperative, lowercase, no period>

<optional body: why, not how. Wrap at 72 characters.>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.

**Scopes** used in this repo: `api`, `parsers`, `fetcher`, `analysis`, `db`, `ui`, `deps`.

Good examples:

```
feat(parsers): add Eve Shop store
fix(parsers): read Trendyol price from discounted price element
feat(analysis): flag unusual price rises with modified z-score
test(api): cover duplicate product links
docs: add screenshots to README
chore(deps): bump fastapi to 0.116
```

Avoid messages like `update`, `fix stuff`, `wip` or `final version`.

Rules of thumb:

- **One logical change per commit.** If the message needs "and", it's probably two commits.
- **Every commit should pass the tests**, so history stays usable with `git bisect`.
- Write the subject so it completes the sentence "If applied, this commit will …".

## Adding a store

1. Add a `Store(...)` entry in `backend/src/price_diaries/parsers/sites.py` with its domains and price selectors. To find a selector, open a product page, right-click the price, choose **Inspect**, and note a stable class name.
2. Set `needs_browser=True` if the price only appears after JavaScript runs. A quick test: view the page source (Ctrl+U) and search for the price.
3. Add a case to `test_store_selectors` and `test_store_lookup` in `backend/tests/test_parsers.py`.
4. Commit as `feat(parsers): add <store> store`.

## Database changes

Change the models in `db.py`, then create a migration:

```bash
cd backend
uv run alembic -c alembic.ini revision --autogenerate -m "add notes to products"
```

Review the generated file in `migrations/versions/` before committing it.

## Before opening a pull request

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && npm run lint && npm test && npm run build
```
