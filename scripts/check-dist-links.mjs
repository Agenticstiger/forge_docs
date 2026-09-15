#!/usr/bin/env node
/**
 * check-dist-links.mjs — the only gate in this repo that reads what actually
 * deploys.
 *
 * WHY THIS EXISTS
 * ---------------
 * Every other link gate here reads SOURCE MARKDOWN:
 *
 *   - the bundled @vuepress/plugin-links-check (config.ts: linksCheck.build =
 *     'error') inspects markdown link tokens and filters targets on
 *     /\.md(?:[?#]|$)/, so it sees roughly 861 of ~1331 internal links and
 *     nothing that is not written as a .md target;
 *   - link-check.yml's base-prefix-check greps `](/…)` in docs/**.md;
 *   - link-check.yml's lychee-source runs lychee over docs/**.md.
 *
 * None of them can see the rendered artifact. Consequences, all proven against
 * this checkout:
 *
 *   - a one-character typo in the navbar or sidebar array in
 *     docs/.vuepress/config.ts ships a live 404 on 212 of 213 pages while all
 *     five existing gates exit 0, because config.ts is not markdown;
 *   - the landing page hero buttons live in docs/README.md FRONTMATTER, not in
 *     its body, so no markdown-link gate reads them;
 *   - raw HTML anchors in markdown, `.html`-suffixed targets and extensionless
 *     targets are invisible to the .md filter.
 *
 * So this walks docs/.vuepress/dist/**.html — the bytes that get uploaded —
 * and checks every absolute reference against the files that are actually
 * there.
 *
 * DESIGNED AGAINST THE FAILURE MODE THIS REPO KEEPS HITTING
 * --------------------------------------------------------
 * The recurring defect class here is A GATE THAT REPORTS GREEN WHILE MEASURING
 * THE WRONG THING (a lychee flag that made it exit before checking a URL; a
 * log-string grep that passed when the wording changed; a per-line grep -v that
 * threw a broken link away with a good one on the same line). Four structural
 * defences, in order of importance:
 *
 *   1. CANARIES RUN IN-PROCESS, ALWAYS, BEFORE THE REAL SCAN. A synthetic
 *      fixture carries one link that must resolve, one that must 404 and one
 *      that is missing the base prefix. The real scan does not start until the
 *      checker has proven, this run, that it both resolves and rejects. They
 *      are not a separate workflow step precisely because a separate step can
 *      be deleted while the gate keeps reporting green.
 *   2. FLOORS on pages walked, absolute references examined and DISTINCT
 *      targets resolved. A regex that decays to matching one link shape, or a
 *      walk that finds an empty dist, fails instead of passing.
 *   3. EVERY PAGE MUST CONTRIBUTE. A page that yields zero absolute references
 *      is an extraction failure, not a clean page — except the handful of
 *      genuinely self-contained pages named in ZERO_REF_ALLOWLIST.
 *   4. IT PRINTS ITS CENSUS. Counts per resolution rule, per exclusion class,
 *      the busiest targets. "Passed" with no numbers is indistinguishable from
 *      "inspected nothing".
 *
 * PRIOR ART (searched before building; see the reuse note at the end of this
 * comment)
 * -------------------------------------------------------------------------
 *   - lychee            https://github.com/lycheeverse/lychee
 *   - hyperlink         https://github.com/untitaker/hyperlink
 *   - htmltest          https://github.com/wjdp/htmltest
 *   - html-proofer      https://github.com/gjtorikian/html-proofer
 *   - proof-html        https://github.com/anishathalye/proof-html
 *   - check-html-links  https://github.com/modernweb-dev/check-html-links
 *
 * All six check built HTML. None of them can express the rule that actually
 * matters here — "an absolute reference MUST begin with /forge_docs/" — and
 * that is not a gap worth papering over: proof-html's swap_urls approach strips
 * the base before checking, which makes a link missing the base
 * indistinguishable from one carrying it, i.e. it silently passes the exact bug
 * this gate exists for. hyperlink explicitly refuses pretty URLs ("one cannot
 * request /mypage and expect mypage.html"), which is 43 false failures on this
 * site. And none of them assert a floor on what they inspected or print an
 * inspection census, which is requirement 1-4 above.
 *
 * Reuse strategy: ADAPT THE PATTERN, do not add a dependency.
 *   - scope ("check the built output, all tag types, internal only") is
 *     htmltest's CheckInternal and check-html-links' model;
 *   - the must-resolve / must-not-resolve canary pair is lifted from this
 *     repo's own lychee-source job in .github/workflows/link-check.yml, which
 *     established the discipline after lychee "ran" 12 scheduled times while
 *     checking nothing;
 *   - implemented in pure Node with no imports beyond node: builtins, so it
 *     runs in the same job right after `npm run docs:build` with no extra
 *     toolchain, no network and nothing to install.
 *
 * Usage:
 *   node scripts/check-dist-links.mjs                 # canaries, then scan dist
 *   node scripts/check-dist-links.mjs --self-test     # canaries only
 *   node scripts/check-dist-links.mjs --relative=error  # also fail on broken
 *                                                       # RELATIVE refs (see
 *                                                       # KNOWN GAPS below)
 *   node scripts/check-dist-links.mjs --dist DIR --base /prefix/
 *
 * Exit codes: 0 clean, 1 findings or a blind-gate assertion tripped.
 */

