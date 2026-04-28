# 万能视频解析器 - 项目解读文档

> 本文档旨在帮助第一次接触此项目的开发者快速理解项目的整体架构、核心功能和技术实现，便于后续开发和维护。

---

## 一、项目概览

### 1.1 项目名称

**万能视频解析器**（Free Video Downloader）

### 1.2 一句话描述

这是一个基于 yt-dlp 的在线视频解析工具，支持从 1800+ 视频平台解析视频，并提供 AI 智能总结、字幕提取、思维导图生成等高级功能，采用 FastAPI + Vue 3 技术栈实现前后端分离架构。

### 1.3 核心价值

| 痛点 | 解决方案 |
|------|----------|
| 视频平台多、下载困难 | 基于 yt-dlp 支持 1800+ 平台 |
| 视频水印难以去除 | 抖音专用无水印解析模块 |
| 视频内容难以快速理解 | AI 视频总结和思维导图生成 |
| 无字幕视频难以总结 | B站/抖音字幕提取 + AI 问答 |
| 版权限制无法直接下载 | 直链解析和服务端代理双模式 |

### 1.4 技术栈总览

| 层级 | 技术选型 | 作用 |
|------|----------|------|
| **后端框架** | FastAPI | 异步 Web API 服务 |
| **视频解析核心** | yt-dlp | 多平台视频解析 |
| **AI 大模型** | DeepSeek | 视频总结、思维导图、问答 |
| **数据库** | SQLite | 用户数据、订单存储 |
| **前端框架** | Vue 3 | 用户交互界面 |
| **构建工具** | Vite | 前端开发服务器和构建 |
| **CSS 框架** | Tailwind CSS | 响应式样式 |
| **支付系统** | Stripe | VIP 会员支付 |
| **对象存储** | 腾讯云 COS | 视频文件存储（预留） |

---

## 二、核心业务流程

### 2.1 视频解析流程

```
用户输入视频链接
       ↓
  ┌─────────────────┐
  │ URL 平台识别     │
  └────────┬────────┘
           ↓
  ┌─────────────────┐
  │ 抖音? → DouyinParser │
  │ B站? → BilibiliParser │
  │ 其他? → VideoDownloader (yt-dlp) │
  └────────┬────────┘
           ↓
  ┌─────────────────┐
  │ 返回视频信息     │
  │ • 标题/缩略图   │
  │ • 时长/上传者   │
  │ • 可用格式列表  │
  └─────────────────┘
           ↓
  ┌─────────────────┐
  │ 用户选择格式    │
  └────────┬────────┘
           ↓
  ┌─────────────────┐
  │ 两种下载模式     │
  ├─────────────────┤
  │ 直链模式: 返回直链 │
  │ 代理模式: 服务端下载 │
  └─────────────────┘
```

### 2.2 AI 视频总结流程

```
用户请求 AI 总结
       ↓
  ┌─────────────────┐
  │ 额度检查        │
  │ VIP 无限 / 普通 20 次 │
  └────────┬────────┘
           ↓
  ┌─────────────────┐
  │ 字幕提取        │
  ├─────────────────┤
  │ 抖音: API → 字幕数据 │
  │ B站: dm/view API │
  │ 其他: yt-dlp 提取 │
  │ 无字幕: 视频描述降级 │
  └────────┬────────┘
           ↓
  ┌─────────────────┐
  │ SSE 流式推送    │
  │ 1. subtitle 事件 │
  │ 2. summary 事件  │
  │ 3. mindmap 事件  │
  │ 4. quota 事件    │
  │ 5. done 事件     │
  └─────────────────┘
```

### 2.3 用户权限体系

```
普通用户
├── 视频解析/下载: 每日 20 次额度
├── AI 总结: 统一使用 usage_count 额度
└── VIP 会员
    ├── 无限次解析/下载
    ├── 无限次 AI 总结
    └── 专属优惠价格
```

---

## 三、项目目录结构

### 3.1 顶级目录

```
free-video-downloader/
├── backend/                    # FastAPI 后端
├── frontend/                   # Vue 3 前端
├── docs/                       # 项目文档
├── README.md                   # 项目说明
├── LICENSE                    # MIT 许可证
└── problems solve.md           # 问题排查文档
```

