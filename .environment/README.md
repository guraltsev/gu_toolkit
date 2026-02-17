# Environment scripts

This folder contains simple project environment scripts that can be run directly,
with or without Codex.

## Files

- `setup.sh` / `setup.cmd`
  - Installs dependencies from `requirements.txt` if the file exists.
- `maintainance.sh` / `maintainance.cmd`
  - Upgrades `pip`, then installs dependencies from `requirements.txt` if the file exists.
- `install_test_tools.py`
  - First attempts to install real `pytest-cov`; if that is unavailable (common in offline Codex environments), installs a local fallback pytest plugin shim so `pytest --cov ...` commands do not fail on argument parsing.
- `pytest_cov_shim/`
  - Local editable package used by `install_test_tools.py`; accepts `--cov`/`--cov-report` options and emits a clear summary that real coverage was not generated.

If `requirements.txt` is missing, dependency installation is skipped and the scripts
continue successfully.

Both setup scripts also run `install_test_tools.py` after dependency installation.

## Run without Codex

From the repository root:

### Bash

```bash
./.environment/setup.sh
./.environment/maintainance.sh
```

### Windows CMD

```cmd
.environment\setup.cmd
.environment\maintainance.cmd
```

## Use with Codex

Point your Codex setup and maintenance script paths to files in this folder.

Example:

- setup script: `.environment/setup.sh`
- maintenance script: `.environment/maintainance.sh`

For Windows environments, use the `.cmd` variants.
