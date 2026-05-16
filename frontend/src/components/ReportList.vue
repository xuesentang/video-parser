<template>
  <div>
    <!-- 操作栏 -->
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-base font-semibold text-text-primary">追踪报告</h3>
      <button
        @click="handleGenerate"
        :disabled="generating"
        class="px-4 py-2 btn-primary text-white text-sm font-medium rounded-xl disabled:opacity-50 transition-all cursor-pointer"
      >
        {{ generating ? '生成中...' : '生成报告' }}
      </button>
    </div>

    <!-- 生成进度 -->
    <div v-if="generating && progress" class="gradient-border p-5 mb-6">
      <div class="flex items-center gap-3 mb-3">
        <svg class="w-5 h-5 text-primary animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        <span class="text-sm font-medium text-primary">正在生成报告...</span>
      </div>
      <div class="w-full bg-bg-card rounded-full h-2 mb-2">
        <div
          class="bg-gradient-to-r from-primary to-purple h-2 rounded-full transition-all duration-300"
          :style="{ width: progressPercent + '%' }"
        ></div>
      </div>
      <div class="text-xs text-text-secondary">
        正在检查：{{ progress.current_creator || '准备中...' }}
        （{{ progress.progress_current }} / {{ progress.progress_total }}）
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="text-center py-10 text-text-muted">加载中...</div>

    <!-- 报告列表 -->
    <template v-else>
      <div v-if="reports.length" class="space-y-4">
        <div
          v-for="r in reports"
          :key="r.id"
          class="gradient-border card-hover p-5"
        >
          <div class="flex items-start justify-between">
            <div class="cursor-pointer flex-1 min-w-0" @click="openReport(r.id)">
              <div class="font-medium text-text-primary text-sm">{{ formatTitle(r) }}</div>
              <div class="text-xs text-text-muted mt-1">
                {{ formatDate(r.created_at) }}
                <span v-if="r.status === 'completed'" class="ml-2">{{ r.video_count || 0 }} 个视频</span>
                <span v-else-if="r.status === 'no_videos'" class="ml-2 text-warning">无新视频</span>
                <span v-else-if="r.status === 'no_subscription'" class="ml-2 text-text-muted">无订阅</span>
                <span v-else-if="r.status === 'failed'" class="ml-2 text-error">生成失败</span>
                <span v-else-if="r.status === 'generating'" class="ml-2 text-primary">生成中...</span>
              </div>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0 ml-3">
              <button
                @click.stop="openReport(r.id)"
                class="p-1.5 text-text-muted hover:text-primary rounded-lg hover:bg-primary-light transition-colors cursor-pointer"
                title="查看详情"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
              </button>
              <button
                @click.stop="confirmDelete(r)"
                class="p-1.5 text-text-muted hover:text-error rounded-lg hover:bg-error/10 transition-colors cursor-pointer"
                title="删除报告"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="text-center py-16">
        <svg class="w-16 h-16 mx-auto text-text-muted mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
        <p class="text-text-muted text-sm">暂无追踪报告</p>
        <p class="text-text-muted text-xs mt-1">点击上方"生成报告"按钮手动创建</p>
      </div>
    </template>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="deleteTarget = null">
      <div class="gradient-border max-w-sm w-full mx-4 p-6 shadow-2xl">
        <div class="flex items-center gap-3 mb-4">
          <div class="w-10 h-10 rounded-full bg-error/10 flex items-center justify-center flex-shrink-0 border border-error/20">
            <svg class="w-5 h-5 text-error" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>
          </div>
          <div>
            <h4 class="font-semibold text-text-primary text-sm">确认删除</h4>
            <p class="text-xs text-text-muted mt-1">删除后无法恢复，确定要删除这份报告吗？</p>
          </div>
        </div>
        <div class="flex gap-3 justify-end">
          <button
            @click="deleteTarget = null"
            class="px-4 py-2 text-sm text-text-secondary bg-bg-card rounded-xl hover:bg-bg-section transition-colors cursor-pointer"
          >取消</button>
          <button
            @click="handleDelete"
            :disabled="deleting"
            class="px-4 py-2 text-sm text-white bg-error rounded-xl hover:bg-error/80 disabled:opacity-50 transition-colors cursor-pointer"
          >{{ deleting ? '删除中...' : '确认删除' }}</button>
        </div>
      </div>
    </div>

    <!-- 报告详情弹窗 -->
    <div v-if="detailVisible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="detailVisible = false">
      <div class="gradient-border max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col shadow-2xl">
        <div class="flex items-center justify-between p-5 border-b border-border">
          <h3 class="font-semibold text-text-primary">报告详情</h3>
          <button @click="detailVisible = false" class="text-text-muted hover:text-text-primary cursor-pointer">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="p-5 overflow-y-auto flex-1">
          <div v-if="detailLoading" class="text-center py-8 text-text-muted">加载中...</div>
          <template v-else-if="detail">
            <!-- 无视频提示 -->
            <div v-if="detail.display_message" class="text-center py-8">
              <svg class="w-12 h-12 mx-auto text-warning mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 12H4"/></svg>
              <p class="text-text-secondary text-sm">{{ detail.display_message }}</p>
            </div>
            <!-- 正常报告 -->
            <template v-else>
              <div class="text-sm text-text-muted mb-3">{{ formatDate(detail.created_at) }} · {{ detail.video_count || 0 }} 个视频</div>
              <div v-if="detail.content_markdown" class="prose prose-sm max-w-none report-content" v-html="renderMarkdown(detail.content_markdown)" @click="handleContentClick"></div>
              <div v-else class="text-text-muted text-sm">报告内容为空</div>
            </template>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, inject } from 'vue'
