import { defineUserConfig } from 'vuepress'
import { defaultTheme } from '@vuepress/theme-default'
import { viteBundler } from '@vuepress/bundler-vite'
import { slimsearchPlugin } from '@vuepress/plugin-slimsearch'
import { markdownChartPlugin } from '@vuepress/plugin-markdown-chart'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

// Deployment origin and base, kept as separate values on purpose.
//
// `hostname` must be the BARE ORIGIN, with no base path in it. Both
// @vuepress/plugin-seo and @vuepress/plugin-sitemap build absolute URLs as
// `hostname + base + path` (seo's getUrl; sitemap's robots.txt line is
// `Sitemap: ${hostname}${base}${sitemapFilename}`), so a hostname that already
// carries `/forge_docs/` doubles the base. That is what produced the 404ing
// `.../forge_docs/forge_docs/sitemap.xml` in robots.txt.
//
// The sitemap's <loc> entries were correct even with the doubled hostname,
// because the `sitemap` package resolves the root-relative `/forge_docs/x.html`
// against the origin and discards the hostname's own path. They stay correct
// with the bare origin, which is the same resolution with nothing to discard.
const HOSTNAME = 'https://agenticstiger.github.io'
const BASE = '/forge_docs/'

// Origin + base with no trailing slash. plugin-seo builds each canonical as
// `removeEndingSlash(canonical) + page.path`, and page.path excludes the base.
const CANONICAL_ROOT = `${HOSTNAME}${BASE.replace(/\/$/, '')}`

