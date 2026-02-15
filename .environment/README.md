# Environment scripts

This folder contains simple project environment scripts that can be run directly,
with or without Codex.

## Files

- `setup.sh` / `setup.cmd`
  - Installs dependencies from `requirements.txt` if the file exists.
- `maintainance.sh` / `maintainance.cmd`
  - Upgrades `pip`, then installs dependencies from `requirements.txt` if the file exists.

If `requirements.txt` is missing, dependency installation is skipped and the scripts
continue successfully.

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
