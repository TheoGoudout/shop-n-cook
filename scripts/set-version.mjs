#!/usr/bin/env bun
/**
 * Single source of truth for where the release version lives.
 *
 * Every file listed in TARGETS below carries the version in some form. Keeping
 * that list here — rather than as a pile of inline sed/jq steps in a workflow —
 * is what makes drift detectable: `--check` reads all of them back and fails if
 * they disagree.
 *
 *   bun scripts/set-version.mjs 1.5.0        write the version everywhere
 *   bun scripts/set-version.mjs 1.5.0-rc1    pre-release
 *   bun scripts/set-version.mjs --check      verify every file already agrees
 *   bun scripts/set-version.mjs --print      print the current version
 */

import { execFileSync } from "node:child_process"
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")

const SEMVER = /^(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?$/

/** Parse `1.5.0` / `1.5.0-rc1`, or throw. */
export function parseVersion(version) {
  const m = SEMVER.exec(version)
  if (!m) {
    throw new Error(
      `invalid version ${JSON.stringify(version)} — expected X.Y.Z or X.Y.Z-rcN`,
    )
  }
  const [, major, minor, patch, rc] = m
  return {
    version,
    major: Number(major),
    minor: Number(minor),
    patch: Number(patch),
    rc: rc === undefined ? null : Number(rc),
    /** Version with the pre-release suffix stripped (Chrome manifests reject it). */
    base: `${major}.${minor}.${patch}`,
    isPrerelease: rc !== undefined,
  }
}

/**
 * The version a bump leads to, from the current one.
 *
 * This used to be a `bun -e '...'` program embedded in release-prepare.yml,
 * with its own copy of the semver regex and its own idea of what "patch" means
 * on a release candidate. Two definitions of the version format is one too
 * many: `parseVersion` above is the one the nine version files are written
 * from, so it should also be the one the next version is computed with.
 */
export function nextVersion(current, bump, explicit = "") {
  if (bump === "explicit") {
    if (!explicit) throw new Error("bump = explicit requires the version input")
    // Validated, not just stripped: an unparseable --version input would
    // otherwise reach the tag and the nine version files unchallenged.
    return parseVersion(explicit.replace(/^v/, "")).version
  }

  const { major, minor, patch, rc } = parseVersion(current)
  switch (bump) {
    case "major":
      return `${major + 1}.0.0`
    case "minor":
      return `${major}.${minor + 1}.0`
    // Bumping patch off a release candidate promotes it: 1.5.0-rc2 -> 1.5.0
    case "patch":
      return rc === null ? `${major}.${minor}.${patch + 1}` : `${major}.${minor}.${patch}`
    case "rc":
      return rc === null
        ? `${major}.${minor}.${patch + 1}-rc1`
        : `${major}.${minor}.${patch}-rc${rc + 1}`
    default:
      throw new Error(`unknown bump ${bump}`)
  }
}

/**
 * Android versionCode. Must increase monotonically across every build ever
 * uploaded, and a stable release must outrank all of its own release candidates.
 *
 *   1.4.6-rc1 -> 1046001
 *   1.4.6     -> 1046099
 *
 * This formula used to live inline in publish-stores.yml and was sed-injected at
 * build time; it lives here now so the committed gradle file tells the truth and
 * there is only one implementation of it.
 */
export function versionCode({ major, minor, patch, rc }) {
  if (rc !== null && rc > 98) {
    throw new Error(`rc number ${rc} would collide with the stable marker (99)`)
  }
  return major * 1_000_000 + minor * 10_000 + patch * 100 + (rc ?? 99)
}

/**
 * Order two versions. Negative when `a` precedes `b`.
 *
 * Note this cannot be done with `sort -V`, which ranks `1.5.0-rc2` *above*
 * `1.5.0` and would therefore reject every promotion of a release candidate.
 * versionCode already encodes the right precedence (rc 01-98, stable 99), so
 * reuse it.
 */
export function compareVersions(a, b) {
  return versionCode(parseVersion(a)) - versionCode(parseVersion(b))
}

/** Highest existing `vX.Y.Z[-rcN]` tag, ignoring anything that doesn't parse. */
function highestTag() {
  let tags
  try {
    tags = execFileSync("git", ["tag", "--list"], { cwd: ROOT, encoding: "utf8" })
  } catch {
    return null
  }
  let best = null
  for (const line of tags.split("\n")) {
    const name = line.trim()
    if (!name.startsWith("v")) continue
    let parsed
    try {
      parsed = parseVersion(name.slice(1))
    } catch {
      continue // e.g. the stray capital-V tag in this repo's history
    }
    if (best === null || compareVersions(parsed.version, best) > 0) {
      best = parsed.version
    }
  }
  return best
}

// --- file handlers -------------------------------------------------------
//
// Each target knows how to read the version out of its file and how to write a
// new one back. `read` returns the full version string for --check; a target
// whose file cannot represent a pre-release suffix returns the base version and
// sets `baseOnly` so --check compares it against the stripped version instead.

/** Read/modify a JSON file while preserving Biome's 2-space + trailing-newline style. */
function editJson(relPath, mutate) {
  const path = join(ROOT, relPath)
  const json = JSON.parse(readFileSync(path, "utf8"))
  mutate(json)
  writeFileSync(path, `${JSON.stringify(json, null, 2)}\n`)
}

function readJson(relPath) {
  return JSON.parse(readFileSync(join(ROOT, relPath), "utf8"))
}

/** Replace text in a file via regex, asserting the pattern actually matched. */
function editText(relPath, replacements) {
  const path = join(ROOT, relPath)
  let text = readFileSync(path, "utf8")
  for (const [pattern, replacement] of replacements) {
    const before = text
    text = text.replace(pattern, replacement)
    if (text === before) {
      throw new Error(`${relPath}: pattern ${pattern} did not match anything`)
    }
  }
  writeFileSync(path, text)
}

function matchText(relPath, pattern) {
  const text = readFileSync(join(ROOT, relPath), "utf8")
  const m = pattern.exec(text)
  if (!m) throw new Error(`${relPath}: could not find a version (${pattern})`)
  return m[1]
}

const PYPROJECT_VERSION = /^version = "(.+)"$/m
const GRADLE_VERSION_NAME = /versionName "([^"]*)"/
const GRADLE_VERSION_CODE = /versionCode (\d+)/
/**
 * The `app` entry in uv.lock mirrors backend/pyproject.toml's version. `uv`
 * rewrites it on the next lock refresh, so leaving it alone means the bump
 * commit is followed by a stray diff — it had already drifted to 1.4.4 while
 * the backend was at 1.4.6.
 */