### 3.2 后端目录详解

```
backend/
├── main.py                    # FastAPI 应用入口 + 核心路由
├── downloader.py              # yt-dlp 封装层（通用视频解析）
├── douyin.py                  # 抖音专用解析模块
├── bilibili.py                # B站专用解析模块
├── summarizer.py              # AI 总结模块（字幕提取 + DeepSeek）
├── api_summarize.py           # AI 总结 API 路由
├── api_auth.py                # 用户认证 API
├── api_payment.py             # 支付 API
├── auth.py                    # 认证中间件（JWT）
├── database.py                # 数据库操作（SQLite）
├── requirements.txt           # Python 依赖
└── .env.example               # 环境变量模板
```

### 3.3 前端目录详解

```
frontend/
├── src/
│   ├── App.vue                # 根组件
│   ├── main.js                # 应用入口
│   ├── style.css              # 全局样式
│   ├── components/            # Vue 组件
│   │   ├── AppHeader.vue      # 页面头部
│   │   ├── AppFooter.vue      # 页面底部
│   │   ├── HeroSection.vue    # 首屏区域
│   │   ├── VideoResult.vue    # 视频结果展示
│   │   ├── VideoSummary.vue   # AI 总结展示
│   │   ├── FeatureSection.vue # 功能特性
│   │   ├── PricingSection.vue # 定价页面
│   │   ├── PlatformSection.vue # 支持平台
│   │   ├── HowToSection.vue   # 使用教程
│   │   ├── ComparisonSection.vue # 对比区域
│   │   └── AuthModal.vue      # 登录注册弹窗
│   └── api/                   # API 封装
│       ├── video.js          # 视频解析接口
│       ├── summarize.js       # AI 总结接口
│       ├── auth.js           # 用户认证接口
│       └── payment.js        # 支付接口
├── public/                    # 静态资源
├── index.html                 # HTML 模板
├── package.json               # 前端依赖
└── vite.config.js            # Vite 配置
```

### 3.4 文档目录

```
docs/
├── 需求分析.md                 # 需求规格说明
├── 方案设计.md                 # 技术方案设计
└── 保姆级本地运行指南.md       # 本地开发指南
```

---

## 四、后端核心模块详解

### 4.1 main.py - 应用入口

```python
# 位置: backend/main.py
```

**职责**：
- FastAPI 应用初始化和配置
- CORS 中间件配置
- 核心路由挂载
- 应用生命周期管理（启动/关闭）
- 下载临时文件清理

**核心路由**：
| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/parse` | POST | 解析视频信息 |
| `/api/download` | POST | 服务端代理下载 |
| `/api/direct-url` | POST | 获取直链 |
| `/api/proxy/thumbnail` | GET | 缩略图代理 |

**平台分发逻辑**：
```python
if is_douyin_url(url):
    douyin_parser.parse(url)      # 抖音专用解析
elif is_bilibili_url(url):
    bilibili_parser.parse(url)    # B站专用解析
else:
    downloader.parse_video(url)   # yt-dlp 通用解析