import { readFileSync, readdirSync, statSync, existsSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join, resolve, relative, dirname, sep } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

// ---------------------------------------------------------------------------
// Blind-gate floors.
//
// Measured on a clean build of 92925e5: 219 HTML files, 111,490 href/src
// attributes of which 107,738 are absolute and same-origin, resolving to 474
// distinct targets. The floors sit well below those so
// ordinary growth or pruning does not trip them, and far above zero so a broken
// walk, a decayed extractor or a half-written dist cannot pass. If a
// legitimate change takes the site below a floor, RAISE THE PAGE COUNT OR LOWER
// THE FLOOR DELIBERATELY, in a commit that says which — never delete the
// assertion.
// ---------------------------------------------------------------------------
const FLOORS = {
  pages: 180,      // 219 today
  refs: 90000,     // 107,738 today
  distinct: 400,   // 474 today
}

// Pages that legitimately carry no absolute reference at all. These six are
// the standalone terminal reels shipped verbatim from docs/.vuepress/public/:
// self-contained HTML with no site chrome, no navbar and no asset of their own.
// Every OTHER page must contribute at least one absolute reference, because a
// VuePress-rendered page always carries at least its own <script src>. A new
// entry here needs a reason, not just a path.
const ZERO_REF_ALLOWLIST = [/^reels\/[^/]+\.html$/]

