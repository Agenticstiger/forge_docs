<!--
  Fluid Forge — interactive YAML playground
  ============================================================
  In-browser editor pre-loaded with FLUID-spec contracts so visitors
  can poke at real schemas without installing the CLI.

  Scope of THIS commit (Phase 2B v1):
    - Monaco editor with YAML syntax highlighting + auto-completion
      (built-in YAML language support)
    - 4 starter templates: Local/DuckDB, GCP/BigQuery, AWS/Athena,
      Snowflake — switchable via tabs
    - Copy-to-clipboard button
    - "Open in CLI" instruction block (paste into local file, run
      `fluid validate`)

  Deferred to a follow-up:
    - In-browser `fluid validate` via Pyodide-compiled CLI or a
      hosted serverless validator
    - Sharing — generate a permalink that round-trips the editor's
      buffer through URL params

  Lazy-loaded: the Monaco bundle is ~1 MB gzipped. Only the playground
  route triggers it; every other doc page stays lean.
  ============================================================
-->

<template>
  <div class="ff-playground">
    <header class="ff-playground__header">
      <h2 class="ff-playground__title">FLUID contract playground</h2>
      <p class="ff-playground__subtitle">
        Pick a template, edit, copy. Validation in browser is on the roadmap;
        for now, paste into a local file and run <code>fluid validate</code>.
      </p>
    </header>

    <nav class="ff-playground__tabs" role="tablist">
      <button
        v-for="t in templates"
        :key="t.id"
        :class="['ff-playground__tab', { active: active === t.id }]"
        role="tab"
        :aria-selected="active === t.id"
        @click="loadTemplate(t.id)"
      >
        <span class="ff-playground__tab-icon">{{ t.icon }}</span>
        {{ t.label }}
      </button>
    </nav>

    <div class="ff-playground__editor-wrap">
      <div
        ref="editorRoot"
        class="ff-playground__editor"
        :class="{ 'ff-playground__editor--loading': !editorReady }"
        aria-label="YAML editor"
      ></div>
      <div v-if="!editorReady" class="ff-playground__loading">
        <span class="ff-playground__spinner" aria-hidden="true"></span>
        Loading editor (Monaco, ~1 MB)…
      </div>
    </div>

    <div class="ff-playground__actions">
      <button class="ff-playground__action" @click="copyToClipboard">
        <span aria-hidden="true">📋</span>
        {{ copyState }}
      </button>
      <button class="ff-playground__action" @click="resetToTemplate">
        <span aria-hidden="true">↺</span>
        Reset to template
      </button>
      <span class="ff-playground__hint">
        Then run <code>fluid validate &lt;file&gt;</code> on the saved YAML.
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

interface Template {
  id: string
  label: string
  icon: string
  body: string
}

