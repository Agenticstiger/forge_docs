<!--
  Fluid Forge — VideoEmbed component
  ============================================================
  Privacy-respecting "lite-youtube" / "lite-loom" pattern: shows a
  thumbnail with a play button until the user clicks. No iframe loads,
  no third-party cookies, no analytics calls until intent.

  Usage in markdown (interior pages):

    ---
    title: Local walkthrough
    videoId: dQw4w9WgXcQ          # YouTube video ID, or
    videoProvider: youtube         # 'youtube' (default) or 'loom'
    videoTitle: Local quickstart in 90 seconds
    ---

    <VideoEmbed v-if="$frontmatter.videoId"
                :id="$frontmatter.videoId"
                :provider="$frontmatter.videoProvider"
                :title="$frontmatter.videoTitle" />

  Or directly in a markdown body:
    <VideoEmbed id="dQw4w9WgXcQ" title="Local quickstart" />

  Registered globally as <VideoEmbed> via VuePress 2's
  @vuepress/plugin-register-components default-theme behavior — every
  .vue file inside docs/.vuepress/components/ is auto-registered with
  the kebab-cased filename.
  ============================================================
-->

<template>
  <div
    class="ff-video"
    :class="{ 'ff-video--loaded': loaded }"
    role="region"
    :aria-label="title || 'Embedded video'"
  >
    <button
      v-if="!loaded"
      type="button"
      class="ff-video__poster"
      :style="posterStyle"
      :aria-label="`Play ${title || 'video'}`"
      @click="loaded = true"
    >
      <span class="ff-video__play" aria-hidden="true">
        <svg viewBox="0 0 64 64" width="48" height="48">
          <circle cx="32" cy="32" r="32" fill="rgba(0, 0, 0, 0.7)" />
          <path d="M24 18 L48 32 L24 46 Z" fill="white" />
        </svg>
      </span>
      <span v-if="title" class="ff-video__title">{{ title }}</span>
      <span class="ff-video__hint">Click to load · {{ providerName }} · loads no third-party JS until you click</span>
    </button>

    <iframe
      v-else
      :src="embedUrl"
      :title="title || 'Embedded video'"
      frameborder="0"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
      allowfullscreen
      loading="lazy"
      class="ff-video__iframe"
    ></iframe>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface Props {
  id: string
  provider?: 'youtube' | 'loom'
  title?: string
  /**
   * Override the thumbnail URL. Defaults to YouTube's mqdefault.jpg
   * for YouTube videos; Loom doesn't expose public thumbnails so we
   * fall back to a brand-coloured placeholder.
   */
  poster?: string
}

const props = withDefaults(defineProps<Props>(), {
  provider: 'youtube',
})

const loaded = ref(false)

const providerName = computed(() =>
  props.provider === 'loom' ? 'Loom' : 'YouTube',
)

const embedUrl = computed(() => {
  if (props.provider === 'loom') {
    return `https://www.loom.com/embed/${props.id}?autoplay=1`
  }
  // youtube-nocookie domain → no third-party cookies until autoplay
  return `https://www.youtube-nocookie.com/embed/${props.id}?autoplay=1&rel=0`
})

const posterStyle = computed(() => {
  if (props.poster) {
    return { backgroundImage: `url(${props.poster})` }
  }
  if (props.provider === 'youtube') {
    return {
      backgroundImage: `url(https://i.ytimg.com/vi/${props.id}/hqdefault.jpg)`,
    }
  }
  // No public thumbnail for Loom — use the brand gradient placeholder
  return {}
})
</script>

<style lang="scss" scoped>
.ff-video {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  margin: 24px 0;
  border-radius: 12px;
  overflow: hidden;
  background: var(--ff-hero-gradient-soft);
  border: 1px solid var(--vp-c-border);

  &__poster {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: 0;
    padding: 0;
    cursor: pointer;
    background-size: cover;
    background-position: center;
    background-color: var(--vp-c-bg-alt);
    color: white;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;

    &::before {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(
        to bottom,
        rgba(0, 0, 0, 0.05) 0%,
        rgba(0, 0, 0, 0.3) 100%
      );
      pointer-events: none;
    }

    &:hover .ff-video__play svg circle {
      fill: var(--vp-c-accent);
    }
  }

  &__play {
    position: relative;
    z-index: 1;
    transition: transform 200ms ease;

    .ff-video__poster:hover & {
      transform: scale(1.08);
    }
  }

  &__title {
    position: relative;
    z-index: 1;
    font-size: 1.1rem;
    font-weight: 600;
    text-align: center;
    padding: 0 16px;
  }

  &__hint {
    position: relative;
    z-index: 1;
    font-size: 0.75rem;
    opacity: 0.85;
    padding: 0 16px;
  }

  &__iframe {
    width: 100%;
    height: 100%;
    border: 0;
  }
}
</style>
