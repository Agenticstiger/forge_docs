// =====================================================================
// Fluid Forge — VuePress 2 client config
// =====================================================================
// Globally registers components so any markdown page can embed them
// without per-page imports:
//
//   <CliCast src="..." title="..." insight="..." />
//   <ClientOnly><Playground /></ClientOnly>   (in /playground/ only)
//
// Playground is async-loaded — Monaco is ~1 MB gzipped, so we pay the
// network cost only when the visitor actually navigates to /playground/.
// Every other doc page stays lean. ClientOnly avoids SSR-time errors
// (Monaco assumes `window`/`document` exist).
//
// Also overrides two theme layouts, both from layouts/. Layout names
// from this site-level client config win over the theme's because it is
// merged last.
//
//   Layout    — the theme's own layout, wrapped so that a skip-to-content
//               link is the first focusable element in the document and
//               the <main> landmark carries the id it points at
//               (WCAG 2.1 SC 2.4.1, Bypass Blocks, Level A).
//   NotFound  — the branded 404.
//
// Picked up at runtime via the `clientConfigFile` setting in config.ts.
// =====================================================================

import { defineClientConfig } from 'vuepress/client'
import { defineAsyncComponent } from 'vue'
import Layout from './layouts/Layout.vue'
import NotFound from './layouts/NotFound.vue'

// CliCast and Playground both async-load: CliCast carries scoped SCSS
// and only renders on demo-heavy pages; Playground pulls in Monaco
// (~1 MB gzipped) and only runs on /playground/. Every other doc page
// loads neither.
const CliCast = defineAsyncComponent(
  () => import('./components/CliCast.vue'),
)

const Playground = defineAsyncComponent(
  () => import('./components/Playground.vue'),
)

export default defineClientConfig({
  enhance({ app }) {
    app.component('CliCast', CliCast)
    app.component('Playground', Playground)
  },
  layouts: {
    Layout,
    NotFound,
  },
})
