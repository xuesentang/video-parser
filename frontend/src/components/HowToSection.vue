<template>
  <section id="how-to-use" class="py-16 sm:py-20" aria-labelledby="howto-heading">
    <div class="max-w-5xl mx-auto px-4 sm:px-6">
      <div class="text-center mb-12">
        <h2 id="howto-heading" class="text-2xl sm:text-3xl font-bold text-text-primary mb-3">
          如何使用 <span class="bg-gradient-to-r from-primary to-purple bg-clip-text text-transparent">VideoParser</span> 解析视频
        </h2>
        <p class="text-text-secondary text-base max-w-xl mx-auto">
          只需 3 步，即可免费解析 YouTube、Bilibili、抖音等 1800+ 平台的视频
        </p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
        <article v-for="step in steps" :key="step.number" class="gradient-border card-hover p-6 text-center relative">
          <div class="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-gradient-to-r from-primary to-purple flex items-center justify-center text-white text-sm font-bold">
            {{ step.number }}
          </div>
          <div class="w-16 h-16 rounded-2xl bg-primary-light border border-primary/20 flex items-center justify-center mx-auto mb-4 text-3xl">
            {{ step.icon }}
          </div>
          <h3 class="text-lg font-semibold text-text-primary mb-2">{{ step.title }}</h3>
          <p class="text-sm text-text-secondary leading-relaxed">{{ step.desc }}</p>
        </article>
      </div>

      <div class="mt-10 text-center">
        <p class="text-sm text-text-muted">
          登录后即可使用全部功能，手机浏览器也能操作。更新于 2026 年 3 月。
        </p>
      </div>
    </div>
  </section>
</template>

<script setup>
const steps = [
  {
    number: 1,
    icon: '🔗',
    title: '复制视频链接',
    desc: '在 YouTube、Bilibili、抖音等平台上找到想要解析的视频，复制视频的分享链接或地址栏 URL。',
  },
  {
    number: 2,
    icon: '🔍',
    title: '粘贴链接并解析',
    desc: '打开 VideoParser，将复制的链接粘贴到输入框中，点击"解析视频"。系统自动识别平台并解析出视频信息和所有可用清晰度。',
  },
  {
    number: 3,
    icon: '💾',
    title: '选择清晰度并下载',
    desc: '从解析结果中选择想要的清晰度（360p 至 4K），点击下载按钮即可保存到本地。还可以使用 AI 总结功能自动生成视频摘要和思维导图。',
  },
]
</script>
