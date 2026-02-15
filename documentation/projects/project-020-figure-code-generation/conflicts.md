# Merge Conflict Notes: `/claude/smart-figure-code-generation-0bZri` -> `main`

## Context
A local merge attempt was prepared in this workspace, but the source ref `/claude/smart-figure-code-generation-0bZri` and a local `main` branch are not present in the repository metadata currently available in this environment.

Commands used to verify ref availability:

- `git branch -a`
- `git show-ref --heads --tags`
- `cat .git/packed-refs`

## Conflict status
Because the source branch ref is unavailable in this checkout, no line-level merge conflicts could be generated in this environment.

## Proposed conflict-resolution workflow (when refs are available)
1. Ensure both branches exist locally:
   - `git fetch <remote> main claude/smart-figure-code-generation-0bZri`
2. Check out `main` and create an integration branch.
3. Merge the feature branch with `--no-ff`.
4. Resolve conflicts file-by-file, prioritizing:
   - Preservation of existing public API contracts in `main`.
   - Retention of figure code-generation behavior from the feature branch.
   - Updated tests and documentation where behavior diverges.
5. Run the full test suite and smoke-check representative figure-generation flows.
6. Commit conflict resolutions with a dedicated merge-resolution message.

## Resolution notes template
When the missing refs become available, append concrete notes under this section:

- **Conflicted file:** `<path>`
- **Conflict type:** content/rename/delete
- **Resolution decision:** `<kept main|kept feature|manual synthesis>`
- **Rationale:** `<why this choice preserves behavior and compatibility>`
