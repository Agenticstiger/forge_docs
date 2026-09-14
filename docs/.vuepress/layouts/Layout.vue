<!--
  Fluid Forge — default layout with a skip-to-content bypass
  ============================================================
  WCAG 2.1 SC 2.4.1 (Bypass Blocks, Level A). The default theme renders
  the whole sidebar tree on every interior page, so a keyboard visitor
  landing on /cli/init crosses 300+ focusable stops before reaching the
  first word of the page. There is no bypass mechanism in the stock
  theme, so this layout wraps it and adds one.

  Two halves, and both are needed:

    1. The link itself is the FIRST focusable element in the document —
       it is rendered before <ParentLayout>, whose own first child is
       the navbar. It is off-screen until focused (translated out of
       view, never `display: none`, which would remove it from the tab
       order entirely). Styles live in styles/index.scss as
       `.ff-skip-link`.

    2. The target. The theme's <main> (VPPage / VPHome) carries no id,
       so there is nothing to skip TO. Both components are single-root
       <main> elements, so attributes fall through: rendering them here
       through the Layout's `page` slot puts `id` and `tabindex="-1"`
       straight onto the <main> landmark at SSR time, which is what
       makes the id greppable in the built HTML rather than something
       JavaScript patches in after hydration.

  The click handler is belt-and-braces: a bare fragment href does move
  focus in a browser, but this site is a router-driven SPA after
  hydration, so focus is moved explicitly and the URL is left clean.

  Everything imported here comes from @vuepress/theme-default's public
  `exports` map (./client, ./layouts/*, ./components/*) — no deep reach
  into dist/ internals, so a theme upgrade cannot silently break it.
-->

<script setup lang="ts">
import { useData, useScrollPromise } from '@vuepress/theme-default/client'
import ParentLayout from '@vuepress/theme-default/layouts/Layout.vue'
import VPFadeSlideYTransition from '@vuepress/theme-default/components/VPFadeSlideYTransition.vue'
import VPHome from '@vuepress/theme-default/components/VPHome.vue'
import VPPage from '@vuepress/theme-default/components/VPPage.vue'

const MAIN_ID = 'main-content'

const { frontmatter, page } = useData()

// Same wiring the theme's own `page` slot default uses, so overriding
// the slot does not cost us the page transition or its scroll timing.
const scrollPromise = useScrollPromise()
const onBeforeEnter = scrollPromise.resolve
const onBeforeLeave = scrollPromise.pending

const skipToContent = (event: MouseEvent): void => {
  const target = document.getElementById(MAIN_ID)

  if (!target) return

  event.preventDefault()
  target.focus()
  target.scrollIntoView()
}
</script>

<template>
  <a class="ff-skip-link" :href="`#${MAIN_ID}`" @click="skipToContent">
    Skip to main content
  </a>

  <ParentLayout>
    <template #page>
      <VPFadeSlideYTransition
        @before-enter="onBeforeEnter"
        @before-leave="onBeforeLeave"
      >
        <VPHome v-if="frontmatter.home" :id="MAIN_ID" tabindex="-1" />
        <VPPage v-else :key="page.path" :id="MAIN_ID" tabindex="-1" />
      </VPFadeSlideYTransition>
    </template>
  </ParentLayout>
</template>
