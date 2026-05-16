<template>
  <main class="flex-1 max-w-5xl mx-auto px-4 sm:px-6 py-8">
    <div class="text-center mb-8">
      <h1 class="text-2xl sm:text-3xl font-bold text-text-primary mb-2">批量字幕提取</h1>
      <p class="text-text-secondary text-sm sm:text-base">粘贴多个视频链接，每行一个，批量提取字幕文本（不调用AI，速度快）</p>
    </div>

    <!-- 输入区 -->
    <div class="gradient-border p-5 sm:p-6 mb-6">
      <textarea
        v-model="urlInput"
        :disabled="processing"
        rows="8"
        placeholder="https://www.bilibili.com/video/BV1xx...
https://www.youtube.com/watch?v=abc...
https://www.douyin.com/video/123...

每行一个视频链接，最多20个"
        class="w-full px-4 py-3 rounded-xl border border-border bg-bg-card text-sm text-text-primary placeholder:text-text-muted input-glow transition-all resize-y min-h-[160px] font-mono"
      ></textarea>
      <div class="flex items-center justify-between mt-3">
        <span class="text-xs text-text-muted">
          已输入 <strong :class="urlCount > 20 ? 'text-error' : 'text-primary'">{{ urlCount }}</strong> 个链接（最多20个）
        </span>
        <button
          @click="startExtract"
          :disabled="processing || urlCount === 0 || urlCount > 20"
          class="flex items-center gap-2 px-6 py-2.5 rounded-xl btn-primary text-white text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          <svg v-if="processing" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          {{ processing ? `提取中 (${progressCurrent}/${progressTotal})...` : '开始提取字幕' }}
        </button>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="results.length > 0 || errors.length > 0" class="space-y-4">
      <div class="flex items-center justify-between mb-2">
        <h2 class="text-lg font-semibold text-text-primary">提取结果</h2>
        <div class="flex items-center gap-2">
          <button
            v-if="hasAnySubtitle"
            @click="copyAllSubtitles"
            class="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg btn-primary text-white hover:opacity-90 transition-opacity cursor-pointer"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            {{ copyAllSuccess ? '已复制' : '复制全部字幕' }}
          </button>
          <button
            v-if="hasAnySubtitle"
            @click="downloadAllSubtitles"
            class="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-border text-text-secondary hover:bg-bg-card transition-colors cursor-pointer"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            下载全部 (TXT)
          </button>
        </div>
      </div>

      <!-- 成功结果 -->
      <div
        v-for="(item, idx) in results"
        :key="'r-' + idx"
        class="gradient-border overflow-hidden"
      >
        <div class="flex items-center justify-between px-5 py-3 bg-bg-section border-b border-border">
          <div class="flex items-center gap-2 min-w-0">
            <span class="flex-shrink-0 text-xs font-bold text-text-muted w-6">{{ idx + 1 }}</span>
            <span class="text-sm font-medium text-text-primary truncate">{{ item.title || item.url }}</span>
            <span class="flex-shrink-0 px-2 py-0.5 text-xs rounded-full"
              :class="platformClass(item.platform)">
              {{ platformLabel(item.platform) }}
            </span>
            <span v-if="item.subtitle.has_subtitle" class="flex-shrink-0 text-success">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
            </span>
            <span v-else class="flex-shrink-0 text-text-muted text-xs">无字幕</span>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <button
              v-if="item.subtitle.has_subtitle"
              @click="item.viewMode = item.viewMode === 'plain' ? 'segment' : 'plain'"
              class="text-xs text-primary hover:text-primary-dark transition-colors cursor-pointer px-2 py-1 rounded hover:bg-primary-light"
            >
              {{ item.viewMode === 'plain' ? '分段' : '纯文本' }}
            </button>
            <button
              v-if="item.subtitle.has_subtitle"
              @click="copySingleSubtitle(idx)"
              class="text-xs text-primary hover:text-primary-dark transition-colors cursor-pointer px-2 py-1 rounded hover:bg-primary-light"
            >
              {{ item.copied ? '已复制' : '复制' }}
            </button>
            <button
              v-if="item.subtitle.has_subtitle"
              @click="downloadSingleSubtitle(idx)"
              class="text-xs text-primary hover:text-primary-dark transition-colors cursor-pointer px-2 py-1 rounded hover:bg-primary-light"
            >
              下载
            </button>
          </div>
        </div>

        <!-- 有字幕 -->
        <div v-if="item.subtitle.has_subtitle" class="p-4 max-h-[300px] overflow-y-auto">
          <!-- 分段视图 -->
          <div v-if="item.viewMode === 'segment'" class="space-y-1">
            <div
              v-for="(seg, si) in item.subtitle.segments"
              :key="si"
              class="flex gap-3 py-1.5 px-2 rounded-lg hover:bg-bg-card transition-colors"
            >
              <span class="flex-shrink-0 text-xs text-primary font-mono pt-0.5 min-w-[55px]">
                {{ formatTime(seg.start) }}
              </span>
              <span class="text-sm text-text-primary leading-relaxed">{{ seg.text }}</span>
            </div>
          </div>
          <!-- 纯文本视图 -->
          <div v-else class="bg-bg-card border border-border rounded-lg p-4 text-sm text-text-primary leading-relaxed whitespace-pre-wrap break-words">
            {{ item.subtitle.full_text }}
          </div>
        </div>
        <!-- 无字幕 -->
        <div v-else class="p-6 text-center text-text-muted text-sm">
          该视频没有可用的字幕
        </div>
      </div>

      <!-- 失败项 -->
      <div
        v-for="(item, idx) in errors"
        :key="'e-' + idx"
        class="gradient-border overflow-hidden border-error/30"
      >
        <div class="flex items-center gap-2 px-5 py-3 bg-error/5">
          <span class="text-error">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </span>
          <span class="text-sm text-error truncate">{{ item.url }}</span>
          <span class="text-xs text-error/70 ml-auto">{{ item.message }}</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!processing" class="text-center py-16 text-text-muted">
      <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <p class="text-sm">在上方输入视频链接，点击"开始提取字幕"</p>
    </div>
  </main>