// ---------------------------------------------------------------------------
// What is EXCLUDED from the "must exist in dist" check, and why.
//
//   - anything with a URI scheme (https:, mailto:, data:, javascript:) — off
//     this artifact entirely. External reachability is link-check.yml's weekly
//     `external` job.
//   - protocol-relative (//host/…) — also a different origin.
//   - fragment-only (#section) — same page; this gate checks FILE presence, not
//     anchor targets. Anchors are an unguarded class: see KNOWN GAPS.
//   - relative (./x, ../x, x.html) — resolved against the containing page.
//     Counted and resolved, but WARN by default rather than fail; see KNOWN
//     GAPS for the one live breakage that blocks flipping it to error.
//   - empty href.
//
// Nothing else is excluded. There is no ignore-list of specific paths on
// purpose: an ignore-list is how a gate ends up inspecting nothing.
//
// KNOWN GAPS, stated plainly so nobody mistakes this for total coverage:
//   (a) fragment/anchor targets are not verified (#no-such-heading passes);
//   (b) relative refs default to warn. There is one real live 404 today,
//       confirmed against the published site on 2026-09-15:
//         curl -s -o /dev/null -w '%{http_code}\n' \
//           https://agenticstiger.github.io/forge_docs/.vuepress/cli-version.json
//         -> 404   (the page carrying the link, RELEASE_NOTES_0.7.11.html, -> 200)
//       docs/RELEASE_NOTES_0.7.11.md links ./.vuepress/cli-version.json, and
//       .vuepress/ is not copied into dist. lychee-source resolves it against a
//       mirror where docs/.vuepress/ IS present, so it passes there;
//       links-check ignores it because the target is not .md. Fix it the way
//       docs/contributing.md already does (link the file on github.com), then
//       switch the workflow step to --relative=error and delete this paragraph.
//       RELEASE_NOTES files are frozen, so this gate does not fail on it —
//       a red gate nobody is allowed to fix is a gate that gets disabled.
//   (c) CSS url(...) references are not read.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Reference extraction: a tag-aware scan, not a bare regex over the file.
//
// A bare /href="([^"]*)"/ over the raw bytes also matches text that merely
// LOOKS like an attribute inside a <script> body or a highlighted code sample.
// This walks tags, skips comments and skips the bodies of raw-text elements, so
// only real attribute values are collected. Verified against the naive count on
// a clean build: identical, 107,734 — the extra rigour costs nothing today and
// stops a future code sample from producing a phantom finding.
// ---------------------------------------------------------------------------
const RAW_TEXT_ELEMENTS = new Set(['script', 'style', 'textarea', 'title'])
const ATTR_RE = /\b(href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>`=]+))/gi

/** Index of the '>' closing the tag that starts at `start`, skipping quoted values. */
function tagEnd(html, start) {
  let quote = null
  for (let i = start + 1; i < html.length; i++) {
    const c = html[i]
    if (quote) {
      if (c === quote) quote = null
    } else if (c === '"' || c === "'") {
      quote = c
    } else if (c === '>') {
      return i
    }
  }
  return html.length
}

function extractRefs(html) {
  const refs = []
  let i = 0
  while (i < html.length) {
    const lt = html.indexOf('<', i)
    if (lt === -1) break
    if (html.startsWith('<!--', lt)) {
      const end = html.indexOf('-->', lt + 4)
      i = end === -1 ? html.length : end + 3
      continue
    }
    if (html.startsWith('<!', lt) || html.startsWith('</', lt) || html.startsWith('<?', lt)) {
      i = tagEnd(html, lt) + 1
      continue
    }
    const nameMatch = /^<([a-zA-Z][a-zA-Z0-9:-]*)/.exec(html.slice(lt, lt + 64))
    if (!nameMatch) {
      i = lt + 1
      continue
    }
    const tag = nameMatch[1].toLowerCase()
    const end = tagEnd(html, lt)
    const openTag = html.slice(lt, end)
    const selfClosing = openTag.endsWith('/')
    for (const m of openTag.matchAll(ATTR_RE)) {
      refs.push({ attr: m[1].toLowerCase(), tag, value: m[2] ?? m[3] ?? m[4] ?? '' })
    }
    i = end + 1
    if (!selfClosing && RAW_TEXT_ELEMENTS.has(tag)) {
      const close = new RegExp(`</${tag}[\\s>]`, 'i')
      close.lastIndex = 0
      const rest = html.slice(i)
      const hit = close.exec(rest)
      if (hit) i += hit.index
    }
  }
  return refs
}

const ENTITIES = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&apos;': "'" }

function decodeRef(raw) {
  const unescaped = raw.replace(/&(?:amp|lt|gt|quot|#39|apos);/g, (m) => ENTITIES[m])
  const pathname = unescaped.split(/[?#]/)[0]
  try {
    return { pathname: decodeURIComponent(pathname), ok: true }
  } catch {
    // A malformed percent-escape is itself a broken reference. Do not swallow.
    return { pathname, ok: false }
  }
}

function walkHtml(dir) {
  const out = []
  const visit = (d) => {
    for (const entry of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, entry.name)
      if (entry.isDirectory()) visit(p)
      else if (entry.isFile() && entry.name.toLowerCase().endsWith('.html')) out.push(p)
    }
  }
  visit(dir)
  return out.sort()
}

function isFile(p) {
  try {
    return statSync(p).isFile()
  } catch {
    return false
  }
}

/**
 * Resolve a site-root-relative path inside dist, returning WHICH rule resolved
 * it. The three rules are real, observed behaviours of the two things that
 * serve this artifact, not conveniences:
 *
 *   exact    the file is there.
 *   index    `/dir/` and `/dir` are served by dist/dir/index.html.
 *   pretty   `/cli/init` is served by dist/cli/init.html. 95 references in the
 *            built site (43 distinct) rely on this, so it was verified rather
 *            than assumed, on both paths that serve this artifact:
 *              - the live host, 2026-09-15 (.nojekyll is set by
 *                deploy-docs.yml, and extensionless resolution is the Pages
 *                static layer, not Jekyll):
 *                  curl -s -o /dev/null -w '%{http_code}\n' \
 *                    https://agenticstiger.github.io/forge_docs/cli/init
 *                -> 200, while .../forge_docs/definitely-not-a-page -> 404, so
 *                the host is not blanket-200ing unknown paths;
 *              - VuePress's own client router on a soft navigation:
 *                @vuepress/shared's inferRoutePath() appends '.html' to any
 *                path lacking an extension
 *                (node_modules/@vuepress/shared/dist/index.js).
 *
 * If that ever stops holding, this rule turns from a fact about the serving
 * layer into a leniency that hides live 404s — which is why the buckets are
 * counted and printed separately, so a shift toward the lenient rule is visible
 * instead of silent.
 */
function resolveInDist(distRoot, relPath) {
  const cleaned = relPath.replace(/^\/+/, '')
  const target = resolve(distRoot, cleaned)
  // Path traversal: /forge_docs/../secret escapes the artifact. Not resolvable.
  if (target !== distRoot && !target.startsWith(distRoot + sep)) return null
  if (isFile(target)) return 'exact'
  if (isFile(join(target, 'index.html'))) return 'index'
  if (!/\.[a-zA-Z0-9]+$/.test(cleaned) && isFile(`${target}.html`)) return 'pretty'
  return null
}

// ---------------------------------------------------------------------------
// The scan.
// ---------------------------------------------------------------------------
function scan({ distRoot, base, relativeMode }) {
  const pages = walkHtml(distRoot)
  const census = {
    pages: pages.length,
    refs: 0,
    absolute: 0,
    byRule: { exact: 0, index: 0, pretty: 0 },
    excluded: { scheme: 0, protocolRelative: 0, fragment: 0, relative: 0, empty: 0 },
    zeroRefPages: [],
    targetHits: new Map(),
  }
  const findings = []       // fatal
  const relativeFindings = []

  for (const file of pages) {
    const pageRel = relative(distRoot, file)
    const html = readFileSync(file, 'utf8')
    let absoluteOnPage = 0

    for (const ref of extractRefs(html)) {
      census.refs++
      const raw = ref.value.trim()

      if (raw === '') { census.excluded.empty++; continue }
      if (raw.startsWith('//')) { census.excluded.protocolRelative++; continue }
      if (raw.startsWith('#')) { census.excluded.fragment++; continue }

      if (!raw.startsWith('/')) {
        if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(raw)) { census.excluded.scheme++; continue }
        census.excluded.relative++
        // Resolved against the directory of the containing page.
        const { pathname, ok } = decodeRef(raw)
        if (pathname === '') continue
        const fromDir = join(distRoot, dirname(pageRel))
        const abs = resolve(fromDir, pathname)
        const asSiteRel = relative(distRoot, abs)
        if (!ok || asSiteRel.startsWith('..') || !resolveInDist(distRoot, asSiteRel)) {
          relativeFindings.push({ page: pageRel, ref: raw, attr: ref.attr, tag: ref.tag })
        }
        continue
      }

      // Absolute, same-origin. This is the class this gate owns.
      census.absolute++
      absoluteOnPage++
      const { pathname, ok } = decodeRef(raw)

      if (!ok) {
        findings.push({ kind: 'undecodable', page: pageRel, ref: raw, attr: ref.attr, tag: ref.tag })
        continue
      }
      if (!pathname.startsWith(base)) {
        findings.push({ kind: 'missing-base', page: pageRel, ref: raw, attr: ref.attr, tag: ref.tag })
        continue
      }
      const siteRel = pathname.slice(base.length)
      const rule = resolveInDist(distRoot, siteRel)
      if (!rule) {
        findings.push({ kind: 'missing-file', page: pageRel, ref: raw, attr: ref.attr, tag: ref.tag })
        continue
      }
      census.byRule[rule]++
      census.targetHits.set(pathname, (census.targetHits.get(pathname) ?? 0) + 1)
    }

    if (absoluteOnPage === 0) census.zeroRefPages.push(pageRel)
  }

  census.distinct = census.targetHits.size
  return { census, findings, relativeFindings, relativeMode }
}

// ---------------------------------------------------------------------------
// Canaries. A synthetic dist with a known-good link, a known-missing link and
// a link missing the base prefix. Run in-process before every real scan.
// ---------------------------------------------------------------------------
function runCanaries() {
  const dir = mkdtempSync(join(tmpdir(), 'dist-links-canary-'))
  try {
    const base = '/canary_base/'
    mkdirSync(join(dir, 'guide'), { recursive: true })
    writeFileSync(join(dir, 'guide', 'index.html'), '<html><body><a href="/canary_base/real.html">dir page</a></body></html>')
    // A real asset, so the fixture covers a non-.html target as well as a
    // non-href ATTRIBUTE. Without a `src` in here the canaries could not tell
    // that the extractor had stopped reading src at all: dropping `src` from
    // ATTR_RE moves the artifact counts by 219 of 107,738 references, which
    // clears every floor, and the gate then prints "Clean" while no asset
    // reference in dist is checked. Verified: that mutant passed --self-test.
    writeFileSync(join(dir, 'pic.png'), '')
    writeFileSync(join(dir, 'real.html'), [
      '<html><body>',
      '<a href="/canary_base/real.html">must resolve — exact</a>',
      '<img src="/canary_base/pic.png" alt="must resolve — exact, via src">',
      '<script src="/canary_base/no-such-script.js"></script>',
      '<a href="/canary_base/guide/">must resolve — index</a>',
      '<a href="/canary_base/real">must resolve — pretty</a>',
      '<a href="/canary_base/no-such-page.html">must NOT resolve — missing file</a>',
      '<a href="/real.html">must NOT resolve — missing base prefix</a>',
      '<pre><code>&lt;a href="/canary_base/not-a-real-link.html"&gt;in a code sample&lt;/a&gt;</code></pre>',
      '<script>var s = "href=\\"/canary_base/also-not-a-link.html\\"";</script>',
      '</body></html>',
    ].join('\n'))

    const { census, findings } = scan({ distRoot: resolve(dir), base, relativeMode: 'warn' })
    const kinds = findings.map((f) => f.kind).sort()
    const problems = []

    if (census.pages !== 2) problems.push(`walked ${census.pages} canary pages, expected 2`)
    if (census.byRule.exact !== 3) problems.push(`exact-rule resolutions ${census.byRule.exact}, expected 3`)
    if (census.byRule.index !== 1) problems.push(`index-rule resolutions ${census.byRule.index}, expected 1`)
    if (census.byRule.pretty !== 1) problems.push(`pretty-rule resolutions ${census.byRule.pretty}, expected 1`)
    if (findings.length !== 3) problems.push(`reported ${findings.length} findings, expected exactly 3`)
    if (kinds.join(',') !== 'missing-base,missing-file,missing-file') {
      problems.push(`finding kinds were [${kinds.join(', ')}], expected [missing-base, missing-file, missing-file]`)
    }
    // The code sample and the script-body string must NOT have been collected.
    // If either shows up, the extractor is reading page text as markup and
    // every "finding" it reports is suspect.
    if (findings.some((f) => /not-a-real-link|also-not-a-link/.test(f.ref))) {
      problems.push('extractor picked up an attribute-shaped string out of a code sample or a <script> body')
    }
    // Both directions of the src class, named explicitly rather than left to the
    // counts above: a src that resolves must be counted, and a src that does not
    // must be reported. The coverage map in docs-pr-check.yml promises this gate
    // sees <script src> and <img src>; this is what keeps that promise true.
    if (census.byRule.exact !== 3 || !findings.some((f) => f.ref === '/canary_base/no-such-script.js')) {
      problems.push(
        'the src attribute class was not inspected — a <img src> that resolves ' +
        'was not counted, or a <script src> pointing at a missing file was not ' +
        'reported. Every asset reference in the artifact is unchecked, and the ' +
        'floors cannot see it: src is ~0.2% of references here.')
    }

    return { problems, census, findings }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

// ---------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------
const isGitHub = Boolean(process.env.GITHUB_ACTIONS)
const annotate = (level, msg) => console.log(isGitHub ? `::${level}::${msg}` : `[${level}] ${msg}`)

function num(n) {
  return n.toLocaleString('en-US')
}

function printCensus(census, base, distRoot) {
  console.log('')
  console.log('What this gate inspected')
  console.log('------------------------')
  console.log(`  artifact              ${relative(REPO_ROOT, distRoot) || distRoot}`)
  console.log(`  required base prefix  ${base}`)
  console.log(`  HTML pages walked     ${num(census.pages)}   (floor ${num(FLOORS.pages)})`)
  console.log(`  href/src attributes   ${num(census.refs)}`)
  console.log(`  absolute, same-origin ${num(census.absolute)}   (floor ${num(FLOORS.refs)})  <- the class this gate owns`)
  console.log(`  distinct targets      ${num(census.distinct)}   (floor ${num(FLOORS.distinct)})`)
  console.log('  resolved by rule      ' +
    `exact ${num(census.byRule.exact)}, ` +
    `dir index.html ${num(census.byRule.index)}, ` +
    `extensionless +.html ${num(census.byRule.pretty)}`)
  console.log('  excluded              ' +
    `scheme (https:/mailto:/data:) ${num(census.excluded.scheme)}, ` +
    `fragment-only ${num(census.excluded.fragment)}, ` +
    `relative ${num(census.excluded.relative)}, ` +
    `protocol-relative ${num(census.excluded.protocolRelative)}, ` +
    `empty ${num(census.excluded.empty)}`)

  const top = [...census.targetHits.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5)
  console.log('  busiest targets       ' + (top.length
    ? top.map(([p, n]) => `${p} (${num(n)})`).join(', ')
    : 'none'))
  if (census.zeroRefPages.length) {
    console.log(`  pages with no absolute reference (allowlisted): ${census.zeroRefPages.join(', ')}`)
  }
  console.log('')
}

function main(argv) {
  const arg = (name, fallback) => {
    const hit = argv.find((a) => a === `--${name}` || a.startsWith(`--${name}=`))
    if (!hit) return fallback
    if (hit.includes('=')) return hit.slice(hit.indexOf('=') + 1)
    const i = argv.indexOf(hit)
    return argv[i + 1] ?? fallback
  }
  const selfTestOnly = argv.includes('--self-test') || argv.includes('--self-test-only')
  const relativeMode = arg('relative', 'warn')
  if (!['warn', 'error'].includes(relativeMode)) {
    annotate('error', `--relative must be warn or error, got "${relativeMode}"`)
    return 1
  }

  // The base prefix is deliberately NOT read from docs/.vuepress/config.ts.
  // config.ts is the thing under test: a typo'd base there must fail this gate,
  // not teach it a new expectation. package.json's "homepage" is an independent
  // declaration of where this site is published, so the two must agree.
  const declaredHome = JSON.parse(readFileSync(join(REPO_ROOT, 'package.json'), 'utf8')).homepage
  let base = arg('base', null)
  if (!base) {
    if (!declaredHome) {
      annotate('error', 'package.json has no "homepage", so the deployment base prefix cannot be established. Refusing to guess.')
      return 1
    }
    base = new URL(declaredHome).pathname
  }
  if (!base.startsWith('/')) base = `/${base}`
  if (!base.endsWith('/')) base = `${base}/`
  if (base === '/') {
    annotate('error', `Resolved base prefix "/" — every absolute link would pass the prefix rule trivially. Refusing to run a check that cannot fail. Fix package.json "homepage" (got ${declaredHome}) or pass --base.`)
    return 1
  }

  // --- canaries, always, first -------------------------------------------
  console.log('Canaries (a link that must resolve, a link that must not, a link missing the base prefix)')
  const canary = runCanaries()
  if (canary.problems.length) {
    for (const p of canary.problems) annotate('error', `Canary failed: ${p}`)
    annotate('error', 'The dist link checker cannot be trusted this run: it failed its own must-resolve / must-not-resolve fixture. Refusing to report on the real artifact.')
    return 1
  }
  // Derived from the canary run, never hardcoded. A fixed sentence is how a
  // summary drifts away from what was actually measured: this line read
  // "resolved 4 links … caught 1 missing file" for a fixture that resolved 5 and
  // caught 2, so it was describing an earlier version of itself.
  {
    const c = canary.census
    const kinds = canary.findings.reduce((a, f) => ({ ...a, [f.kind]: (a[f.kind] || 0) + 1 }), {})
    const resolved = c.byRule.exact + c.byRule.index + c.byRule.pretty
    const rules = ['exact', 'index', 'pretty'].map((r) => `${c.byRule[r] || 0} ${r}`).join(', ')
    const caught = Object.keys(kinds).sort().map((k) => `${kinds[k]} ${k}`).join(', ')
    console.log(`  ok — resolved ${resolved} references in the fixture (${rules}), caught ${caught},`)
    console.log('       and did not mistake a code sample or a <script> body string for markup.')
  }
  if (selfTestOnly) {
    console.log('')
    console.log('--self-test only: not scanning the artifact.')
    return 0
  }

  // --- the real scan ------------------------------------------------------
  const distRoot = resolve(REPO_ROOT, arg('dist', 'docs/.vuepress/dist'))
  if (!existsSync(distRoot)) {
    annotate('error', `No artifact at ${distRoot}. This gate must run AFTER \`npm run docs:build\`; it has nothing to measure and will not pass by default.`)
    return 1
  }

  const { census, findings, relativeFindings } = scan({ distRoot, base, relativeMode })
  printCensus(census, base, distRoot)

  let failed = false

  // --- blind-gate assertions --------------------------------------------
  // These come BEFORE the findings verdict on purpose. "No findings" from a
  // scan that inspected almost nothing is the failure mode this repo keeps
  // rediscovering, and it must never read as a pass.
  if (census.pages < FLOORS.pages) {
    annotate('error', `Walked only ${census.pages} HTML pages (floor ${FLOORS.pages}). A clean build renders 213 pages plus 6 static ones. Either the artifact is incomplete or the walk is broken — this run proves nothing about links.`)
    failed = true
  }
  if (census.absolute < FLOORS.refs) {
    annotate('error', `Examined only ${num(census.absolute)} absolute references (floor ${num(FLOORS.refs)}). A clean build carries ~107,700. The extractor is not seeing the page; a clean result here would be meaningless.`)
    failed = true
  }
  if (census.distinct < FLOORS.distinct) {
    annotate('error', `Resolved only ${census.distinct} DISTINCT targets (floor ${FLOORS.distinct}). A clean build has ~474. A high reference count with few distinct targets means the extractor is only seeing repeated site chrome (navbar/sidebar) and is blind to page bodies.`)
    failed = true
  }
  const unexplainedZeroRef = census.zeroRefPages.filter((p) => !ZERO_REF_ALLOWLIST.some((re) => re.test(p)))
  if (unexplainedZeroRef.length) {
    annotate('error', `${unexplainedZeroRef.length} page(s) yielded ZERO absolute references, which a VuePress-rendered page cannot do (it always carries its own <script src>): ${unexplainedZeroRef.slice(0, 10).join(', ')}${unexplainedZeroRef.length > 10 ? ', …' : ''}`)
    annotate('error', 'Either extraction failed on those pages or they are new self-contained pages. If the latter, add them to ZERO_REF_ALLOWLIST in scripts/check-dist-links.mjs with a reason — do not widen it blindly.')
    failed = true
  }
  if (failed) {
    annotate('error', 'Refusing to report on link health: the checker did not inspect enough of the artifact for a result to mean anything.')
    return 1
  }

  // --- findings ----------------------------------------------------------
  if (findings.length) {
    const byKind = { 'missing-base': [], 'missing-file': [], undecodable: [] }
    for (const f of findings) byKind[f.kind].push(f)

    console.log('Broken absolute references in the built artifact')
    console.log('-----------------------------------------------')
    for (const [kind, list] of Object.entries(byKind)) {
      if (!list.length) continue
      console.log(`\n  ${kind} (${num(list.length)} occurrence(s), ${new Set(list.map((f) => f.ref)).size} distinct):`)
      const seen = new Map()
      for (const f of list) {
        if (!seen.has(f.ref)) seen.set(f.ref, [])
        seen.get(f.ref).push(f.page)
      }
      for (const [ref, pagesHit] of [...seen.entries()].sort((a, b) => b[1].length - a[1].length)) {
        const uniquePages = [...new Set(pagesHit)]
        console.log(`    ${ref}`)
        console.log(`      ${num(pagesHit.length)} occurrence(s) across ${num(uniquePages.length)} page(s), e.g. ${uniquePages.slice(0, 3).join(', ')}`)
      }
    }
    console.log('')
    if (byKind['missing-base'].length) {
      annotate('error', `${num(byKind['missing-base'].length)} absolute reference(s) in the built HTML do not start with ${base}. They will 404 on the live site. Body markdown links are NOT auto-prefixed: write /forge_docs/x, or use a relative path.`)
    }
    if (byKind['missing-file'].length) {
      annotate('error', `${num(byKind['missing-file'].length)} absolute reference(s) point at a file that is not in the artifact. Nothing in dist serves them, so they are live 404s. Check for a typo in docs/.vuepress/config.ts (navbar/sidebar), in docs/README.md frontmatter (hero actions) or in a raw HTML anchor — none of those are read by any markdown-based gate.`)
    }
    if (byKind.undecodable.length) {
      annotate('error', `${num(byKind.undecodable.length)} reference(s) carry a malformed percent-escape and cannot be resolved by a browser either.`)
    }
    return 1
  }

  // --- relative refs: secondary, and honest about it ---------------------
  if (relativeFindings.length) {
    console.log('Broken RELATIVE references (secondary check)')
    console.log('-------------------------------------------')
    for (const f of relativeFindings) console.log(`  ${f.page}  ->  ${f.ref}`)
    console.log('')
    const msg = `${relativeFindings.length} relative reference(s) in the built artifact resolve to nothing in dist.`
    if (relativeMode === 'error') {
      annotate('error', msg)
      return 1
    }
    annotate('warning', `${msg} NOT failing the build, because --relative defaults to warn: one of these lives in a RELEASE_NOTES file that is frozen. Fix them and switch the step to --relative=error.`)
  }

  console.log(`Clean: all ${num(census.absolute)} absolute references across ${num(census.pages)} built pages carry the ${base} base and name a file that exists in the artifact.`)
  return 0
}

process.exit(main(process.argv.slice(2)))
