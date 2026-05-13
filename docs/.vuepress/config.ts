import { defineUserConfig } from 'vuepress'
import { defaultTheme } from '@vuepress/theme-default'
import { viteBundler } from '@vuepress/bundler-vite'
import { copyCodePlugin } from '@vuepress/plugin-copy-code'
import { searchPlugin } from '@vuepress/plugin-search'
import { sitemapPlugin } from '@vuepress/plugin-sitemap'
import { markdownChartPlugin } from '@vuepress/plugin-markdown-chart'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineUserConfig({
  lang: 'en-US',
  title: 'Fluid Forge',
  description: 'Declarative data products for local and multi-cloud delivery with a contract-first CLI.',

  base: '/forge_docs/',

  // Loads client.ts so <CliCast> is registered globally for markdown pages.
  clientConfigFile: resolve(__dirname, './client.ts'),

  bundler: viteBundler({
    viteOptions: {
      build: {
        rollupOptions: {
          output: {
            manualChunks: undefined
          }
        }
      }
    }
  }),

  shouldPrefetch: false,
  shouldPreload: false,

  head: [
    ['link', { rel: 'icon', href: '/forge_docs/logo.png' }],
    ['meta', { name: 'theme-color', content: '#2563eb' }], // brand blue (Phase 2A foundation)
    ['meta', { name: 'apple-mobile-web-app-capable', content: 'yes' }],
    ['meta', { name: 'apple-mobile-web-app-status-bar-style', content: 'black' }],

    // Open Graph — full social card (Phase 2A polish)
    ['meta', { property: 'og:title', content: 'Fluid Forge — Declarative Data Products' }],
    ['meta', { property: 'og:description', content: 'Write YAML, deploy anywhere. One contract, every cloud. What Terraform did for infrastructure, Fluid Forge does for data products.' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:url', content: 'https://agenticstiger.github.io/forge_docs/' }],
    ['meta', { property: 'og:image', content: 'https://agenticstiger.github.io/forge_docs/og-card.png' }],
    ['meta', { property: 'og:image:width', content: '1200' }],
    ['meta', { property: 'og:image:height', content: '630' }],
    ['meta', { property: 'og:site_name', content: 'Fluid Forge' }],

    // Twitter / X
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: 'Fluid Forge — Declarative Data Products' }],
    ['meta', { name: 'twitter:description', content: 'Write YAML, deploy anywhere. One contract, every cloud.' }],
    ['meta', { name: 'twitter:image', content: 'https://agenticstiger.github.io/forge_docs/og-card.png' }],

    ['meta', { name: 'keywords', content: 'fluid forge, data products, declarative data engineering, duckdb, bigquery, snowflake, aws, cli' }],
  ],

  theme: defaultTheme({
    logo: '/logo.png',

    navbar: [
      { text: 'Home', link: '/' },
      { text: 'Get Started', link: '/getting-started/' },
      { text: 'See it run', link: '/see-it-run' },
      {
        text: 'Walkthroughs',
        children: [
          { text: 'Local (DuckDB)', link: '/walkthrough/local' },
          { text: 'Source-Aligned (Postgres → DuckDB)', link: '/walkthrough/source-aligned-postgres-duckdb' },
          { text: 'AI Forge + Data Models', link: '/walkthrough/ai-forge-data-model' },
          { text: 'GCP (BigQuery)', link: '/walkthrough/gcp' },
          { text: 'Snowflake Team Collaboration', link: '/walkthrough/snowflake' },
          { text: 'Declarative Airflow', link: '/walkthrough/airflow-declarative' },
          { text: 'Orchestration Export', link: '/walkthrough/export-orchestration' },
          { text: 'Jenkins CI/CD', link: '/walkthrough/jenkins-cicd' },
          { text: 'Universal Pipeline', link: '/walkthrough/universal-pipeline' }
        ]
      },
      { text: 'CLI Reference', link: '/cli/' },
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
      { text: 'Demos', link: '/demos/' },
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
      },
      {
        text: 'GitHub',
        link: 'https://github.com/Agenticstiger/forge-cli'
      }
    ],

    sidebar: {
      '/': [
        {
          text: 'Introduction',
          children: [
            '/README.md',
            '/getting-started/',
            '/getting-started/snowflake.md',
            '/see-it-run.md',
            '/forge-data-model.md',
            '/vision.md'
          ]
        },
        {
          text: 'Data Products',
          children: [
            '/data-products/product-type.md'
          ]
        },
        {
          text: 'Walkthroughs',
          children: [
            '/walkthrough/local.md',
            '/walkthrough/source-aligned-postgres-duckdb.md',
            '/walkthrough/ai-forge-data-model.md',
            '/walkthrough/gcp.md',
            '/walkthrough/snowflake.md',
            '/walkthrough/airflow-declarative.md',
            '/walkthrough/export-orchestration.md',
            '/walkthrough/jenkins-cicd.md',
            '/walkthrough/universal-pipeline.md'
          ]
        },
        {
          text: 'CLI Reference',
          children: [
            '/cli/README.md',
            // Core workflow
            '/cli/init.md',
            '/cli/demo.md',
            '/cli/forge.md',
            '/cli/skills.md',
            '/cli/status.md',
            '/cli/validate.md',
            '/cli/plan.md',
            '/cli/apply.md',
            // Generate & visualize
            '/cli/generate.md',
            '/cli/generate-airflow.md',
            '/cli/generate-pipeline.md',
            '/cli/viz-graph.md',
            // Standards & interop
            '/cli/odps.md',
            '/cli/odps-bitol.md',
            '/cli/odcs.md',
            '/cli/export.md',
            '/cli/export-opds.md',
            // Integrations
            '/cli/publish.md',
            '/cli/datamesh-manager.md',
            '/cli/market.md',
            '/cli/import.md',
            // Quality & governance
            '/cli/policy-check.md',
            '/cli/policy-compile.md',
            '/cli/policy-apply.md',
            '/cli/contract-tests.md',
            '/cli/contract-validation.md',
            '/cli/diff.md',
            '/cli/test.md',
            '/cli/verify.md',
            // Project & workspace
            '/cli/product-new.md',
            '/cli/product-add.md',
            '/cli/workspace.md',
            '/cli/ide.md',
            '/cli/ai.md',
            '/cli/memory.md',
            '/cli/mcp.md',
            // CI & scaffolding
            '/cli/scaffold-ci.md',
            '/cli/scaffold-composer.md',
            '/cli/docs.md',
            // Utilities
            '/cli/config.md',
            '/cli/split.md',
            '/cli/bundle.md',
            '/cli/auth.md',
            '/cli/doctor.md',
            '/cli/providers.md',
            '/cli/provider-init.md',
            '/cli/roadmap.md',
            '/cli/version.md',
            // Source-aligned acquisition (next release)
            '/cli/runs.md',
            '/cli/retention.md',
            '/cli/secrets.md',
            '/cli/stats.md',
            '/cli/contract.md',
            '/cli/ship.md'
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
          text: 'Advanced',
          children: [
            '/advanced/blueprints.md',
            '/advanced/governance.md',
            '/advanced/airflow.md',
            '/advanced/custom-llm-agents.md',
            '/advanced/chatgpt-forge-contract-gpt/',
            '/advanced/forge-copilot-discovery.md',
            '/advanced/forge-copilot-memory.md',
            '/advanced/llm-providers.md',
            '/advanced/capability-warnings.md',
            '/advanced/litellm-backend.md',
            '/advanced/mcp.md',
            '/advanced/credential-resolver.md',
            '/advanced/cost-tracking.md',
            '/advanced/agentic-primitives.md',
            '/advanced/typed-errors.md',
            '/advanced/typed-cli-errors.md',
            '/advanced/forge-tools.md',
            '/advanced/source-aligned-acquisition.md',
            '/advanced/api-stability.md',
            '/advanced/guided-forge-ux.md',
            '/advanced/v1.5-architecture.md',
            '/advanced/v1.5-release-notes.md'
          ]
        },
        {
          text: 'Project',
          children: [
            '/contributing.md',
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
  // - copy-code: one-click copy on every fenced code block
  // - search: client-side fuzzy search (Cmd+K / "/" hotkey). DocSearch
  //   was the original target; client-side keeps us free of external
  //   indexing dependencies and works offline in dev.
  // - sitemap: writes /sitemap.xml at build time using the canonical URL
  // - markdown-chart: renders ```mermaid blocks at build time so they
  //   show on the live site (without this plugin Mermaid only renders
  //   on github.com READMEs).
  plugins: [
    copyCodePlugin({}),
    searchPlugin({
      maxSuggestions: 12,
      hotKeys: ['s', '/'],
    }),
    sitemapPlugin({
      hostname: 'https://agenticstiger.github.io/forge_docs/',
    }),
    markdownChartPlugin({
      mermaid: true,
    }),
  ],
})