const UVLOCK_APP_VERSION = /(\[\[package\]\]\nname = "app"\nversion = )"([^"]*)"/

const TARGETS = [
  {
    path: "package.json",
    read: () => readJson("package.json").version,
    write: (v) => editJson("package.json", (j) => { j.version = v.version }),
  },
  {
    path: "frontend/package.json",
    read: () => readJson("frontend/package.json").version,
    write: (v) =>
      editJson("frontend/package.json", (j) => { j.version = v.version }),
  },
  {
    path: "extension/package.json",
    read: () => readJson("extension/package.json").version,
    write: (v) =>
      editJson("extension/package.json", (j) => { j.version = v.version }),
  },
  {
    path: "landing/package.json",
    read: () => readJson("landing/package.json").version,
    write: (v) =>
      editJson("landing/package.json", (j) => { j.version = v.version }),
  },
  {
    path: "backend/pyproject.toml",
    read: () => matchText("backend/pyproject.toml", PYPROJECT_VERSION),
    write: (v) =>
      editText("backend/pyproject.toml", [
        [PYPROJECT_VERSION, `version = "${v.version}"`],
      ]),
  },
  {
    path: "uv.lock",
    read: () => {
      const m = UVLOCK_APP_VERSION.exec(readFileSync(join(ROOT, "uv.lock"), "utf8"))
      if (!m) throw new Error("could not find the `app` package entry")
      return m[2]
    },
    write: (v) =>
      editText("uv.lock", [[UVLOCK_APP_VERSION, `$1"${v.version}"`]]),
  },
  {
    // Chrome rejects a pre-release suffix in `version`; `version_name` is the
    // human-facing string and keeps the full `-rcN`.
    path: "extension/public/manifest.json",
    baseOnly: true,
    read: () => readJson("extension/public/manifest.json").version,
    write: (v) =>
      editJson("extension/public/manifest.json", (j) => {
        j.version = v.base
        j.version_name = v.version
      }),
  },
  {
    path: "mobile/android/app/build.gradle",
    read: () => matchText("mobile/android/app/build.gradle", GRADLE_VERSION_NAME),
    write: (v) =>
      editText("mobile/android/app/build.gradle", [
        [GRADLE_VERSION_CODE, `versionCode ${versionCode(v)}`],
        [GRADLE_VERSION_NAME, `versionName "${v.version}"`],
      ]),
  },
  {
    path: "mobile/android/twa-manifest.json",
    read: () => readJson("mobile/android/twa-manifest.json").appVersionName,
    write: (v) =>
      editJson("mobile/android/twa-manifest.json", (j) => {
        j.appVersionName = v.version
        j.appVersionCode = versionCode(v)
        j.appVersion = v.version
      }),
  },
]

