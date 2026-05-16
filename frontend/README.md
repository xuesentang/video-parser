# VideoParser 前端

VideoParser 前端项目 —— 基于 Vue 3 + Vite + Tailwind CSS 构建的赛博霓虹风格视频解析平台。

## 技术栈

| 技术 | 版本 | 说明 |
|------|------|------|
| Vue | 3.5.25 | 渐进式 JavaScript 框架，使用 Composition API |
| Vite | 7.3.1 | 下一代前端构建工具 |
| Tailwind CSS | 4.2.1 | 原子化 CSS 框架 |
| marked | 17.0.3 | Markdown 解析器 |
| markmap-lib / markmap-view | 0.18.12 | 思维导图生成与渲染 |
| axios | 1.13.5 | HTTP 客户端 |

## 项目结构

```
frontend/
├── index.html              # 入口 HTML，包含完整的 SEO 结构化数据
├── package.json            # 依赖与脚本配置
├── vite.config.js          # Vite 构建配置
├── src/
│   ├── main.js             # 应用入口
│   ├── App.vue             # 根组件，全局状态管理与路由模式切换
│   ├── style.css           # 全局样式：赛博霓虹主题变量、动画、工具类
│   ├── api/                # API 接口层
│   │   ├── auth.js         # 用户认证（登录/注册/登出/获取用户信息）
│   │   ├── video.js        # 视频解析与下载
│   │   ├── summarize.js    # AI 视频总结与问答（SSE 流式）
│   │   ├── batch.js        # 批量字幕提取（SSE 流式）
│   │   ├── tracker.js      # 博主追踪（订阅/报告/进度轮询）
│   │   └── payment.js      # 支付相关
│   └── components/         # Vue 组件
│       ├── AppHeader.vue       # 顶部导航栏：Logo、模式切换、用户状态
│       ├── AppFooter.vue       # 页脚
│       ├── AuthModal.vue       # 登录/注册弹窗
│       ├── HeroSection.vue     # 首屏：视频链接输入框
│       ├── VideoResult.vue     # 视频解析结果：缩略图、格式选择、下载
│       ├── VideoSummary.vue    # AI 总结：摘要/字幕/思维导图/问答
│       ├── FeatureSection.vue  # 功能特性展示
│       ├── HowToSection.vue    # 使用步骤
│       ├── ComparisonSection.vue # 竞品对比
│       ├── PricingSection.vue  # 定价方案
│       ├── PlatformSection.vue # 支持平台展示
│       ├── TrackerView.vue     # 博主追踪页面框架（Tab 切换）
│       ├── CreatorManager.vue  # 博主订阅管理
│       ├── ReportList.vue      # 追踪报告列表与详情
│       ├── TrackerSettings.vue # 追踪设置
│       └── BatchSubtitleView.vue # 批量字幕提取页面
```

## 三大核心功能模块

### 1. 视频解析（默认模式）
- 粘贴视频链接 → 解析出视频信息和可用格式
- 支持 1800+ 平台（YouTube、Bilibili、抖音、TikTok 等）
- 多种清晰度选择（360p 至 4K）
- AI 视频总结：自动生成摘要、思维导图、字幕文本
- AI 问答：基于视频内容进行多轮对话

### 2. 博主追踪（`appMode === 'tracker'`）
- 订阅 B站/YouTube 博主主页
- 自动生成追踪报告，汇总最新视频动态
- 报告支持 Markdown 渲染，可一键解析视频

### 3. 批量字幕提取（`appMode === 'batch'`）
- 一次性粘贴多个视频链接（最多 20 个）
- 批量提取字幕，支持分段/纯文本两种视图
- 支持复制/下载全部字幕（SRT/VTT/TXT）

## 主题设计

采用**赛博霓虹（Cyber Neon）**风格：
- **主色调**：霓虹青 `#00d4ff` + 霓虹紫 `#a855f7`
- **背景**：深色 `#0a0a0f`，配合动态光球和网格背景
- **卡片**：渐变边框（`gradient-border`）+ 玻璃拟态（`glass`）
- **按钮**：霓虹渐变（`btn-primary`）+ 悬停发光
- **输入框**：深色背景 + 聚焦辉光（`input-glow`）

## 开发脚本

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview
```

## 构建产物

构建输出至 `dist/` 目录，可直接部署到静态服务器：

```bash
cd dist
python -m http.server 8080
```

## 关键实现细节

### 模式切换
应用通过 `appMode` 状态在三个界面间切换，无 Vue Router：
- `downloader` → 视频解析首页
- `tracker` → 博主追踪
- `batch` → 批量字幕提取

### SSE 流式处理
AI 总结和批量字幕使用 Server-Sent Events：
- `summarize.js`：接收 `subtitle` / `summary` / `mindmap` / `quota` / `done` / `error` 事件
- `batch.js`：接收 `progress` / `result` / `error` / `done` 事件

### 思维导图
使用 `markmap-lib` + `markmap-view` 将 Markdown 转为 SVG 思维导图：
- 支持全屏展示
- 支持导出 PNG（4K 超清）和 SVG
- 文字颜色适配深色主题

### 报告详情弹窗
追踪报告使用 Markdown 渲染，内嵌视频链接旁附带"解析"按钮，点击可直接跳转回视频解析模式并自动填入链接。
