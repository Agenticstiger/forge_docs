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
// Picked up at runtime via the `clientConfigFile` setting in config.ts.
// =====================================================================

import { defineClientConfig } from 'vuepress/client'
import { defineAsyncComponent } from 'vue'
import CliCast from './components/CliCast.vue'

const Playground = defineAsyncComponent(
  () => import('./components/Playground.vue'),
)

export default defineClientConfig({
  enhance({ app }) {
    app.component('CliCast', CliCast)
    app.component('Playground', Playground)
  },
})