```

### 4.2 VideoDownloader - yt-dlp 封装

```python
# 位置: backend/downloader.py
```

**职责**：封装 yt-dlp，提供通用视频解析、下载、直链获取能力。

**核心功能**：

| 方法 | 说明 |
|------|------|
| `parse_video(url)` | 解析视频信息，返回元数据和格式列表 |
| `download_video(url, format_id)` | 下载视频到服务器临时目录 |
| `get_direct_url(url, format_id)` | 获取视频直链 |

**支持的格式信息**：
```python
{
    "format_id": "bestvideo+bestaudio/best",
    "ext": "mp4",
    "resolution": "1920x1080",
    "height": 1080,
    "filesize": 104857600,
    "vcodec": "h264",
    "acodec": "aac",
    "has_audio": True,
    "label": "1080p MP4 (最佳画质)"
}
```

**技术细节**：
- 自动检测 ffmpeg 路径，支持视频+音频合并
- 模拟浏览器请求头，降低反爬拦截概率
- 格式去重，按分辨率排序

### 4.3 DouyinParser - 抖音专用解析

```python
# 位置: backend/douyin.py
```

**职责**：针对抖音平台的专用解析器，实现无水印视频获取。

**核心流程**：
```
分享链接 → 重定向解析 → 提取 video_id → API 获取元数据 → 无水印播放地址
```

**核心方法**：

| 方法 | 说明 |
|------|------|
| `parse(url)` | 解析抖音视频信息 |
| `download(url, mode)` | 下载抖音视频/音频 |

**技术亮点**：
- 无需 Cookie，基于公开 API
- 自动解决 WAF 反爬验证（`__jswci__` Cookie）
- 支持从分享页面 HTML 解析（降级方案）
- 无水印播放地址：`playwm` → `play`

**URL 识别**：
```python
douyin_domains = [
    "douyin.com", "iesdouyin.com", "v.douyin.com",
    "www.douyin.com", "m.douyin.com",
]
```

### 4.4 BilibiliParser - B站专用解析

```python
# 位置: backend/bilibili.py
```

**职责**：针对 B站的专用解析器，基于公开 API。

**核心流程**：
```
短链接/bv号 → view API 获取元数据 → playurl API 获取视频流 → DASH 格式组装
```

**核心方法**：

| 方法 | 说明 |
|------|------|
| `parse(url)` | 解析 B站视频信息 |
| `_fetch_view_info()` | 通过 view API 获取视频信息 |
| `_fetch_play_url()` | 通过 playurl API 获取视频流地址 |
| `_extract_formats()` | 提取并整理可用格式 |

**技术亮点**：
- 支持 b23.tv 短链接解析
- 支持 BV 号和 AV 号两种识别方式
- DASH 格式支持（视频+音频分离）
- 获取失败时自动降级到 yt-dlp

### 4.5 summarizer.py - AI 总结模块

```python
# 位置: backend/summarizer.py
```

**职责**：AI 视频总结、字幕提取、思维导图生成。

#### 4.5.1 SubtitleExtractor - 字幕提取

**字幕提取优先级**：
```
抖音: API字幕 → 视频描述降级
B站: dm/view API字幕 → yt-dlp 字幕
其他: yt-dlp 字幕 → 自动字幕
```

**字幕类型**：
| 类型 | 说明 |
|------|------|
| `manual` | 人工添加的字幕 |
| `auto` | AI 自动生成的字幕 |
| `desc` | 视频描述降级（无字幕时使用） |
| `none` | 无可用字幕 |

**返回格式**：
```python
{
    "has_subtitle": True,
    "language": "zh",
    "subtitle_type": "auto",
    "segments": [
        {"start": 0.0, "end": 5.5, "text": "字幕文本"},
        ...
    ],
    "full_text": "完整字幕文本..."
}
```

#### 4.5.2 VideoSummarizer - DeepSeek 封装

**三个核心功能**：

| 方法 | 说明 | 返回方式 |
|------|------|----------|
| `summarize_stream()` | 视频总结 | SSE 流式 |
| `generate_mindmap()` | 思维导图 | 一次性返回 |
| `chat_stream()` | AI 问答 | SSE 流式 |

**Prompt 设计**：
- 总结：视频概述 → 内容大纲 → 核心知识要点 → 总结
- 思维导图：Markdown 层级结构，# 一级 / ## 二级 / ### 三级
- 问答：基于字幕内容诚实回答

### 4.6 database.py - 数据库操作

```python
# 位置: backend/database.py
```

**职责**：SQLite 数据库操作，用户和订单管理。

**数据库表**：

| 表名 | 说明 |
|------|------|
| `users` | 用户表（邮箱、密码、VIP状态、额度） |
| `orders` | 订单表（订单号、金额、支付状态、VIP时效） |

**核心函数**：

| 函数 | 说明 |
|------|------|
| `init_db()` | 初始化数据库表结构 |
| `create_user()` | 创建用户（VIP邮箱自动获得VIP） |
| `get_user_by_email()` | 根据邮箱查询用户 |
| `check_and_increment_usage()` | 检查并增加使用次数（解析/下载） |
| `check_and_increment_summary()` | 检查并增加使用次数（AI总结） |
| `complete_order()` | 支付完成后激活VIP |

**VIP 用户硬编码**：
```python
VIP_EMAIL = "18300658398@163.com"  # 硬编码的 VIP 邮箱
NORMAL_USER_USAGE_LIMIT = 20       # 普通用户额度
```

### 4.7 auth.py - 认证中间件

```python
# 位置: backend/auth.py
```

**职责**：JWT 用户认证中间件。

**Token 包含信息**：
```python
{
    "sub": str(user_id),
    "email": email,
    "is_vip": is_vip
}
```

**验证流程**：
```
请求 Header → Authorization: Bearer <token> → 解码验证 → 返回用户信息
```

### 4.8 API 路由模块

#### 4.8.1 api_summarize.py - AI 总结 API

```python
# 位置: backend/api_summarize.py
```

**SSE 事件类型**：

| 事件 | 说明 | 数据内容 |
|------|------|----------|
| `subtitle` | 字幕数据 | `{has_subtitle, language, segments, full_text}` |
| `summary` | 总结片段 | token 字符串 |
| `mindmap` | 思维导图 | `{markdown: "..."}` |
| `quota` | 额度信息 | `{remaining, limit}` |
| `error` | 错误信息 | `{message, need_vip}` |
| `done` | 完成 | `[DONE]` |

#### 4.8.2 api_auth.py - 用户认证 API

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/me` | GET | 获取当前用户信息 |

