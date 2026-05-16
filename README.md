# 万能视频解析器

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/FastAPI-0.135+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.5+-brightgreen.svg" alt="Vue 3">
  <img src="https://img.shields.io/badge/yt--dlp-2026.1+-orange.svg" alt="yt-dlp">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
</p>

<p align="center">
  <b>基于 yt-dlp 的万能视频解析服务，支持 1800+ 平台</b><br>
  集成 AI 视频总结、字幕提取、思维导图生成、博主追踪、批量字幕提取等高级功能
</p>

---

## 项目简介

万能视频解析器是一个功能强大的在线视频解析工具，支持从 1800+ 视频平台解析视频，并提供 AI 智能总结、字幕提取、思维导图生成、博主追踪等高级功能。

### 核心特性

- **多平台支持**：基于 yt-dlp，支持 YouTube、Bilibili、抖音、TikTok、Twitter/X、Instagram 等 1800+ 平台
- **多清晰度选择**：自动解析所有可用格式和清晰度，支持 4K/8K 画质
- **抖音专用解析**：针对抖音平台优化，支持无水印解析
- **B站专用解析**：针对 Bilibili 平台优化，支持完整格式解析
- **AI 视频总结**：自动生成视频摘要、内容大纲、核心知识要点
- **字幕提取**：支持提取平台自带字幕和自动字幕，可解析 SRT/VTT/TXT 格式
- **思维导图**：AI 自动生成结构化思维导图，支持 PNG/SVG 导出
- **AI 问答**：基于视频内容的智能问答，支持多轮对话
- **博主追踪**：自动追踪 B站/YouTube 博主，定期生成新视频报告
- **批量字幕提取**：支持一次性提取最多 20 个视频的字幕
- **用户系统**：支持用户注册登录，VIP 会员体系
- **支付系统**：集成 Stripe 支付，支持 VIP 会员购买
- **响应式设计**：完美适配桌面端和移动端
- **Docker 部署**：支持 Docker 容器化一键部署

---

## 功能展示

### 视频解析与下载

- 粘贴视频链接，自动解析视频信息
- 展示视频标题、缩略图、时长、上传者、平台来源
- 列出所有可用的格式和清晰度选项
- 支持直链解析和服务端代理解析两种模式

### AI 视频总结

- **总结摘要**：AI 自动生成视频概述、内容大纲、核心知识要点
- **字幕文本**：带时间戳的完整字幕列表，支持解析字幕文件
- **思维导图**：可交互的思维导图，支持全屏展示和导出
- **AI 问答**：针对视频内容提问，AI 基于字幕上下文回答

### 博主追踪系统

- **多平台支持**：支持 B站UP主、YouTube频道追踪
- **自动识别**：输入主页 URL，自动识别平台和博主信息
- **定期报告**：自动生成博主新视频报告
- **分组管理**：支持别名设置和分组标签管理
- **进度展示**：实时显示报告生成进度

### 批量字幕提取

- **批量处理**：一次性输入最多 20 个视频链接
- **流式返回**：SSE 实时返回每个视频的提取结果
- **智能识别**：自动识别视频平台
- **智能延时**：内置随机延时，避免请求过快

---

## 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 编程语言 |
| FastAPI | 0.135+ | Web 框架 |
| yt-dlp | 2026.1+ | 视频解析核心 |
| OpenAI SDK | 1.0+ | AI 大模型调用（兼容 DeepSeek） |
| SQLite | - | 数据库 |
| PyJWT | 2.8+ | 用户认证 |
| bcrypt | 4.0+ | 密码加密 |
| Stripe | 8.0+ | 支付系统 |
| feedparser | 6.0+ | RSS/Atom 订阅源解析 |
| httpx | 0.28+ | HTTP 客户端 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.5+ | 前端框架 |
| Vite | 7.3+ | 构建工具 |
| Tailwind CSS | 4.2+ | CSS 框架 |
| Axios | 1.13+ | HTTP 请求 |
| markmap | 0.18+ | 思维导图渲染 |
| marked | 17.0+ | Markdown 渲染 |

---

## 目录结构