// Templates pulled from real working contracts (the 4 binding.platform
// values that ship as production providers). Trimmed to ~30 lines each
// so the playground tabs feel snappy on first paint.
const templates: Template[] = [
  {
    id: 'local',
    label: 'Local · DuckDB',
    icon: '🏠',
    body: `# Local — DuckDB / Parquet (no cloud account required)
fluidVersion: "0.7.2"
kind: DataProduct
id: gold.crypto.bitcoin_tracker_v1
name: Bitcoin Price Tracker
description: Hourly BTC price snapshots, runs on your laptop.
domain: crypto

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-team@example.com
  tags: [real-time, pricing]

builds:
  - id: bitcoin_price_ingestion
    pattern: embedded-logic
    engine: sql
    properties:
      sql: |
        SELECT CURRENT_TIMESTAMP AS price_timestamp,
               price AS price_usd
        FROM raw_btc_feed

exposes:
  - exposeId: bitcoin_prices
    title: Bitcoin Hourly Prices
    kind: table
    binding:
      platform: local
      format: parquet
      location:
        path: ./runtime/out/bitcoin_prices.parquet
    contract:
      schema:
        - name: price_timestamp
          type: TIMESTAMP
          required: true
        - name: price_usd
          type: NUMERIC
          required: true
          description: Bitcoin price in USD
      dq:
        rules:
          - id: price_not_null
            type: completeness
            selector: price_usd
            threshold: 1.0
            operator: ">="
            severity: error
`,
  },
  {
    id: 'gcp',
    label: 'GCP · BigQuery',
    icon: '☁️',
    body: `# GCP — BigQuery
fluidVersion: "0.7.2"
kind: DataProduct
id: analytics.customers_v1
name: Customer Analytics
domain: customer

metadata:
  layer: Gold
  owner:
    team: data-engineering
    email: data-eng@example.com

exposes:
  - exposeId: customers_table
    kind: table
    binding:
      platform: gcp
      format: bigquery_table
      location:
        project: my-project
        dataset: analytics
        table: customers
        region: europe-west3
    contract:
      schema:
        - name: id
          type: INTEGER
          required: true
        - name: email
          type: STRING
          required: true
          sensitivity: pii        # auto-masking on cloud IAM

accessPolicy:
  grants:
    - principal: "group:analysts@example.com"
      permissions: ["read"]

agentPolicy:
  allowedModels: ["gpt-4", "claude-3-opus"]
  allowedUseCases: ["analysis"]
`,
  },
  {
    id: 'aws',
    label: 'AWS · Athena',
    icon: '🔶',
    body: `# AWS — S3 + Athena (Glue catalog)
fluidVersion: "0.7.2"
kind: DataProduct
id: bronze.events.web_clickstream_v1
name: Web Clickstream
domain: events

metadata:
  layer: Bronze
  owner:
    team: data-eng
    email: data-eng@example.com

exposes:
  - exposeId: clickstream_table
    kind: table
    binding:
      platform: aws
      format: s3_file
      location:
        bucket: example-data-lake
        prefix: events/web_clickstream/
        region: eu-west-1
    contract:
      schema:
        - name: ts
          type: TIMESTAMP
          required: true
        - name: user_id
          type: STRING
        - name: event
          type: STRING
          required: true
        - name: properties
          type: STRING
`,
  },
  {
    id: 'snowflake',
    label: 'Snowflake',
    icon: '❄️',
    body: `# Snowflake
fluidVersion: "0.7.2"
kind: DataProduct
id: gold.customer_360_v1
name: Customer 360
domain: customer

metadata:
  layer: Gold
  owner:
    team: customer-platform
    email: cust-platform@example.com

exposes:
  - exposeId: customer_360_table
    kind: table
    binding:
      platform: snowflake
      format: snowflake_table
      location:
        database: PROD
        schema: GOLD
        table: CUSTOMER_360
    contract:
      schema:
        - name: customer_id
          type: STRING
          required: true
        - name: ltv
          type: NUMERIC
        - name: email
          type: STRING
          sensitivity: pii
      dq:
        rules:
          - id: customer_id_not_null
            type: completeness
            selector: customer_id
            threshold: 1.0
            operator: ">="
            severity: error

accessPolicy:
  grants:
    - principal: "role:DATA_ANALYST"
      permissions: ["read"]
`,
  },
]

const editorRoot = ref<HTMLElement | null>(null)
const editorReady = ref(false)
const active = ref<string>('local')
const copyState = ref('Copy YAML')

let editor: any = null
let monacoModule: any = null

async function ensureMonaco() {
  if (monacoModule) return monacoModule
  // Dynamic import keeps the ~1 MB Monaco bundle out of the rest of the
  // site. Only the playground route ever pays the network cost.
  monacoModule = await import('monaco-editor')
  return monacoModule
}

function getTemplate(id: string): Template {
  return templates.find((t) => t.id === id) ?? templates[0]
}

function loadTemplate(id: string) {
  active.value = id
  if (editor) {
    editor.setValue(getTemplate(id).body)
  }
}

function resetToTemplate() {
  if (editor) {
    editor.setValue(getTemplate(active.value).body)
  }
}

