---
name: release
description: Information about how Shop'n'Cook releases work. Use when the user asks how to cut a release, bump the version, what publishes happen on a release, or how to roll out a new build to extension stores / app stores.
---

# Release process

Shop'n'Cook follows semantic versioning. Tags are `v<version>`, e.g. `v1.5.0` or
`v1.5.0-rc1`. Releasing is two steps: prepare a draft, then publish it.

## Step 1 — Prepare Release

Run the **Prepare Release** workflow
([`release-prepare.yml`](../../../.github/workflows/release-prepare.yml)) from
the Actions tab. Pick a `bump` of `patch`, `minor`, `major`, `rc`, or `explicit`
(with a `version` input).

It refuses to run unless master is releasable: the ref is `master`, every version
file agrees, the new version parses and sorts above every existing tag, no tag or
release already claims it, and the required test suites are green on HEAD.

Then it generates release notes from the commits since the last **stable** tag,
prepends them to `release-notes.md`, bumps every version file, commits
`chore(release): <version>` to master, and creates a **draft GitHub Release**.

**No tag is created at this point.** The draft carries a tag name that does not
exist yet; GitHub creates the tag when you publish. That is deliberate — it makes
a tag without a release impossible, which is how `v1.4.5` and `v1.4.6` ended up
tagged but never published under the old process.

## Step 2 — publish the draft

Review the generated notes in the draft release, edit if you want, and press
**Publish release**. The body you publish is what the stores show as "what's
new", so it is worth reading.

Publishing creates the tag and fires
[`release.yml`](../../../.github/workflows/release.yml), which drives the entire
rollout as one workflow run:

| Job | What it does |
| --- | --- |
| Browser extensions | Chrome Web Store, Firefox (AMO), Edge, Opera, Safari (TestFlight) |
| App stores | Google Play (draft), Apple App Store, Windows Store (MSIX) |
| Coolify production (backend) | Re-pins `api.shop-n-cook.com` to the tag and redeploys |
| Cloudflare production | `shop-n-cook.com` + `app.shop-n-cook.com` — waits for the backend first |

Because it is a single run, **Re-run failed jobs** retries only the target that
broke — useful because the external stores fail for reasons that have nothing to
do with the code. There is also a `workflow_dispatch` on `release.yml` with a
`targets` input to re-drive one target for an existing tag.

## Pre-releases

A version containing `-rcN` is published as a GitHub pre-release. Then:

- Chrome, Firefox, Edge and Opera are **skipped** (a submission in review blocks
  the next one, so RCs must not queue ahead of the real release).
- Safari still builds — everything lands in TestFlight first.
- Android goes to the `internal` track, iOS to the `beta` lane, Windows to a
  flight.
- **Cloudflare and Coolify production are skipped.** Pre-releases must not reach
  the production domains or the production API.

Stable releases go to Android `alpha`, iOS `release`, and Google Play submissions
land as **draft** — a human still promotes them in the Play Console.

## Where the version lives

`scripts/set-version.mjs` is the single source of truth for that list:

```bash
bun scripts/set-version.mjs --check    # verify every file agrees
bun scripts/set-version.mjs --print    # the current version
bun scripts/set-version.mjs 1.5.0      # write it everywhere
```

It updates the root, `frontend/`, `extension/` and `landing/` `package.json`,
`backend/pyproject.toml`, `extension/public/manifest.json` (where `version` is
the pre-release suffix stripped, because Chrome rejects it, and `version_name`
keeps the full string), and both Android version files. It also owns the Android
`versionCode` formula (`MAJOR*1000000 + MINOR*10000 + PATCH*100 + RC`, with 99
for a stable release so a stable outranks its own RCs).

Never bump versions by hand in a feature PR — the release workflow owns it.

## Release notes

`scripts/release-notes.mjs` generates them from Conventional Commits since the
last stable tag. Commit subjects become the bullets, so write them accordingly:
`feat(scope):` → Features, `fix:` → Fixes, `perf:` → Performance, `refactor:` →
Refactors, everything else → Internal. A `!` or a `BREAKING CHANGE:` footer
promotes a commit to Breaking changes. `chore(release):` commits are skipped, and
subjects that are not conventional are kept verbatim under Internal rather than
dropped.

The same generated text goes into `release-notes.md` **and** the release body, so
the file and the stores cannot drift apart.

## Backend and database

A release target like any other. `deploy-coolify.yml` re-pins the production
Coolify application's git ref to the released tag, redeploys it, waits for the
build, and asserts that `api.shop-n-cook.com` reports the released version. It
runs before the Cloudflare deploy so the API is upgraded ahead of the frontend
that calls it.

Staging is separate and unchanged: it still redeploys continuously from `master`
via the Coolify GitHub App. See `deployment.md`.

## Required secrets

`RELEASE_TOKEN` (a PAT or GitHub App token with `contents: write`) is what
`release-prepare.yml` pushes the bump commit with. It must not be the default
`GITHUB_TOKEN`: GitHub suppresses workflow runs for anything pushed with it, so
the released commit would get no CI.

`COOLIFY_URL`, `COOLIFY_API_TOKEN` and `COOLIFY_APP_UUID` live on the
`production` GitHub Environment and drive the backend deploy. Unlike the store
credentials these are **required** — the job fails rather than skipping, because
a backend that silently did not deploy leaves the frontend on the wrong API.

Store credentials are read per-target and each is skipped when its secret is
absent — see the `Check secret availability` steps in
[`publish-extension.yml`](../../../.github/workflows/publish-extension.yml) and
[`publish-stores.yml`](../../../.github/workflows/publish-stores.yml) for the
authoritative list.

## Reverting

For the backend, dispatch
[`deploy-coolify.yml`](../../../.github/workflows/deploy-coolify.yml) with
`environment: production` and `ref` set to the previous tag — it re-pins and
redeploys, and the version assertion confirms the rollback landed. Coolify also
keeps previous backend deploys around for a redeploy from its dashboard.

Everything else rolls forward: bump again to a new patch version with the fix
included.