```
free-video-downloader/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 应用入口 + 路由注册
│   ├── downloader.py           # yt-dlp 封装（视频解析/下载）
│   ├── douyin.py               # 抖音专用解析模块
│   ├── bilibili.py             # B站专用解析模块
│   ├── summarizer.py           # AI 总结模块
│   ├── api_summarize.py        # AI 总结 API 路由
│   ├── api_auth.py             # 用户认证 API
│   ├── api_payment.py          # 支付 API
│   ├── api_tracker.py          # 博主追踪 API
│   ├── api_batch.py            # 批量字幕提取 API
│   ├── auth.py                 # 认证中间件
│   ├── database.py             # 数据库操作
│   ├── tracker_database.py     # 追踪系统数据库
│   ├── tracker_scheduler.py    # 报告生成调度器
│   ├── tracker_bilibili_adapter.py  # B站追踪适配器
│   ├── tracker_youtube_adapter.py   # YouTube追踪适配器
│   ├── requirements.txt        # Python 依赖
│   └── .env.example            # 环境变量模板
│
├── frontend/                   # Vue3 前端
│   ├── src/
│   │   ├── App.vue             # 根组件
│   │   ├── main.js             # 入口文件
│   │   ├── style.css           # 全局样式
│   │   ├── components/         # Vue 组件
│   │   │   ├── AppHeader.vue           # 顶部导航
│   │   │   ├── AppFooter.vue           # 底部信息
│   │   │   ├── AuthModal.vue           # 登录注册弹窗
│   │   │   ├── HeroSection.vue         # 首页英雄区
│   │   │   ├── FeatureSection.vue      # 功能展示
│   │   │   ├── PricingSection.vue      # 定价方案
│   │   │   ├── PlatformSection.vue     # 支持平台
│   │   │   ├── HowToSection.vue        # 使用教程
│   │   │   ├── ComparisonSection.vue   # 对比展示
│   │   │   ├── VideoResult.vue         # 视频解析结果
│   │   │   ├── VideoSummary.vue        # AI 总结展示
│   │   │   ├── CreatorManager.vue      # 博主管理
│   │   │   ├── TrackerView.vue         # 追踪视图
│   │   │   ├── TrackerSettings.vue     # 追踪设置
│   │   │   ├── ReportList.vue          # 报告列表
│   │   │   ├── BatchSubtitleView.vue   # 批量字幕视图
│   │   │   └── ...
│   │   └── api/                # API 封装
│   │       ├── video.js        # 视频解析 API
│   │       ├── summarize.js    # AI 总结 API
│   │       ├── auth.js         # 认证 API
│   │       ├── payment.js      # 支付 API
│   │       ├── tracker.js      # 追踪 API
│   │       └── batch.js        # 批量字幕 API
│   ├── public/                 # 静态资源
│   │   ├── favicon.svg         # 网站图标
│   │   ├── robots.txt          # 爬虫规则
│   │   └── sitemap.xml         # 站点地图
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── docs/                       # 项目文档
│   ├── 需求分析.md
│   └── 方案设计.md
│
├── Dockerfile                  # Docker 镜像构建
├── docker-compose.yml          # Docker 编排
├── .dockerignore               # Docker 忽略文件
├── .gitignore                  # Git 忽略文件
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
├── demand.md                   # 需求文档
├── project.md                  # 项目说明
├── 项目架构解读文档.md          # 架构文档
└── README.md                   # 本文件
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- FFmpeg（视频下载需要）

### 1. 克隆项目

```bash
git clone https://github.com/your-username/free-video-downloader.git
cd free-video-downloader
```

### 2. 后端配置

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量配置
cp .env.example .env

# 编辑 .env 文件，填入必要的配置
```

**环境变量配置说明**：

```env
# ============ AI 服务 ============
# DeepSeek API Key（用于AI总结和追踪报告生成，必填）
DEEPSEEK_API_KEY=your_deepseek_api_key

# ============ 认证 ============
# JWT 密钥（生产环境请使用强随机字符串）
JWT_SECRET=your-jwt-secret-change-in-production

# ============ 支付（可选，不配置则支付功能不可用） ============
# STRIPE_SECRET_KEY=your_stripe_key
# STRIPE_WEBHOOK_SECRET=your_webhook_secret
# STRIPE_PRICE_ID_MONTHLY=your_price_id

# ============ 网络代理 ============
# 代理地址（用于访问 YouTube RSS 等，留空则不使用代理）
# 格式: http://IP:PORT 或 socks5://IP:PORT
PROXY_URL=http://127.0.0.1:6478

# ============ 其他 ============
# 前端 URL
FRONTEND_URL=http://localhost:5173
```

### 3. 前端配置

```bash
# 进入前端目录
cd ../frontend

# 安装依赖
npm install
```