</template>

<script setup>
import { ref, computed } from 'vue'
import { batchSubtitles } from '../api/batch.js'

const props = defineProps({
  user: { type: Object, default: null },
})
const emit = defineEmits(['need-login'])

const urlInput = ref('')
const processing = ref(false)
const progressCurrent = ref(0)
const progressTotal = ref(0)
const results = ref([])
const errors = ref([])
const copyAllSuccess = ref(false)

const urlCount = computed(() => {
  return urlInput.value.split('\n').filter(u => u.trim()).length
})

const hasAnySubtitle = computed(() => {
  return results.value.some(r => r.subtitle && r.subtitle.has_subtitle)
})

function platformLabel(platform) {
  const map = { bilibili: 'B站', youtube: 'YouTube', douyin: '抖音' }
  return map[platform] || '其他'
}

function platformClass(platform) {
  const map = {
    bilibili: 'bg-primary-light text-primary border border-primary/20',
    youtube: 'bg-error/10 text-error border border-error/20',
    douyin: 'bg-bg-card text-text-secondary border border-border',
  }
  return map[platform] || 'bg-bg-card text-text-muted border border-border'
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

async function startExtract() {
  if (!props.user) {
    emit('need-login')
    return
  }

  const urls = urlInput.value.split('\n').map(u => u.trim()).filter(u => u)
  if (urls.length === 0 || urls.length > 20) return

  processing.value = true
  progressCurrent.value = 0
  progressTotal.value = urls.length
  results.value = []
  errors.value = []

  try {
    await batchSubtitles(urls, {
      progress: (data) => {
        try {
          const parsed = JSON.parse(data)
          progressCurrent.value = parsed.current
          progressTotal.value = parsed.total
        } catch {}
      },
      result: (data) => {
        try {
          const parsed = JSON.parse(data)
          results.value.push({
            url: parsed.url,
            title: parsed.title || parsed.url,
            platform: parsed.platform,
            subtitle: parsed.subtitle || { has_subtitle: false },
            viewMode: 'plain',
            copied: false,
          })
        } catch {}
      },
      error: (data) => {
        try {
          const parsed = JSON.parse(data)
          errors.value.push({ url: parsed.url, message: parsed.message })
        } catch {}
      },
      done: (data) => {
        processing.value = false
      },
    })
  } catch (err) {
    processing.value = false
    if (err.message && err.message.includes('401')) {
      emit('need-login')
      return
    }
    alert('批量提取失败: ' + err.message)
  }
}

function copySingleSubtitle(idx) {
  const item = results.value[idx]
  if (!item || !item.subtitle.full_text) return
  navigator.clipboard.writeText(item.subtitle.full_text).then(() => {
    item.copied = true
    setTimeout(() => { item.copied = false }, 2000)
  }).catch(() => {
    alert('复制失败，请手动选中复制')
  })
}

function downloadSingleSubtitle(idx) {
  const item = results.value[idx]
  if (!item || !item.subtitle.full_text) return
  const filename = (item.title || '视频').replace(/[\\/*?:"<>|]/g, '_').substring(0, 80)
  const blob = new Blob([item.subtitle.full_text], { type: 'text/plain;charset=utf-8' })
  triggerDownload(blob, `${filename} - 字幕.txt`)
}

function copyAllSubtitles() {
  const allText = results.value
    .filter(r => r.subtitle && r.subtitle.has_subtitle && r.subtitle.full_text)
    .map(r => `=== ${r.title || r.url} ===\n${r.subtitle.full_text}`)
    .join('\n\n')

  if (!allText) return
  navigator.clipboard.writeText(allText).then(() => {
    copyAllSuccess.value = true
    setTimeout(() => { copyAllSuccess.value = false }, 2000)
  }).catch(() => {
    alert('复制失败，请手动选中复制')
  })
}

function downloadAllSubtitles() {
  const allText = results.value
    .filter(r => r.subtitle && r.subtitle.has_subtitle && r.subtitle.full_text)
    .map(r => `=== ${r.title || r.url} ===\n${r.subtitle.full_text}`)
    .join('\n\n')

  if (!allText) return
  const blob = new Blob([allText], { type: 'text/plain;charset=utf-8' })
  triggerDownload(blob, `批量字幕提取 - ${new Date().toLocaleDateString()}.txt`)
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>