#### 4.8.3 api_payment.py - 支付 API

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/payment/create-session` | POST | 创建 Stripe 支付会话 |
| `/api/payment/webhook` | POST | Stripe 回调处理 |

---

## 五、前端核心模块详解

### 5.1 页面结构

| 组件 | 说明 |
|------|------|
| `HeroSection.vue` | 首屏区域，包含 URL 输入框 |
| `VideoResult.vue` | 视频解析结果展示和格式选择 |
| `VideoSummary.vue` | AI 总结结果（字幕/总结/思维导图/问答） |
| `FeatureSection.vue` | 功能特性展示 |
| `PricingSection.vue` | VIP 定价页面 |
| `PlatformSection.vue` | 支持的平台列表 |
| `HowToSection.vue` | 使用教程 |
| `ComparisonSection.vue` | 与竞品对比 |
| `AuthModal.vue` | 登录注册弹窗 |

### 5.2 核心交互流程

```
首页输入视频链接
       ↓
  VideoResult 展示视频信息
       ↓
  用户选择下载方式（直链/代理）
       ↓
  发起解析请求，扣减额度
       ↓
  SSE 连接接收 AI 总结流
       ↓
  展示字幕/总结/思维导图
```

### 5.3 API 封装

```javascript
// video.js
export const parseVideo = (url) => api.post('/api/parse', { url })
export const downloadVideo = (url, format_id) => api.post('/api/download', { url, format_id })
export const getDirectUrl = (url, format_id) => api.post('/api/direct-url', { url, format_id })

// summarize.js
export const summarizeVideo = (url, language) => EventSource.post('/api/summarize', { url, language })
export const chatWithVideo = (url, question, subtitle_text) => EventSource.post('/api/chat', { url, question, subtitle_text })

// auth.js
export const register = (email, password) => api.post('/api/auth/register', { email, password })
export const login = (email, password) => api.post('/api/auth/login', { email, password })
export const getCurrentUser = () => api.get('/api/auth/me')
```

---

## 六、技术亮点

### 6.1 多平台视频解析策略

```
┌─────────────────────────────────────────────────────────────┐
│                      统一入口                                  │
│                    parse_video(url)                           │
└─────────────────────────┬─────────────────────────────────────┘
                          ↓
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
   抖音 URL?          B站 URL?          其他平台?
        ↓                 ↓                 ↓
  DouyinParser      BilibiliParser    VideoDownloader
  (专用解析)         (专用解析)         (yt-dlp)
        ↓                 ↓                 ↓
  无水印 API         playurl API        yt-dlp
        ↓                 ↓                 ↓
  返回统一格式 ←────────────────────────────┘
```

**优势**：
- 抖音/B站使用专用解析，绕过登录限制
- 其他平台统一使用 yt-dlp，代码复用
- 返回数据格式统一，便于前端处理

### 6.2 字幕提取多级降级

```
一级: 平台官方字幕（最准确）
  ↓ 失败
