#!/usr/bin/env bash
# Push the reformatting the hooks just did back onto the pull request branch.
#
# Only reached on the own-repo path, where the checkout above used the
# PRE_COMMIT PAT: a push authenticated with GITHUB_TOKEN does not trigger other
# workflows, so the branch would go quiet after the autofix commit. Forks take
# the pre-commit-ci/lite-action path instead and never get here.
set -euo pipefail

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git add -A
if git diff --staged --quiet; then
  echo "No changes to commit"
else
  git commit -m "🎨 Auto format and update with pre-commit"
  git push
fi
