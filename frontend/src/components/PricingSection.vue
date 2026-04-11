<template>
  <section id="pricing" class="py-16 sm:py-20 bg-white" aria-labelledby="pricing-heading">
    <div class="max-w-5xl mx-auto px-4 sm:px-6">
      <div class="text-center mb-12">
        <h2 id="pricing-heading" class="text-2xl sm:text-3xl font-bold text-text-primary mb-3">
          免费视频解析方案
        </h2>
        <p class="text-text-secondary text-base max-w-xl mx-auto">
          注册即获 20 次免费使用额度，满足日常视频解析需求
        </p>
      </div>

      <div class="max-w-md mx-auto">
        <!-- 免费版 -->
        <div class="bg-white rounded-2xl border border-border p-7 flex flex-col">
          <div class="mb-6">
            <h3 class="text-lg font-semibold text-text-primary mb-1">免费版</h3>
            <p class="text-sm text-text-secondary">满足基础解析需求</p>
          </div>
          <div class="mb-6">
            <span class="text-4xl font-bold text-text-primary">¥0</span>
            <span class="text-text-muted text-sm ml-1">/永久</span>
          </div>
          <ul class="space-y-3 mb-8 flex-1">
            <li v-for="item in freePlan" :key="item" class="flex items-start gap-2.5 text-sm text-text-secondary">
              <svg class="w-5 h-5 text-success flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              {{ item }}
            </li>
          </ul>
          <button
            class="w-full h-11 rounded-full border border-border text-sm font-medium text-text-primary transition-colors"
            :class="user ? 'bg-gray-50 cursor-default' : 'hover:bg-gray-50 cursor-pointer'"
            @click="!user && $emit('need-login')"
          >
            {{ user ? '当前方案' : '免费注册' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  user: { type: Object, default: null },
})

const emit = defineEmits(['need-login'])

const freePlan = [
  '20次视频解析额度',
  '支持 1800+ 平台',
  '基础视频信息解析',
  'AI 视频总结（共享额度）',
]
</script>