export default defineUserConfig({
  lang: 'en-US',
  title: 'Fluid Forge',
  description: 'Declarative data products for local and multi-cloud delivery with a contract-first CLI.',

  base: BASE,

  // Loads client.ts so <CliCast> is registered globally for markdown pages
  // and the branded NotFound layout overrides the theme's default 404.
  clientConfigFile: resolve(__dirname, './client.ts'),

  bundler: viteBundler(),

  // Both of these default to TRUE in VuePress. They were set to false in the
  // initial commit with no rationale, and the cost is paid on every single
  // navigation: with prefetch off the built HTML carries zero
  // `<link rel="prefetch">`, so clicking through to a page blocks on fetching
  // that page's chunk. Measured on the built site: 0 prefetch links across 213
  // pages, against 310 chunks.
  //
  // Turning prefetch fully back on is not right either. Of 19 MB of chunks,
  // 12.4 MB is Monaco - the `ts` / `css` / `html` / `json` workers plus
  // `editor.api` and `vs` - and that is reachable only from /playground/.
  // Prefetching it for every visitor would trade one problem for a worse one.
  //
  // So: prefetch the route chunks (299 of the 310 are under 100 KB), and skip
  // the editor. The remaining page chunks are what make navigation feel
  // instant.
  shouldPrefetch: (file, type) => {
    if (type !== 'script') return false
    return !/(?:ts|css|html|json)\.worker-|editor\.api-|(?:^|\/)vs-/.test(file)
  },

  // Preload only covers files the CURRENT page needs, so the default is simply
  // correct - including on /playground/, where Monaco genuinely is needed.
  shouldPreload: true,

  head: [
    // Favicon. This was `logo.png`, which is 69,734 bytes at 256x139 — a
    // full wordmark lockup shipped to every visitor on all 213 pages to
    // fill a 16px tab slot, and referenced from nowhere else in the site.
    //
    // favicon-32.png is that same file scaled down, nothing else:
    //   sips -Z 32 docs/.vuepress/public/logo.png \
    //        --out docs/.vuepress/public/favicon-32.png
    //
    // 2,076 bytes, 32x17, alpha preserved. Deliberately NOT padded to a
    // square: sips can only pad with an opaque colour, and a white pad
    // would put a white box behind the mark on dark tab bars, where the
    // browser currently letterboxes it transparently. Aspect and alpha are
    // unchanged, so it renders identically to what shipped before — the
    // browser was already downscaling the 256px original to the same size.
    //
    // logo.png stays in public/ as the full-size brand asset. It is now
    // unreferenced by the site, so it costs dist size but no page weight.
    ['link', { rel: 'icon', href: '/forge_docs/favicon-32.png' }],
    ['meta', { name: 'theme-color', content: '#050813' }], // brand deep-navy
    ['meta', { name: 'apple-mobile-web-app-capable', content: 'yes' }],
    ['meta', { name: 'apple-mobile-web-app-status-bar-style', content: 'black' }],

    // Open Graph — static social card only.
    //
    // og:title, og:description, og:url, og:type and og:site_name are NOT set
    // here: @vuepress/plugin-seo (registered by the theme, see `hostname`
    // below) emits all five per page. A site-wide copy of any of them is not
    // just redundant, it is wrong on 212 of 213 pages — the old hard-coded
    // og:url pointed every page at the homepage — and og:type genuinely varies
    // (the plugin emits `article` for content pages, `website` for the home
    // page), so a fixed `website` would contradict the plugin's own tag.
    //
    // og:image stays static and site-wide: it is the branded 1200x630 card,
    // and the plugin only emits an og:image of its own when a page declares a
    // frontmatter cover or embeds an image, which no page here does.
    ['meta', { property: 'og:image', content: `${CANONICAL_ROOT}/og-card.png` }],
    ['meta', { property: 'og:image:width', content: '1200' }],
    ['meta', { property: 'og:image:height', content: '630' }],

    // Twitter / X. Kept hand-written: plugin-seo emits twitter:* tags only
    // when a page declares a frontmatter cover, so these do not collide.
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: 'Fluid Forge — Declarative Data Products' }],
    ['meta', { name: 'twitter:description', content: 'Write YAML, deploy anywhere. One contract, every cloud.' }],
    ['meta', { name: 'twitter:image', content: `${CANONICAL_ROOT}/og-card.png` }],

    ['meta', { name: 'keywords', content: 'fluid forge, data products, declarative data engineering, duckdb, bigquery, snowflake, aws, cli' }],
  ],

  theme: defaultTheme({
    // The theme gates BOTH its bundled @vuepress/plugin-seo and its bundled
    // @vuepress/plugin-sitemap on exactly this option
    // (`hostname && (themePlugins.seo ?? true) ? seoPlugin({ hostname }) : []`
    // in @vuepress/theme-default 2.0.0-rc.132 dist/node/index.js). Without it
    // neither plugin was ever registered, which is why every page carried the
    // same hand-written og:url and none carried a canonical.
    hostname: HOSTNAME,

    themePlugins: {
      // The theme already registers @vuepress/plugin-links-check; by default it
      // only warns. `build: 'error'` makes the build itself throw on a dead
      // internal link, so a broken link fails CI natively instead of relying on
      // a workflow that greps the build log for a warning string.
      linksCheck: { build: 'error' },

      // plugin-seo emits rel="canonical" only when `canonical` is set; passing
      // `hostname` alone gives per-page og:* but no canonical at all.
      seo: { canonical: CANONICAL_ROOT },
    },

    // Dark is the brand default (matches agenticstransformation.com).
    // The navbar toggle still switches to the refined light theme.
    // The theme hides the .vp-site-name span whenever logoAlt resolves equal to
    // the site title (VPNavbarBrand: navBarLogoAltMatchesTitle), which is what
    // `logoAlt ?? title` gives when no logo is configured - leaving the brand
    // anchor with no unhidden child and an EMPTY accessible name on every page.
    // An explicit logoAlt breaks that equality so the wordmark stays readable.
    logoAlt: 'Fluid Forge home',
    colorMode: 'dark',
    colorModeSwitch: true,

    // No `logo`: the current logo.png has a baked-in white background
    // that reads as a bright box on the dark theme. The navbar shows the
    // "Fluid Forge" wordmark instead (and still links home, so a "Home"
    // navbar item is redundant). Add a transparent `logo` / `logoDark`
    // asset later to bring the mark back.
    //
    // `logoAlt: ''` is what gives the brand/home link an accessible name,
    // and it is load-bearing despite there being no logo to describe.
    // VPNavbarBrand computes
    //   logoAlt        = themeLocale.logoAlt ?? siteLocale.title
    //   aria-hidden    = logoAlt.toUpperCase().trim() === title.toUpperCase().trim()
    // on the <span class="vp-site-name"> that holds the wordmark. The
    // intent is to stop a screen reader saying "Fluid Forge" twice when an
    // <img alt="Fluid Forge"> already sits next to the text. With no logo
    // there is no img, so the guard compared the title against itself,
    // resolved true, and hid the anchor's ONLY child: the link came out as
    // `<a href="/forge_docs/"><span aria-hidden="true">Fluid Forge</span></a>`,
    // an interactive element with an empty accessible name on all 213 pages
    // (WCAG 2.1 SC 2.4.4 Link Purpose, SC 4.1.2 Name/Role/Value).
    //
    // '' is not ?? -coalesced away (?? only falls back on null/undefined), so
    // it survives as the alt, compares unequal to the title, and the wordmark
    // is exposed. It is also the correct alt for the logo if one is ever
    // added back: a mark sitting beside its own wordmark is decorative.
    logoAlt: '',
    navbar: [
      { text: 'Why Forge', link: '/why' },
      { text: 'Concepts', link: '/concepts/' },
      { text: 'Get Started', link: '/getting-started/' },
      {
        text: 'Walkthroughs',
        children: [
          { text: 'Consume a Data Product', link: '/data-products/consume' },
          { text: 'See it run', link: '/see-it-run' },
          { text: 'Demos', link: '/demos/' },
          { text: 'Local (DuckDB)', link: '/walkthrough/local' },
          { text: 'Source-Aligned (Postgres → DuckDB)', link: '/walkthrough/source-aligned-postgres-duckdb' },
          { text: 'AI Forge + Data Models', link: '/walkthrough/ai-forge-data-model' },
          { text: 'MCP Output Port — Serve to AI Agents', link: '/walkthrough/mcp-output-port' },
          { text: 'GCP (BigQuery)', link: '/walkthrough/gcp' },
          { text: 'Snowflake Team Collaboration', link: '/walkthrough/snowflake' },
          { text: 'Declarative Airflow', link: '/walkthrough/airflow-declarative' },
          { text: 'Orchestration Export', link: '/walkthrough/export-orchestration' },
          { text: 'Jenkins CI/CD', link: '/walkthrough/jenkins-cicd' },
          { text: 'Universal Pipeline', link: '/walkthrough/universal-pipeline' },
          { text: '11-Stage Production Pipeline', link: '/walkthrough/11-stage-pipeline' },
          { text: 'Catalog Forge End-to-End', link: '/walkthrough/catalog-forge-end-to-end' }
        ]
      },
      { text: 'CLI Reference', link: '/cli/' },
      {
        text: 'AI & Agents',
        children: [
          { text: 'Agent Policy (concept)', link: '/concepts/agent-policy' },
          { text: 'MCP Output Port — Serve to Agents', link: '/walkthrough/mcp-output-port' },
          { text: 'MCP deep-dive', link: '/advanced/mcp' },
          { text: 'AI-assisted authoring', link: '/advanced/custom-llm-agents' },
          { text: 'LLM providers & backends', link: '/advanced/llm-providers' }
        ]
      },
      {
        text: 'SDK & Plugins',
        children: [
          { text: 'Overview', link: '/sdk-and-plugins/' },
          { text: 'Quickstart', link: '/sdk-and-plugins/quickstart' },
          { text: 'Examples', link: '/sdk-and-plugins/examples/' },
          { text: 'Your own CI', link: '/sdk-and-plugins/journeys/your-own-ci' },
          { text: 'Your own scaffolding', link: '/sdk-and-plugins/journeys/your-own-scaffolding' },
          { text: 'Custom validator', link: '/sdk-and-plugins/journeys/custom-validator' },
          { text: 'Apply hook', link: '/sdk-and-plugins/journeys/apply-hook' },
          { text: 'Reference', link: '/sdk-and-plugins/reference/' }
        ]
      },
      {
        text: 'Providers',
        children: [
          { text: 'Overview', link: '/providers/' },
          { text: 'Architecture', link: '/providers/architecture' },
          { text: 'GCP (BigQuery)', link: '/providers/gcp' },
          { text: 'AWS (S3 + Athena)', link: '/providers/aws' },
          { text: 'Snowflake', link: '/providers/snowflake' },
          { text: 'Local (DuckDB)', link: '/providers/local' },
          { text: 'Custom Providers', link: '/providers/custom-providers' },
          { text: 'Roadmap', link: '/providers/roadmap' }
        ]
      }
    ],

    sidebar: {
      '/': [
        {
          text: 'Introduction',
          children: [
            { text: 'Home', link: '/' },
            '/why.md',
            '/getting-started/',
            '/getting-started/snowflake.md',
            '/see-it-run.md',
            '/forge-data-model.md',
            '/vision.md',
            '/playground/',
            '/faq/'
          ]
        },
        {
          text: 'Concepts',
          children: [
            '/concepts/README.md',
            '/concepts/builds-exposes-bindings.md',
            '/concepts/contract.md',
            '/concepts/quality-sla-lineage.md',
            '/concepts/governance-policy.md',
            '/concepts/sovereignty.md',
            '/concepts/agent-policy.md',
            '/concepts/providers-vs-platforms.md',
            '/concepts/vs-alternatives.md'
          ]
        },
        {
          text: 'Data Products',
          children: [
            '/data-products/consume.md',
            '/data-products/product-type.md'
          ]
        },
        {
          text: 'Walkthroughs',
          children: [
            '/walkthrough/local.md',
            '/walkthrough/source-aligned-postgres-duckdb.md',
            '/walkthrough/ai-forge-data-model.md',
            '/walkthrough/mcp-output-port.md',
            '/walkthrough/gcp.md',
            '/walkthrough/snowflake.md',
            '/walkthrough/airflow-declarative.md',
            '/walkthrough/export-orchestration.md',
            '/walkthrough/jenkins-cicd.md',
            '/walkthrough/universal-pipeline.md',
            '/walkthrough/11-stage-pipeline.md',
            '/walkthrough/catalog-forge-end-to-end.md'
          ]
        },
        {
          text: 'CLI Reference',
          children: [
            '/cli/README.md',
            // Core workflow — the validate -> plan -> apply lifecycle; open by default.
            {
              text: 'Core workflow',
              children: [
                '/cli/init.md',
                '/cli/demo.md',
                '/cli/forge.md',
                '/cli/validate.md',
                '/cli/plan.md',
                '/cli/apply.md',
                '/cli/diff.md',
                '/cli/status.md'
              ]
            },
            {
              text: 'Build & ship',
              collapsible: true,
              children: [
                '/cli/bundle.md',
                '/cli/generate.md',
                '/cli/generate-artifacts.md',
                '/cli/validate-artifacts.md',
                '/cli/verify-signature.md',
                '/cli/generate-iac.md',
                '/cli/generate-airflow.md',
                '/cli/generate-pipeline.md',
                '/cli/generate-vector.md',
                '/cli/viz-graph.md',
                '/cli/publish.md',
                '/cli/ship.md',
                '/cli/rollback.md',
                '/cli/schedule-sync.md'
              ]
            },
            {
              text: 'AI & Agents',
              collapsible: true,
              children: [
                '/cli/ai.md',
                '/cli/agents.md',
                '/cli/mission.md',
                '/cli/mcp.md',
                '/cli/memory.md',
                '/cli/stats.md',
                '/cli/skills.md'
              ]
            },
            {
              text: 'Quality & governance',
              collapsible: true,
              children: [
                '/cli/test.md',
                '/cli/verify.md',
                '/cli/contract-tests.md',
                '/cli/contract-validation.md',
                '/cli/policy.md',
                '/cli/policy-check.md',
                '/cli/policy-compile.md',
                '/cli/policy-apply.md'
              ]
            },
            {
              text: 'Standards & interoperability',
              collapsible: true,
              children: [
                '/cli/odps.md',
                '/cli/odps-bitol.md',
                '/cli/odcs.md',
                '/cli/export.md',
                '/cli/export-odps.md',
                '/cli/exporters.md',
                '/cli/import.md',
                '/cli/market.md',
                '/cli/datamesh-manager.md'
              ]
            },
            {
              text: 'Project & workspace',
              collapsible: true,
              children: [
                '/cli/product-new.md',
                '/cli/product-add.md',
                '/cli/workspace.md',
                '/cli/contract.md',
                '/cli/split.md',
                '/cli/config.md',
                '/cli/providers.md',
                '/cli/plugins.md',
                '/cli/provider-init.md',
                '/cli/auth.md',
                '/cli/secrets.md',
                '/cli/ide.md',
                '/cli/scaffold-ci.md',
                '/cli/scaffold-composer.md',
                '/cli/scaffold-ide.md',
                '/cli/docs.md',
                '/cli/runs.md',
                '/cli/retention.md',
                '/cli/describe.md',
                '/cli/doctor.md',
                '/cli/roadmap.md',
                '/cli/version.md'
              ]
            },
            {
              text: 'Catalog adapters',
              collapsible: true,
              children: [
                '/cli/catalogs/README.md',
                '/cli/catalogs/overview.md',
                '/cli/catalogs/bigquery.md',
                '/cli/catalogs/snowflake.md',
                '/cli/catalogs/unity.md',
                '/cli/catalogs/dataplex.md',
                '/cli/catalogs/glue.md',
                '/cli/catalogs/datahub.md',
                '/cli/catalogs/datamesh-manager.md',
                '/cli/catalogs/openmetadata.md'
              ]
            },
            {
              text: 'CLI by task',
              collapsible: true,
              children: [
                '/cli/tasks/README.md',
                '/cli/tasks/add-quality-rules.md',
                '/cli/tasks/agent-governance.md',
                '/cli/tasks/debug-failed-run.md',
                '/cli/tasks/switch-clouds.md'
              ]
            }
          ]
        },
        {
          text: 'Recipes',
          children: [
            '/recipes/README.md',
            '/recipes/add-a-quality-rule.md',
            '/recipes/switch-clouds.md',
            '/recipes/tag-pii.md',
            '/recipes/consumes-contract-to-contract.md',
            '/recipes/per-environment-overlays.md'
          ]
        },
        {
          text: 'SDK & Plugins',
          children: [
            '/sdk-and-plugins/README.md',
            '/sdk-and-plugins/quickstart.md',
            {
              text: 'Examples',
              children: [
                '/sdk-and-plugins/examples/README.md',
                '/sdk-and-plugins/examples/hello-scaffold.md',
                '/sdk-and-plugins/examples/gitlab-ci-scaffold.md',
                '/sdk-and-plugins/examples/steward-validator.md',
                '/sdk-and-plugins/examples/apply-hook-prod-key-guard.md'
              ]
            },
            {
              text: 'Journeys',
              children: [
                '/sdk-and-plugins/journeys/README.md',
                {
                  text: 'Your own CI/CD',
                  children: [
                    '/sdk-and-plugins/journeys/your-own-ci.md',
                    '/sdk-and-plugins/journeys/your-own-ci-gitlab.md',
                    '/sdk-and-plugins/journeys/your-own-ci-github.md',
                    '/sdk-and-plugins/journeys/your-own-ci-jenkins.md',
                    '/sdk-and-plugins/journeys/your-own-ci-circleci.md'
                  ]
                },
                '/sdk-and-plugins/journeys/your-own-scaffolding.md',
                '/sdk-and-plugins/journeys/custom-validator.md',
                '/sdk-and-plugins/journeys/apply-hook.md'
              ]
            },
            {
              text: 'Reference',
              children: [
                '/sdk-and-plugins/reference/README.md',
                '/sdk-and-plugins/reference/roles.md',
                '/sdk-and-plugins/reference/entry-points.md',
                '/sdk-and-plugins/reference/trust-model.md',
                '/sdk-and-plugins/reference/packaging.md',
                '/sdk-and-plugins/reference/companion-packages.md'
              ]
            }
          ]
        },
        {
          text: 'Providers',
          children: [
            '/providers/README.md',
            '/providers/architecture.md',
            '/providers/gcp.md',
            '/providers/aws.md',
            '/providers/snowflake.md',
            '/providers/local.md',
            '/providers/custom-providers.md',
            '/providers/roadmap.md'
          ]
        },
        {
          text: 'AI & Agents',
          collapsible: true,
          children: [
            '/advanced/mcp.md',
            '/advanced/custom-llm-agents.md',
            '/advanced/forge-copilot-discovery.md',
            '/advanced/forge-copilot-memory.md',
            '/advanced/forge-tools.md',
            '/advanced/guided-forge-ux.md',
            '/advanced/llm-providers.md',
            '/advanced/litellm-backend.md',
            '/advanced/capability-warnings.md',
            '/advanced/cost-tracking.md',
            '/advanced/chatgpt-forge-contract-gpt/',
            '/advanced/agentic-primitives.md'
          ]
        },
        {
          text: 'Operate & Deploy',
          collapsible: true,
          children: [
            '/advanced/operating-in-ci.md',
            '/advanced/production-troubleshooting.md',
            '/advanced/airflow.md',
            '/advanced/blueprints.md',
            '/advanced/source-aligned-acquisition.md'
          ]
        },
        {
          text: 'Govern & Secure',
          collapsible: true,
          children: [
            '/governance-compliance-roi.md',
            '/advanced/governance.md',
            '/advanced/network-safety.md',
            '/advanced/credential-resolver.md'
          ]
        },
        {
          text: 'Configuration & Reference',
          collapsible: true,
          children: [
            '/advanced/environment-variables.md',
            '/advanced/typed-errors.md',
            '/advanced/typed-cli-errors.md',
            '/advanced/api-stability.md'
          ]
        },
        {
          text: 'Architecture & Releases',
          collapsible: true,
          children: [
            '/advanced/v1.5-architecture.md',
            '/advanced/v1.5-release-notes.md'
          ]
        },
        {
          text: 'Project',
          children: [
            '/contributing.md',
            '/RELEASE_NOTES_0.15.0.md',
            '/RELEASE_NOTES_0.14.0.md',
            '/RELEASE_NOTES_0.13.0.md',
            '/RELEASE_NOTES_0.12.0.md',
            '/RELEASE_NOTES_0.11.0.md',
            '/RELEASE_NOTES_0.10.0.md',
            '/RELEASE_NOTES_0.9.0.md',
            '/RELEASE_NOTES_0.8.11.md',
            '/RELEASE_NOTES_0.8.10.md',
            '/RELEASE_NOTES_0.8.9.md',
            '/RELEASE_NOTES_0.8.8.md',
            '/RELEASE_NOTES_0.8.7.md',
            '/RELEASE_NOTES_0.8.6.md',
            '/RELEASE_NOTES_0.8.5.md',
            '/RELEASE_NOTES_0.8.4.md',
            '/RELEASE_NOTES_0.8.3.md',
            '/RELEASE_NOTES_0.8.0.md',
            '/RELEASE_NOTES_0.7.11.md',
            '/RELEASE_NOTES_0.7.9.md',
            '/RELEASE_NOTES_0.7.1.md'
          ]
        }
      ]
    },

    repo: 'Agenticstiger/forge-cli',
    docsRepo: 'Agenticstiger/forge_docs',
    docsDir: 'docs',
    docsBranch: 'main',
    editLink: true,
    editLinkText: 'Edit this page on GitHub',
    lastUpdated: true,
    contributors: true
  }),

  // Phase 2A foundation plugins.
  // - slimsearch: client-side search ("s" or "/" hotkey). DocSearch was the
  //   original target; client-side keeps us free of external indexing
  //   dependencies and works offline in dev.
  // - markdown-chart: renders ```mermaid blocks at build time so they
  //   show on the live site (without this plugin Mermaid only renders
  //   on github.com READMEs).
  //
  // copy-code is NOT listed here: @vuepress/theme-default registers it
  // already (themePlugins.copyCode defaults to true). Registering it a
  // second time made the build warn "has been used multiple times".
  //
  // sitemap is NOT listed here either, for the same reason: now that the theme
  // has `hostname` it registers @vuepress/plugin-sitemap itself, with the same
  // single `hostname` option this file used to pass. Keeping the manual
  // registration would have run the plugin twice and left two competing
  // onGenerated hooks writing robots.txt.
  plugins: [
    // slimsearch replaces @vuepress/plugin-search. The old plugin inlined the
    // whole index into the entry chunk as a virtual module, so every visitor
    // downloaded and parsed it on first paint whether or not they ever
    // searched. slimsearch bakes the index into `slimsearch.worker.js` at the
    // site root and fetches it only when the search modal opens, off the main
    // thread. It also indexes section text, not just titles and headings.
    //
    // `hotKeys` MUST be KeyOptions objects, not bare strings. Strings are
    // accepted by the runtime matcher but the SSR key-hint renderer reads
    // `hotKeys[0].key`, and a string there throws during prerender. VuePress
    // swallows that error per page: the build still exits 0 and every page
    // ships with no search box at all.
    //
    // `suggestion: false` is what keeps the worker lazy. With suggestions on,
    // the query-suggestion composable spins the worker up in onMounted, so the
    // index is fetched on every page load and the saving is lost.
    slimsearchPlugin({
      hotKeys: [{ key: 's' }, { key: '/' }],
      suggestion: false,
    }),
    markdownChartPlugin({}),
  ],
})
