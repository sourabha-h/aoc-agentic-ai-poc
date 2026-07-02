Thank you for your interest in contributing to this Agentic AI POC.

Guidelines
- Keep changes focused and minimal; do not alter core application logic for trivial changes.
- Open an issue first for larger features or breaking changes.
- Follow existing code style and add tests for new behaviour when applicable.

Running tests
- Create and activate a Python virtual environment (do not install globally):
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt  # if present
  ```

Secret scanning (local)
- This repo should not contain real secrets. To scan locally you can use one of the following (do not install system-wide if you prefer a venv):
  - Using Docker (recommended when available):
    ```bash
    docker run --rm -v "$(pwd)":/repo zricethezav/gitleaks:8.13.0 detect --source /repo
    ```
  - Using `truffleHog` (install in a virtualenv):
    ```bash
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install truffleHog
    truffleHog filesystem --directory .
    ```
  - Using `gitleaks` binary (install per your OS) or the GitHub Action included in `.github/workflows`.

If you find a secret in this repository
- Immediately rotate the exposed credential and remove it from the repo history (use `git rm --cached <file>` then commit, or use tools such as `git filter-repo`/BFG to fully purge history). Create an issue or PR describing the remediation.

Pull Request checklist
- Tests added/updated where relevant
- No credentials or secrets in changes
- CI passing (if applicable)

Thank you — contributions are welcome but please focus on safe, demonstrable improvements.