### 4. 启动服务

**启动后端**：

```bash
cd backend
python main.py
```

后端服务将运行在 http://localhost:8001

**启动前端**：

```bash
cd frontend
npm run dev
```

前端服务将运行在 http://localhost:5173

### 5. 访问应用

打开浏览器访问：http://localhost:5173

### 6. Docker 部署（可选）

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## API 文档

### 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/parse` | POST | 解析视频信息 |
| `/api/download` | POST | 下载视频（服务端代理） |
| `/api/direct-url` | POST | 获取视频直链 |
| `/api/proxy/thumbnail` | GET | 代理获取缩略图 |

### AI 功能接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/summarize` | POST | AI 视频总结（SSE） |
| `/api/chat` | POST | AI 视频问答（SSE） |
| `/api/batch-subtitles` | POST | 批量字幕提取（SSE） |

### 用户接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/me` | GET | 获取当前用户信息 |

### 支付接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/payment/create-session` | POST | 创建支付会话 |
| `/api/payment/webhook` | POST | Stripe 回调 |

### 博主追踪接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/tracker/creators` | POST | 添加博主订阅 |
| `/api/tracker/creators` | GET | 获取订阅列表 |
| `/api/tracker/creators/{sub_id}` | PATCH | 更新订阅信息 |
| `/api/tracker/creators/{sub_id}` | DELETE | 删除订阅 |
| `/api/tracker/reports` | GET | 获取报告列表 |
| `/api/tracker/reports/{report_id}` | GET | 获取报告详情 |
| `/api/tracker/reports/{report_id}` | DELETE | 删除报告 |
| `/api/tracker/reports/generate` | POST | 手动触发报告生成 |
| `/api/tracker/reports/{report_id}/progress` | GET | 查询报告生成进度 |

详细 API 文档请访问：http://localhost:8001/docs

---

## 使用额度

- **普通用户**：每日 5 次免费解析额度
- **VIP 用户**：无限使用

---

## 支持的平台

基于 yt-dlp，支持 1800+ 视频平台，包括但不限于：

- **视频平台**：YouTube、Bilibili、优酷、腾讯视频、爱奇艺
- **短视频平台**：抖音、TikTok、快手、小红书
- **社交媒体**：Twitter/X、Instagram、Facebook
- **其他平台**：Vimeo、Dailymotion、Twitch 等

完整支持列表请查看：[yt-dlp 支持站点](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

### 博主追踪支持平台

- **Bilibili**：UP主空间追踪，自动获取新视频
- **YouTube**：频道追踪，通过 RSS 获取新视频

---

## 注意事项

1. **仅供学习交流**：本项目仅供学习研究使用，请勿用于商业用途
2. **版权声明**：解析的视频内容版权归原作者所有，请尊重版权
3. **使用限制**：请遵守各平台的使用条款，不要频繁请求
4. **临时文件**：下载的临时文件会在服务重启时自动清理
5. **网络代理**：访问 YouTube 等平台可能需要配置代理
6. **API Key 安全**：请妥善保管 DeepSeek API Key，不要提交到公开仓库

---

## 常见问题

### 1. 视频解析失败？

- 检查 URL 是否正确
- 确认视频是否公开可访问
- 某些平台可能需要登录或存在地区限制

### 2. 下载速度慢？

- 服务端代理模式会占用服务器带宽
- 建议优先使用直链模式解析

### 3. AI 总结不准确？

- AI 总结基于视频字幕，无字幕视频无法总结
- 字幕质量会影响总结效果

### 4. YouTube 追踪失败？

- 检查是否配置了网络代理（PROXY_URL）
- 确认 RSS 订阅源是否可访问
- 某些频道可能没有公开 RSS

### 5. 批量字幕提取报错？

- 检查视频是否有字幕（包括自动字幕）
- 确认网络连接正常
- 无字幕视频无法提取

---

## 后续规划

- [ ] Whisper 语音转文字（为无字幕视频提供 AI 识别）
- [ ] 字幕翻译功能
- [ ] 下载进度实时推送
- [ ] 更多追踪平台支持（TikTok、Twitter/X 等）
- [ ] 移动端 App

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 许可证

本项目基于 MIT 许可证开源。详情请参阅 [LICENSE](LICENSE) 文件。

---

## 联系方式

如有问题或建议，欢迎提交 Issue。

---

<p align="center">
  <sub>Made with ❤️ by free-video-downloader team</sub>
</p>
