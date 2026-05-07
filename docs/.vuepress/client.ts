// =====================================================================
// Fluid Forge — VuePress 2 client config
// =====================================================================
// Globally registers <CliCast> so any markdown page can embed an
// animated CLI demo without per-page imports.
//
//     <CliCast
//       src="/forge_docs/demos/local-quickstart.svg"
//       title="fluid init … → validate → plan → apply"
//       insight="30 seconds. No cloud account. | …"
//     />
//
// Picked up at runtime via the `clientConfigFile` setting in config.ts.
// =====================================================================

import { defineClientConfig } from 'vuepress/client'
import CliCast from './components/CliCast.vue'

export default defineClientConfig({
  enhance({ app }) {
    app.component('CliCast', CliCast)
  },
})