/** The version the repo currently claims, read from the backend as canonical. */
export function currentVersion() {
  return matchText("backend/pyproject.toml", PYPROJECT_VERSION)
}

function check() {
  const canonical = currentVersion()
  const parsed = parseVersion(canonical)
  const mismatches = []

  for (const target of TARGETS) {
    const expected = target.baseOnly ? parsed.base : parsed.version
    let actual
    try {
      actual = target.read()
    } catch (err) {
      mismatches.push(`${target.path}: ${err.message}`)
      continue
    }
    if (actual !== expected) {
      mismatches.push(
        `${target.path}: expected ${expected}, found ${actual ?? "(no version)"}`,
      )
    }
  }

  // The Android versionCode is derived, so verify it separately.
  const expectedCode = versionCode(parsed)
  for (const [path, actual] of [
    [
      "mobile/android/app/build.gradle",
      Number(matchText("mobile/android/app/build.gradle", GRADLE_VERSION_CODE)),
    ],
    [
      "mobile/android/twa-manifest.json",
      readJson("mobile/android/twa-manifest.json").appVersionCode,
    ],
  ]) {
    if (actual !== expectedCode) {
      mismatches.push(
        `${path}: expected versionCode ${expectedCode}, found ${actual}`,
      )
    }
  }

  if (mismatches.length > 0) {
    console.error(`Version drift (canonical is ${canonical}):`)
    for (const line of mismatches) console.error(`  - ${line}`)
    process.exit(1)
  }
  console.log(`All version files agree on ${canonical}.`)
}

function main() {
  const arg = process.argv[2]

  if (!arg) {
    console.error(
      "usage: set-version.mjs <version> | --check | --print" +
        " | --is-newer <version> | --validate <version>" +
        " | --next <patch|minor|major|rc|explicit> [version]",
    )
    process.exit(2)
  }
  if (arg === "--print") {
    console.log(currentVersion())
    return
  }
  if (arg === "--check") {
    check()
    return
  }
  if (arg === "--validate") {
    // Exits non-zero on anything parseVersion rejects. The shell callers used
    // to each carry their own `grep -qP '^\d+\.\d+\.\d+(-rc\d+)?$'`.
    console.log(parseVersion(process.argv[3] ?? "").version)
    return
  }
  if (arg === "--next") {
    console.log(nextVersion(currentVersion(), process.argv[3] ?? "", process.argv[4] ?? ""))
    return
  }
  if (arg === "--is-newer") {
    const candidate = parseVersion(process.argv[3] ?? "").version
    const highest = highestTag()
    if (highest === null) {
      console.log(`No existing tags; ${candidate} is acceptable.`)
      return
    }
    if (compareVersions(candidate, highest) <= 0) {
      console.error(
        `${candidate} does not sort above the highest existing tag v${highest}.`,
      )
      process.exit(1)
    }
    console.log(`${candidate} sorts above the highest existing tag v${highest}.`)
    return
  }

  const parsed = parseVersion(arg)
  for (const target of TARGETS) {
    target.write(parsed)
    console.log(
      `  ${target.path} -> ${target.baseOnly ? parsed.base : parsed.version}`,
    )
  }
  console.log(
    `Set version to ${parsed.version} (Android versionCode ${versionCode(parsed)}).`,
  )
}

if (import.meta.main) main()
