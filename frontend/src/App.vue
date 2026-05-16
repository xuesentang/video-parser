<template>
  <div class="min-h-screen flex flex-col bg-bg-main relative">
    <!-- 动态背景 -->
    <div class="bg-mesh"></div>
    <div class="bg-grid"></div>
    <div class="content-wrapper flex flex-col flex-1">
    <AppHeader
      :user="currentUser"
      :mode="appMode"
      @login="showAuthModal('login')"
      @register="showAuthModal('register')"
      @logout="handleLogout"
      @switch-mode="handleSwitchMode"
    />
    <!-- 博主追踪模式 -->
    <TrackerView v-if="appMode === 'tracker'" :user="currentUser" @need-login="showAuthModal('login')" />
    <!-- 批量字幕模式 -->
    <BatchSubtitleView v-else-if="appMode === 'batch'" :user="currentUser" @need-login="showAuthModal('login')" />
    <!-- 视频解析模式 -->
    <template v-else>
    <main class="flex-1">
      <HeroSection
        @parse="handleParse"
        :loading="loading"
        :compact="!!videoData"
        :showSlogan="!videoData || demoMode"
        :pending-url="pendingParseUrl"
      />
      <!-- 视频信息 + AI 总结：左右双栏同屏布局 -->
      <section v-if="videoData" class="py-4 sm:py-6 bg-bg-main">
        <div class="max-w-7xl mx-auto px-4 sm:px-6">
          <div class="flex flex-col lg:flex-row gap-6">
            <!-- 左栏：视频信息 -->
            <div class="w-full lg:w-2/5 lg:flex-shrink-0">
              <VideoResult
        :video="videoData"
        :summarizing="summarizing"
        @summarize="handleSummarize"
      />
            </div>
            <!-- 右栏：AI 总结 -->
            <div class="w-full lg:w-3/5 min-w-0">
              <VideoSummary
                :videoUrl="currentUrl"
                :videoTitle="videoData.title"
                :user="currentUser"
                :key="summaryKey"
                @loading-change="handleSummarizeLoadingChange"
                @need-login="showAuthModal('login')"
                @need-vip="handleQuotaExceeded"
              />
            </div>
          </div>
        </div>
      </section>
      <FeatureSection />
      <HowToSection />
      <ComparisonSection />
      <PricingSection :user="currentUser" @need-login="showAuthModal('login')" />
      <PlatformSection />
    </main>
    </template>
    <AppFooter />

    <AuthModal
      :visible="authModalVisible"
      :initialMode="authModalMode"
      @close="authModalVisible = false"
      @success="handleAuthSuccess"
    />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, provide, nextTick } from 'vue'
import AppHeader from './components/AppHeader.vue'
import HeroSection from './components/HeroSection.vue'
import VideoResult from './components/VideoResult.vue'
import VideoSummary from './components/VideoSummary.vue'
import FeatureSection from './components/FeatureSection.vue'
import HowToSection from './components/HowToSection.vue'
import ComparisonSection from './components/ComparisonSection.vue'
import PricingSection from './components/PricingSection.vue'
import PlatformSection from './components/PlatformSection.vue'
import AppFooter from './components/AppFooter.vue'
import AuthModal from './components/AuthModal.vue'
import TrackerView from './components/TrackerView.vue'
import BatchSubtitleView from './components/BatchSubtitleView.vue'
import { parseVideo } from './api/video.js'
import { getSavedUser, fetchMe, logout as logoutApi, isLoggedIn } from './api/auth.js'

const demoMode = ref(false)
const appMode = ref('downloader')
let enterCount = 0
let enterTimer = null

function onKeyDown(e) {
  if (e.key === 'Enter' && !e.target.matches('input, textarea, [contenteditable]')) {
    enterCount++
    clearTimeout(enterTimer)
    if (enterCount >= 3) {
      demoMode.value = !demoMode.value
      enterCount = 0
    } else {
      enterTimer = setTimeout(() => { enterCount = 0 }, 800)
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeyDown)
  restoreUser()
})
onBeforeUnmount(() => { document.removeEventListener('keydown', onKeyDown) })

// ===== 用户状态管理 =====
const currentUser = ref(null)
const authModalVisible = ref(false)
const authModalMode = ref('login')

function showAuthModal(mode = 'login') {
  authModalMode.value = mode
  authModalVisible.value = true
}

function handleAuthSuccess(user) {
  currentUser.value = user
}

function handleLogout() {
  logoutApi()
  currentUser.value = null
}

async function restoreUser() {
  if (!isLoggedIn()) return
  const saved = getSavedUser()
  if (saved) currentUser.value = saved
  try {
    currentUser.value = await fetchMe()
  } catch {
    handleLogout()
  }
}

// ===== 模式切换 =====
function handleSwitchMode(mode) {
  appMode.value = mode
}

// ===== 从博主追踪报告传入链接进行解析 =====
const pendingParseUrl = ref('')

async function setParseUrl(url) {
  appMode.value = 'downloader'
  // 先重置确保 watch 能触发（即使连续点击同一个链接）
  pendingParseUrl.value = ''
  // 等待 DOM 更新后再赋值，确保 HeroSection 能收到变化
  await nextTick()
  pendingParseUrl.value = url
}

provide('setParseUrl', setParseUrl)

// ===== 额度用完处理 =====
function handleQuotaExceeded() {
  alert('使用额度已用完（共20次），如需更多请联系管理员')
}

// ===== 视频功能 =====
const loading = ref(false)
const videoData = ref(null)
const currentUrl = ref('')
const summaryKey = ref(0)
const summarizing = ref(false)

function handleSummarize() {
  summaryKey.value++
}

function handleSummarizeLoadingChange(isLoading) {
  summarizing.value = isLoading
}

async function handleParse(url) {
  // 未登录时弹出登录框
  if (!currentUser.value) {
    showAuthModal('login')
    return
  }

  loading.value = true
  videoData.value = null
  currentUrl.value = url
  try {
    const res = await parseVideo(url)
    if (res.success) {
      videoData.value = res.data
      summaryKey.value++
      // 更新用户剩余次数
      if (res.remaining !== undefined && currentUser.value) {
        currentUser.value.remaining = res.remaining
      }
    } else {
      alert('解析失败：' + (res.error || '未知错误'))
    }
  } catch (err) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'object' && detail.need_vip) {
      handleQuotaExceeded()
      return
    }
    const msg = detail?.error || detail || err.message
    alert('解析失败：' + msg)
  } finally {
    loading.value = false
  }
}


</script>