async function copyToClipboard() {
  if (!editor) return
  const text = editor.getValue()
  try {
    await navigator.clipboard.writeText(text)
    copyState.value = 'Copied ✓'
  } catch {
    copyState.value = 'Copy failed (use Cmd+C)'
  }
  setTimeout(() => {
    copyState.value = 'Copy YAML'
  }, 1800)
}

onMounted(async () => {
  if (!editorRoot.value) return
  const monaco = await ensureMonaco()
  editor = monaco.editor.create(editorRoot.value, {
    value: getTemplate(active.value).body,
    language: 'yaml',
    theme:
      typeof document !== 'undefined' &&
      document.documentElement.getAttribute('data-theme') === 'dark'
        ? 'vs-dark'
        : 'vs',
    minimap: { enabled: false },
    fontSize: 14,
    fontFamily:
      "JetBrains Mono, ui-monospace, SF Mono, Menlo, Consolas, monospace",
    scrollBeyondLastLine: false,
    automaticLayout: true,
    tabSize: 2,
    wordWrap: 'on',
  })
  editorReady.value = true

  // React to theme toggles in the default theme
  if (typeof MutationObserver !== 'undefined') {
    const obs = new MutationObserver(() => {
      const dark =
        document.documentElement.getAttribute('data-theme') === 'dark'
      monaco.editor.setTheme(dark ? 'vs-dark' : 'vs')
    })
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
  }
})

onBeforeUnmount(() => {
  if (editor) {
    editor.dispose()
    editor = null
  }
})
</script>

<style lang="scss" scoped>
.ff-playground {
  margin: 32px 0;
  border-radius: 12px;
  border: 1px solid var(--vp-c-border);
  overflow: hidden;

  &__header {
    padding: 24px 24px 16px;
    background: var(--ff-hero-gradient-soft);
    border-bottom: 1px solid var(--vp-c-border);
  }

  &__title {
    margin: 0 0 4px;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--vp-c-text);
    border: 0;
  }

  &__subtitle {
    margin: 0;
    color: var(--vp-c-text-mute);
    font-size: 0.9rem;
    line-height: 1.5;

    code {
      font-size: 0.85em;
      padding: 1px 6px;
    }
  }

  &__tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 12px 12px 0;
    border-bottom: 1px solid var(--vp-c-border);
    background: var(--vp-c-bg-alt);
  }

  &__tab {
    background: transparent;
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 8px 14px;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--vp-c-text-mute);
    cursor: pointer;
    border-radius: 6px 6px 0 0;
    transition: color 120ms ease, border-color 120ms ease,
      background-color 120ms ease;

    &:hover {
      color: var(--vp-c-text);
      background: var(--vp-c-bg);
    }

    &.active {
      color: var(--vp-c-accent);
      border-bottom-color: var(--vp-c-accent);
      background: var(--vp-c-bg);
    }
  }

  &__tab-icon {
    margin-right: 6px;
  }

  &__editor-wrap {
    position: relative;
    height: 460px;
    background: var(--vp-c-bg);
  }

  &__editor {
    width: 100%;
    height: 100%;

    &--loading {
      opacity: 0.4;
    }
  }

  &__loading {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: var(--vp-c-text-mute);
    font-size: 0.95rem;
    pointer-events: none;
  }

  &__spinner {
    width: 18px;
    height: 18px;
    border: 2px solid var(--vp-c-border);
    border-top-color: var(--vp-c-accent);
    border-radius: 50%;
    animation: ff-spin 0.7s linear infinite;
  }

  &__actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px 16px;
    background: var(--vp-c-bg-alt);
    border-top: 1px solid var(--vp-c-border);
    font-size: 0.875rem;
  }

  &__action {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: var(--vp-c-bg);
    border: 1px solid var(--vp-c-border);
    border-radius: 6px;
    color: var(--vp-c-text);
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    transition: border-color 120ms ease, color 120ms ease;

    &:hover {
      border-color: var(--vp-c-accent);
      color: var(--vp-c-accent);
    }
  }

  &__hint {
    color: var(--vp-c-text-subtle);
    font-size: 0.8rem;

    code {
      font-size: 0.85em;
    }
  }
}

@keyframes ff-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
