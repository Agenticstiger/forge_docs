import { defineUserConfig } from 'vuepress'
import { defaultTheme } from '@vuepress/theme-default'
import { viteBundler } from '@vuepress/bundler-vite'

export default defineUserConfig({
  lang: 'en-US',
  title: 'Fluid Forge',
  description: 'Declarative data products for local and multi-cloud delivery with a contract-first CLI.',

  base: '/forge_docs/',

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
    ['meta', { name: 'theme-color', content: '#1a73e8' }],
    ['meta', { name: 'apple-mobile-web-app-capable', content: 'yes' }],
    ['meta', { name: 'apple-mobile-web-app-status-bar-style', content: 'black' }],
    ['meta', { property: 'og:title', content: 'Fluid Forge' }],
    ['meta', { property: 'og:description', content: 'Write contracts, validate locally, and deploy data products with the Fluid Forge CLI.' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:url', content: 'https://agenticstiger.github.io/forge_docs/' }],
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: 'Fluid Forge' }],
    ['meta', { name: 'twitter:description', content: 'Contract-first data product delivery with Fluid Forge.' }],
    ['meta', { name: 'keywords', content: 'fluid forge, data products, declarative data engineering, duckdb, bigquery, snowflake, aws, cli' }],
  ],

  theme: defaultTheme({
    logo: '/logo.png',

    navbar: [
      { text: 'Home', link: '/' },
      { text: 'Get Started', link: '/getting-started/' },
      {
        text: 'Walkthroughs',
        children: [
          { text: 'Local (DuckDB)', link: '/walkthrough/local' },
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
            '/forge-data-model.md',
            '/vision.md'
          ]
        },
        {
          text: 'Walkthroughs',
          children: [
            '/walkthrough/local.md',
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
            '/cli/version.md'
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
            '/advanced/mcp.md',
            '/advanced/credential-resolver.md',
            '/advanced/cost-tracking.md',
            '/advanced/agentic-primitives.md',
            '/advanced/v1.5-architecture.md',
            '/advanced/v1.5-release-notes.md'
          ]
        },
        {
          text: 'Project',
          children: [
            '/contributing.md',
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
})
