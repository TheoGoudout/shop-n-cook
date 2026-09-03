# Workflow scripts

Every multi-line step body in `.github/workflows/` lives here as a file. A workflow
is a list of named steps and their inputs; the logic those steps run is shell that
`shellcheck` lints, `git blame` explains and a contributor can execute by hand.

`scripts/validate_workflow_scripts.py` enforces the convention, and the `shellcheck`
hook in `.pre-commit-config.yaml` lints the result. Both run in `pre-commit.yml`.

Before this existed there were roughly 1,300 lines of shell — and a little Python
and PowerShell — inside YAML strings, including the sixty-five-line `gh api` loop
that decides whether master is green enough to release from. None of it had ever
been read by a linter, and none of it could be run outside a GitHub runner.

## Layout

```
lib/            sourced, never executed — no shebang, not executable
shared/         standalone scripts more than one workflow calls
<workflow>/     one directory per workflow file, one script per step
```

A script's name comes from its step's `name:`, kebab-cased, so a step and its file
can be found from each other: `Trigger the deployment` in `deploy-coolify.yml` is
`deploy-coolify/trigger-the-deployment.sh`.

## Conventions

**Shebang and flags.** `#!/usr/bin/env bash`, then `set -euo pipefail`, then the
executable bit. The runner's default `bash -e` is weaker than that in ways that hide
failures — an unset variable expanding to nothing, a pipeline whose first command
dies — so an extracted script does not inherit it, it declares it.

**GitHub expressions never reach the argument list.** A `${{ … }}` value goes in the
step's `env:` block and the script reads the environment variable:

```yaml
- name: Publish the submission
  env:
    TOKEN: ${{ steps.token.outputs.token }}
  run: .github/scripts/publish-extension/publish-the-submission.sh
```

Interpolating one into the command line would put attacker-controllable text through
a shell parse — the template-injection class zizmor audits for. It is also how a
secret ends up in a process's argv, which is visible to anything else on the runner
and survives into a `set -x` trace: `web-ext sign --api-key ${{ secrets.… }}` and
`gradlew -Pstore_password=${{ secrets.… }}` were both written that way here.
Positional arguments carry only literals written in the workflow itself: a path, a
label.

**The working directory is the repository root.** GitHub runs a step there, so that
is what a script gets, and it should not need anything else. A script that must work
somewhere else takes the directory as an argument and `cd`s to it. A script that is
also runnable by hand resolves the root itself:

```bash
ROOT=$(cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$ROOT"
```

**Comments come too.** The explanation of *why* a step does something the way it does
is the most valuable thing in it. It moves with the code rather than staying behind in
the YAML, where it would describe a `run:` line that no longer says anything.

**GitHub's step protocol still applies.** `$GITHUB_OUTPUT`, `$GITHUB_STEP_SUMMARY`
and `::error::` work in a script exactly as they do inline, because they are a file
path and a stdout convention rather than anything the runner parses out of the YAML.
So does `::add-mask::`, which is the one every script minting a token owes its
caller.

**Not every step is bash.** `publish-stores.yml`'s Windows job runs on
`windows-latest`, so its scripts are `.ps1` and the shebang rule does not apply to
them; the step names them with an explicit `shell: pwsh`. Everything else here —
the naming, the env-not-argv rule, the comments — is the same.