import { listReports, getReport, generateReport, getReportProgress, deleteReport } from '../api/tracker.js'
import { marked } from 'marked'

defineProps({
  user: { type: Object, default: null },
})

const emit = defineEmits(['need-login'])

const setParseUrl = inject('setParseUrl', null)

const loading = ref(false)
const generating = ref(false)
const reports = ref([])
const progress = ref(null)
const deleteTarget = ref(null)
const deleting = ref(false)
let pollTimer = null

const progressPercent = computed(() => {
  if (!progress.value || !progress.value.progress_total) return 0
  return Math.round((progress.value.progress_current / progress.value.progress_total) * 100)
})

onBeforeUnmount(() => {
  stopPolling()
})

async function loadReports() {
  loading.value = true
  try {
    const res = await listReports({ limit: 50 })
    if (res.success) reports.value = res.data.filter(r => r.status !== 'generating')
  } catch (err) {
    if (err.response?.status === 401) emit('need-login')
  } finally {
    loading.value = false
  }
}

loadReports()

async function handleGenerate() {
  generating.value = true
  progress.value = null
  try {
    const res = await generateReport(72)
    if (res.success) {
      startPolling(res.data.report_id)
    }
  } catch (err) {
    alert('生成报告失败: ' + (err.response?.data?.detail || err.message))
    generating.value = false
  }
}

function startPolling(reportId) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await getReportProgress(reportId)
      if (res.success) {
        progress.value = res.data
        const status = res.data.status
        if (status === 'completed' || status === 'failed' || status === 'no_videos' || status === 'no_subscription') {
          stopPolling()
          generating.value = false
          progress.value = null
          await loadReports()

          if (status === 'no_videos') {
            alert('过去72小时内您追踪的博主都没有发布新视频。')
          } else if (status === 'no_subscription') {
            alert('您还没有订阅任何博主，请先添加博主。')
          } else if (status === 'failed') {
            alert('报告生成失败，请稍后重试。')
          }
        }
      }
    } catch {
      stopPolling()
      generating.value = false
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function confirmDelete(report) {
  deleteTarget.value = report
}

async function handleDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    const res = await deleteReport(deleteTarget.value.id)
    if (res.success) {
      reports.value = reports.value.filter(r => r.id !== deleteTarget.value.id)
      deleteTarget.value = null
    }
  } catch (err) {
    alert('删除失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    deleting.value = false
  }
}

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

async function openReport(id) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const res = await getReport(id)
    if (res.success) detail.value = res.data
  } catch {
    alert('加载报告失败')
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

function formatTitle(r) {
  if (r.title) return r.title
  const d = new Date(r.created_at)
  return `追踪报告 - ${d.getFullYear()}/${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')}`
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function isVideoUrl(url) {
  return /(?:bilibili\.com|youtube\.com|youtu\.be|tiktok\.com|douyin\.com|x\.com|twitter\.com|instagram\.com)/i.test(url)
}

// 使用 marked.use() 注册自定义 renderer（只注册一次，避免重复）
marked.use({
  renderer: {
    link({ href, title, tokens }) {
      const rawText = this.parser.parseInline(tokens)
      const linkHtml = `<a href="${href}"${title ? ` title="${title}"` : ''}>${rawText}</a>`
      if (isVideoUrl(href)) {
        const btn = `<button class="parse-video-btn ml-1.5 px-2 py-0.5 text-xs btn-primary rounded hover:opacity-90 transition-opacity cursor-pointer" data-parse-url="${href}">解析</button>`
        return `<span class="inline-flex items-center">${linkHtml}${btn}</span>`
      }
      return linkHtml
    }
  }
})

function renderMarkdown(text) {
  try {
    return marked.parse(text || '')
  } catch { return text }
}

function handleContentClick(e) {
  const btn = e.target.closest('.parse-video-btn')
  if (btn && setParseUrl) {
    const url = btn.getAttribute('data-parse-url')
    if (url) {
      detailVisible.value = false
      setParseUrl(url)
    }
  }
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 报告详情 Markdown 深色主题适配 */
.report-content :deep(h1),
.report-content :deep(h2),
.report-content :deep(h3),
.report-content :deep(h4),
.report-content :deep(h5),
.report-content :deep(h6) {
  color: var(--color-text-primary);
}
.report-content :deep(p) {
  color: var(--color-text-primary);
  line-height: 1.8;
}
.report-content :deep(li) {
  color: var(--color-text-primary);
  line-height: 1.8;
}
.report-content :deep(strong) {
  color: var(--color-text-primary);
}
.report-content :deep(a) {
  color: var(--color-primary);
}
.report-content :deep(blockquote) {
  color: var(--color-text-secondary);
  border-left-color: var(--color-primary);
  background: var(--color-bg-card);
}
.report-content :deep(hr) {
  border-color: var(--color-border);
}
.report-content :deep(code) {
  color: var(--color-primary-dark);
  background: var(--color-bg-card);
}
.report-content :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
}
.report-content :deep(table th),
.report-content :deep(table td) {
  color: var(--color-text-primary);
  border-color: var(--color-border);
}
</style>