二级: 自动字幕（AI生成，可能有误差）
  ↓ 失败
三级: 视频描述降级（无字幕时的保底方案）
  ↓ 失败
四级: 返回 has_subtitle=false
```

### 6.3 SSE 流式输出

**AI 总结 SSE 流程**：
```
1. subtitle 事件 → 推送字幕数据（前端展示字幕列表）
2. summary 事件 → 流式推送总结 tokens（前端逐字显示）
3. mindmap 事件 → 推送思维导图 Markdown（前端渲染）
4. quota 事件 → 推送剩余额度（前端更新 UI）
5. done 事件 → 结束标记
```

**优势**：
- 用户无需等待完整结果
- 实时看到生成进度
- 提升用户体验

### 6.4 视频下载双模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **直链模式** | 返回视频直链，浏览器直接下载 | 绕过地区限制、直链可用 |
| **代理模式** | 服务端下载后返回文件 | 直链失效、需要合并格式 |

---

## 七、部署架构

### 7.1 开发环境

```
本地机器
├── 后端: python main.py (localhost:8000)
└── 前端: npm run dev (localhost:5173)
```

### 7.2 架构图

```
                    ┌─────────────┐
                    │   用户浏览器  │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │   Nginx     │
                    │ (反向代理)   │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         ↓                                   ↓
  ┌──────────────┐                  ┌──────────────┐
  │   前端静态文件 │                  │  FastAPI 后端 │
  │   Vue 3      │                  │   (8000)    │
  └──────────────┘                  └──────┬──────┘
                                           │
                         ┌─────────────────┼─────────────────┐
                         ↓                 ↓                 ↓
                  ┌──────────┐      ┌──────────┐      ┌──────────┐
                  │  SQLite  │      │ DeepSeek │      │  抖音/B站  │
                  │  数据库   │      │   API    │      │   API    │
                  └──────────┘      └──────────┘      └──────────┘
```

### 7.3 环境变量配置

```env
# AI 大模型配置
DEEPSEEK_API_KEY=your_deepseek_api_key

# 用户认证
JWT_SECRET=your_jwt_secret_key

# 支付配置（可选）
STRIPE_API_KEY=your_stripe_api_key
STRIPE_WEBHOOK_SECRET=your_webhook_secret

# 数据库（可选，默认 SQLite）
DATABASE_URL=sqlite:///./data.db
```

---

## 八、数据模型设计

### 8.1 用户表 (users)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| email | TEXT | 邮箱，唯一 |
| password_hash | TEXT | 密码哈希 |
| is_vip | INTEGER | 是否VIP (0/1) |
| vip_expire_at | TEXT | VIP到期时间 |
| usage_count | INTEGER | 已使用次数 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### 8.2 订单表 (orders)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| order_no | TEXT | 订单号，唯一 |
| user_id | INTEGER | 用户ID，外键 |
| amount | INTEGER | 金额（分） |
| currency | TEXT | 货币（默认cny） |
| status | TEXT | 状态（pending/paid） |
| plan_type | TEXT | 套餐类型（monthly/yearly） |
| stripe_session_id | TEXT | Stripe会话ID |
| stripe_payment_intent_id | TEXT | Stripe支付ID |
| paid_at | TEXT | 支付时间 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

---

## 九、当前功能状态

### 9.1 已实现功能

- [x] 多平台视频解析（1800+ 平台）
- [x] 抖音专用无水印解析
- [x] B站专用解析
- [x] 多清晰度选择
- [x] 直链解析模式
- [x] 服务端代理下载
- [x] 缩略图代理（防盗链）
- [x] AI 视频总结（SSE 流式）
- [x] 字幕提取（B站/抖音/通用）
- [x] 思维导图生成
- [x] AI 视频问答
- [x] 用户注册/登录
- [x] JWT 认证
- [x] VIP 会员体系
- [x] Stripe 支付集成
- [x] 响应式前端界面

### 9.2 待实现功能

根据 README 规划：

- [ ] Whisper 语音转文字（无字幕视频 AI 识别）
- [ ] 字幕翻译功能
- [ ] 批量解析支持
- [ ] 下载进度实时推送
- [ ] Docker 容器化部署
- [ ] 移动端 App

---

## 十、快速上手指南

### 10.1 环境要求

- Python 3.10+
- Node.js 18+
- FFmpeg（视频处理需要）
- FFmpeg 自动下载（通过 static_ffmpeg）

### 10.2 启动步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-username/free-video-downloader.git
cd free-video-downloader

# 2. 后端配置
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 API Keys

# 3. 前端配置
cd ../frontend
npm install

# 4. 启动服务
# 终端1: 后端
cd backend
python main.py

# 终端2: 前端
cd frontend
npm run dev

# 5. 访问应用
# 前端: http://localhost:5173
# 后端 API: http://localhost:8000/docs
```

