#!/usr/bin/env bun
/**
 * Generate release notes from Conventional Commits.
 *
 * The notes this produces are used twice: written into release-notes.md and used
 * verbatim as the GitHub Release body (which is what the Play Store, App Store
 * and AMO show as "what's new"). Generating them once removes the hand
 * transcription that let release-notes.md fall behind by three versions.
 *
 *   bun scripts/release-notes.mjs --version 1.5.0
 *   bun scripts/release-notes.mjs --version 1.5.0 --from v1.4.4
 *   bun scripts/release-notes.mjs --version 1.5.0 --insert
 *
 * Without --from, the range starts at the most recent *stable* tag, so the notes
 * for a stable release cover everything since the last stable release rather
 * than only the delta since its own last release candidate.
 */

import { execFileSync } from "node:child_process"
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const NOTES_FILE = join(ROOT, "release-notes.md")

/** Conventional Commit subject: type(scope)!: description */
const CONVENTIONAL = /^(\w+)(?:\(([^)]*)\))?(!)?:\s*(.+)$/

/** Commits that describe the release plumbing itself, not the release. */
const SKIP_SUBJECT = /^chore(\([^)]*\))?:\s*(bump version|release)\b/i

/**
 * Commit type -> section. Order here is the order sections appear in the notes.
 * Anything unmapped (including non-conventional subjects) falls into Internal
 * rather than being silently dropped.
 */
const SECTIONS = [
  ["Breaking changes", []],
  ["Features", ["feat"]],
  ["Fixes", ["fix"]],
  ["Performance", ["perf"]],
  ["Refactors", ["refactor"]],
  ["Internal", ["chore", "ci", "build", "style", "test", "docs", "revert"]],
]

const SECTION_FOR_TYPE = new Map()
for (const [section, types] of SECTIONS) {
  for (const type of types) SECTION_FOR_TYPE.set(type, section)
}

function git(...args) {
  return execFileSync("git", args, { cwd: ROOT, encoding: "utf8" }).trim()
}

/** Most recent stable (non-rc) tag reachable from HEAD, or null if there is none. */
export function lastStableTag() {
  let tags
  try {
    tags = git("tag", "--list", "v*", "--sort=-v:refname").split("\n")
  } catch {
    return null
  }
  for (const tag of tags) {
    const name = tag.trim()
    if (/^v\d+\.\d+\.\d+$/.test(name)) return name
  }
  return null
}

/** Turn a scope into the `Android:` / `Shopping list:` prefix the file already uses. */
function formatScope(scope) {
  if (!scope) return ""
  const known = {
    ci: "CI",
    api: "API",
    db: "DB",
    ui: "UI",
    ios: "iOS",
    e2e: "E2E",
  }
  if (known[scope.toLowerCase()]) return `${known[scope.toLowerCase()]}: `
  return `${scope.charAt(0).toUpperCase()}${scope.slice(1)}: `
}

function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/**
 * Collect commits in `from..to` into sections.
 * A commit is breaking if its subject carries `!` or its body has a
 * `BREAKING CHANGE:` footer.
 */
export function collect({ from, to = "HEAD" }) {
  const range = from ? `${from}..${to}` : to
  // \x1e separates commits, \x1f separates fields — neither appears in messages.
  const raw = git("log", range, "--no-merges", "--pretty=format:%s%x1f%b%x1e")
  const buckets = new Map(SECTIONS.map(([name]) => [name, []]))

  for (const entry of raw.split("\x1e")) {
    const record = entry.trim()
    if (!record) continue
    const [subject = "", body = ""] = record.split("\x1f")
    if (!subject || SKIP_SUBJECT.test(subject)) continue

    const match = CONVENTIONAL.exec(subject)
    const breaking =
      (match && match[3] === "!") || /^BREAKING[ -]CHANGE:/m.test(body)

    let section
    let bullet
    if (match) {
      const [, type, scope, , description] = match
      section = SECTION_FOR_TYPE.get(type.toLowerCase()) ?? "Internal"
      bullet = `${formatScope(scope)}${capitalize(description)}`
    } else {
      // Non-conventional subject (they exist in this repo's history) — keep it
      // verbatim under Internal rather than losing it.
      section = "Internal"
      bullet = capitalize(subject)
    }
    if (breaking) section = "Breaking changes"

    const list = buckets.get(section)
    if (!list.includes(bullet)) list.push(bullet)
  }

  return buckets
}

/** Render the `## X.Y.Z` markdown section. Returns null when there is nothing. */
export function render(version, buckets) {
  const parts = []
  for (const [name] of SECTIONS) {
    const items = buckets.get(name)
    if (!items || items.length === 0) continue
    parts.push(`### ${name}\n`)
    for (const item of items) parts.push(`* ${item}`)
    parts.push("")
  }
  if (parts.length === 0) return null
  return `## ${version}\n\n${parts.join("\n").trimEnd()}\n`
}

/** Prepend a rendered section directly under the `# Release Notes` heading. */
export function insert(section) {
  const existing = readFileSync(NOTES_FILE, "utf8")
  const heading = "# Release Notes\n"
  if (!existing.startsWith(heading)) {
    throw new Error(`release-notes.md must start with ${JSON.stringify(heading)}`)
  }
  const rest = existing.slice(heading.length).replace(/^\n+/, "")
  writeFileSync(NOTES_FILE, `${heading}\n${section}\n${rest}`)
}

function parseArgs(argv) {
  const args = {}
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === "--insert") args.insert = true
    else if (arg.startsWith("--")) args[arg.slice(2)] = argv[++i]
  }
  return args
}

function main() {
  const args = parseArgs(process.argv.slice(2))
  if (!args.version) {
    console.error(
      "usage: release-notes.mjs --version <X.Y.Z> [--from <tag>] [--to <ref>] [--insert]",
    )
    process.exit(2)
  }

  const from = args.from ?? lastStableTag()
  const buckets = collect({ from, to: args.to ?? "HEAD" })
  const section = render(args.version, buckets)

  if (!section) {
    console.error(
      `No release-worthy commits found in ${from ?? "(root)"}..${args.to ?? "HEAD"}.`,
    )
    process.exit(1)
  }

  if (args.insert) {
    insert(section)
    console.error(`Inserted ${args.version} into release-notes.md (since ${from}).`)
  }
  // The section always goes to stdout so a workflow can capture it for the
  // release body in the same step that writes the file.
  process.stdout.write(section)
}

if (import.meta.main) main()
