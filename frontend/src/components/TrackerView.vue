<template>
  <div class="min-h-screen bg-bg-main">
    <!-- 顶部 Tab 切换 -->
    <div class="glass border-b border-border sticky top-16 z-40">
      <div class="max-w-5xl mx-auto px-4">
        <div class="flex gap-6">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            @click="activeTab = tab.key"
            class="py-3 px-1 text-sm font-medium border-b-2 transition-colors cursor-pointer"
            :class="activeTab === tab.key
              ? 'border-primary text-primary'
              : 'border-transparent text-text-secondary hover:text-text-primary'"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Tab 内容 -->
    <div class="max-w-5xl mx-auto px-4 py-6">
      <CreatorManager v-if="activeTab === 'creators'" :user="user" @need-login="$emit('need-login')" />
      <ReportList v-else-if="activeTab === 'reports'" :user="user" @need-login="$emit('need-login')" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import CreatorManager from './CreatorManager.vue'
import ReportList from './ReportList.vue'

defineProps({
  user: { type: Object, default: null },
})

defineEmits(['need-login'])

const activeTab = ref('creators')

const tabs = [
  { key: 'creators', label: '我的订阅' },
  { key: 'reports', label: '追踪报告' },
]
</script>