### 10.3 关键配置

```env
# backend/.env
DEEPSEEK_API_KEY=sk-xxxx      # DeepSeek API Key（必须）
JWT_SECRET=random-secret-key    # JWT 密钥（必须）
STRIPE_API_KEY=sk_test_xxx     # Stripe（可选，支付功能）
```

---

## 十一、常见问题排查

### 11.1 视频解析失败

**可能原因**：
- URL 格式不正确
- 视频设置了登录要求
- 视频存在地区限制
- 网络请求被拦截

**解决方案**：
1. 检查 URL 是否可公开访问
2. 确认是否需要登录
3. 查看后端日志具体错误

### 11.2 AI 总结失败

**可能原因**：
- 视频无字幕
- DeepSeek API Key 配置错误
- API 额度用尽

**解决方案**：
1. 使用有字幕的视频测试
2. 检查 `DEEPSEEK_API_KEY` 配置
3. 查看后端日志

### 11.3 抖音解析失败

**可能原因**：
- 抖音更新了反爬机制
- WAF 验证失败

**解决方案**：
查看 `problems solve.md` 文档中的详细排查步骤。

---

## 十二、后续优化建议

### 12.1 功能增强

1. **Whisper 语音识别**：为无字幕视频提供 AI 识别
2. **字幕翻译**：支持多语言字幕翻译
3. **批量处理**：支持多个视频同时解析
4. **进度推送**：下载进度实时展示

### 12.2 架构优化

1. **消息队列**：引入 Redis/RabbitMQ 处理异步任务
2. **缓存优化**：视频信息缓存，减少重复请求
3. **CDN 加速**：静态资源和缩略图使用 CDN
4. **Docker 部署**：容器化便于部署和扩展

### 12.3 商业化增强

1. **订阅套餐**：多种 VIP 套餐
2. **积分体系**：用户每日签到获积分
3. **推广佣金**：用户推广获得奖励

---

## 附录 A：关键文件索引

| 文件 | 路径 | 说明 |
|------|------|------|
| 后端入口 | `backend/main.py` | FastAPI 应用入口 |
| 通用解析 | `backend/downloader.py` | yt-dlp 封装 |
| 抖音解析 | `backend/douyin.py` | 抖音专用解析器 |
| B站解析 | `backend/bilibili.py` | B站专用解析器 |
| AI 总结 | `backend/summarizer.py` | 字幕提取 + DeepSeek |
| 数据库 | `backend/database.py` | SQLite 操作 |
| 认证 | `backend/auth.py` | JWT 中间件 |
| 总结 API | `backend/api_summarize.py` | SSE 流式接口 |
| 前端入口 | `frontend/src/main.js` | Vue 应用入口 |
| 视频组件 | `frontend/src/components/VideoResult.vue` | 解析结果展示 |

## 附录 B：API 接口速查

### 健康检查
```
GET /api/health
```

### 视频解析
```
POST /api/parse
Body: {"url": "https://..."}
```

### 视频下载
```
POST /api/download
Body: {"url": "https://...", "format_id": "bestvideo+bestaudio/best"}
```

### AI 总结（SSE）
```
POST /api/summarize
Body: {"url": "https://...", "language": "zh"}
```

### AI 问答（SSE）
```
POST /api/chat
Body: {"url": "https://...", "question": "...", "subtitle_text": ""}
```

---

**文档版本**: v1.0
**最后更新**: 2026-04-20
**维护者**: AI 编程助手
