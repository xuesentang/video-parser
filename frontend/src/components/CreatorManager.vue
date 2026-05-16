<template>
  <div>
    <!-- 添加博主 -->
    <div class="gradient-border p-5 mb-6">
      <h3 class="text-base font-semibold text-text-primary mb-3">添加博主</h3>
      <div class="flex gap-3">
        <input
          v-model="urlInput"
          type="text"
          placeholder="输入B站UP主空间链接 或 YouTube频道链接"
          class="flex-1 px-4 py-2.5 border border-border rounded-xl text-sm bg-bg-card text-text-primary placeholder:text-text-muted input-glow transition-all"
          @keyup.enter="handleAdd"
        />
        <button
          @click="handleAdd"
          :disabled="adding"
          class="px-5 py-2.5 btn-primary text-white text-sm font-medium rounded-xl disabled:opacity-50 transition-all cursor-pointer flex-shrink-0"
        >
          {{ adding ? '添加中...' : '添加订阅' }}
        </button>
      </div>
      <p class="text-xs text-text-muted mt-2">
        支持: space.bilibili.com/xxx 或 youtube.com/channel/xxx
      </p>
    </div>

    <!-- 订阅列表 -->
    <div v-if="loading" class="text-center py-10 text-text-muted">加载中...</div>

    <template v-else>
      <!-- B站 -->
      <div v-if="grouped.bilibili.length" class="mb-6">
        <h4 class="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
          <span class="w-5 h-5 rounded bg-primary text-white text-xs flex items-center justify-center font-bold">B</span>
          哔哩哔哩
        </h4>
        <div class="space-y-3">
          <div
            v-for="c in grouped.bilibili"
            :key="c.sub_id"
            class="gradient-border p-4 flex items-center gap-4"
          >
            <div class="w-11 h-11 rounded-full bg-primary-light text-primary text-sm font-bold flex items-center justify-center flex-shrink-0 border border-primary/20">
              {{ c.name ? c.name.charAt(0) : '?' }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-medium text-text-primary text-sm truncate">{{ c.name }}</div>
              <div class="text-xs text-text-muted truncate mt-0.5">{{ c.description || '暂无简介' }}</div>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <span class="px-2 py-0.5 text-xs rounded-full" :class="c.status === 'active' ? 'bg-success/10 text-success' : 'bg-bg-card text-text-muted'">
                {{ c.status === 'active' ? '追踪中' : '已暂停' }}
              </span>
              <button @click="handleRemove(c.sub_id, c.name)" class="text-text-muted hover:text-error transition-colors cursor-pointer" title="取消订阅">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- YouTube -->
      <div v-if="grouped.youtube.length" class="mb-6">
        <h4 class="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
          <span class="w-5 h-5 rounded bg-error text-white text-xs flex items-center justify-center font-bold">Y</span>
          YouTube
        </h4>
        <div class="space-y-3">
          <div
            v-for="c in grouped.youtube"
            :key="c.sub_id"
            class="gradient-border p-4 flex items-center gap-4"
          >
            <div class="w-11 h-11 rounded-full bg-error/10 text-error text-sm font-bold flex items-center justify-center flex-shrink-0 border border-error/20">
              {{ c.name ? c.name.charAt(0) : '?' }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-medium text-text-primary text-sm truncate">{{ c.name }}</div>
              <div class="text-xs text-text-muted truncate mt-0.5">{{ c.description || '暂无简介' }}</div>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <span class="px-2 py-0.5 text-xs rounded-full" :class="c.status === 'active' ? 'bg-success/10 text-success' : 'bg-bg-card text-text-muted'">
                {{ c.status === 'active' ? '追踪中' : '已暂停' }}
              </span>
              <button @click="handleRemove(c.sub_id, c.name)" class="text-text-muted hover:text-error transition-colors cursor-pointer" title="取消订阅">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!grouped.bilibili.length && !grouped.youtube.length" class="text-center py-16">
        <svg class="w-16 h-16 mx-auto text-text-muted mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"/></svg>
        <p class="text-text-muted text-sm">还没有订阅任何博主</p>
        <p class="text-text-muted text-xs mt-1">在上方输入博主主页链接开始追踪</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { addCreator, listCreators, removeCreator } from '../api/tracker.js'

defineProps({
  user: { type: Object, default: null },
})

const emit = defineEmits(['need-login'])

const urlInput = ref('')
const adding = ref(false)
const loading = ref(false)
const grouped = reactive({ bilibili: [], youtube: [] })

onMounted(() => { loadCreators() })

async function loadCreators() {
  loading.value = true
  try {
    const res = await listCreators()
    if (res.success) {
      grouped.bilibili = res.data.bilibili || []
      grouped.youtube = res.data.youtube || []
    }
  } catch (err) {
    if (err.response?.status === 401) emit('need-login')
  } finally {
    loading.value = false
  }
}

async function handleAdd() {
  const url = urlInput.value.trim()
  if (!url) return
  adding.value = true
  try {
    const res = await addCreator(url)
    if (res.success) {
      urlInput.value = ''
      await loadCreators()
    }
  } catch (err) {
    const detail = err.response?.data?.detail
    alert(typeof detail === 'string' ? detail : '添加失败，请检查链接格式')
  } finally {
    adding.value = false
  }
}

async function handleRemove(subId, name) {
  if (!confirm(`确定取消订阅「${name}」？`)) return
  try {
    await removeCreator(subId)
    await loadCreators()
  } catch (err) {
    alert('取消订阅失败')
  }
}
</script>
