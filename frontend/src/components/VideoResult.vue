<template>
  <div class="gradient-border overflow-hidden h-full">
    <!-- 视频信息头部 -->
    <div class="flex flex-col gap-5 p-5 sm:p-6">
      <div class="relative w-full aspect-video rounded-xl overflow-hidden bg-bg-card">
        <img
          v-if="video.thumbnail"
          :src="thumbnailUrl"
          :alt="video.title"
          class="w-full h-full object-cover"
          @error="(e) => e.target.style.display = 'none'"
        />
        <div v-else class="w-full h-full flex items-center justify-center text-text-muted">
          <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        </div>
        <div v-if="video.duration_string" class="absolute bottom-2 right-2 px-2 py-0.5 bg-black/70 text-white text-xs rounded-md">
          {{ video.duration_string }}
        </div>
      </div>

      <div class="flex-1 min-w-0">
        <h3 class="text-lg font-semibold text-text-primary leading-snug mb-2 line-clamp-2">
          {{ video.title }}
        </h3>
        <div class="flex flex-wrap items-center gap-3 text-sm text-text-secondary mb-3">
          <span class="inline-flex items-center gap-1">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            {{ video.uploader }}
          </span>
          <span class="inline-flex items-center gap-1 px-2 py-0.5 bg-primary-light text-primary rounded-full text-xs font-medium">
            {{ video.platform }}
          </span>
          <span v-if="video.view_count" class="inline-flex items-center gap-1">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            {{ formatViewCount(video.view_count) }}
          </span>
        </div>
        <p v-if="video.description" class="text-sm text-text-muted line-clamp-2">
          {{ video.description }}
        </p>
      </div>

      <!-- AI 总结按钮 -->
      <button
        @click="$emit('summarize')"
        :disabled="summarizing"
        class="w-full inline-flex items-center justify-center gap-2 h-12 px-8 rounded-full border-2 border-primary text-primary hover:bg-primary hover:text-white font-medium text-base transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-primary"
      >
        <svg v-if="summarizing" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        {{ summarizing ? '总结中...' : 'AI 总结' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  video: { type: Object, required: true },
  summarizing: Boolean,
})

defineEmits(['summarize'])

const thumbnailUrl = computed(() => {
  if (!props.video.thumbnail) return ''
  return '/api/proxy/thumbnail?url=' + encodeURIComponent(props.video.thumbnail)
})

function formatViewCount(count) {
  if (!count) return ''
  if (count >= 100000000) return (count / 100000000).toFixed(1) + '亿'
  if (count >= 10000) return (count / 10000).toFixed(1) + '万'
  return count.toLocaleString()
}
</script>
