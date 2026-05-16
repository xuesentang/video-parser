# 博主追踪模块性能优化进阶方案（优化plus.md）

> **基于原 `优化.md` 的修正与增强版本**
>
> 原方案大方向正确，但存在代码逻辑错误、过度简化 API 策略、遗漏 AI 并行优化等问题。
> 本方案在保留原方案低风险优化的基础上，修正错误、补充关键优化点，并重新划分实施阶段。

---

## 一、原方案问题诊断

### 1.1 代码逻辑错误（严重）

原方案步骤3中，优化后的 `get_creator_info` 函数在"方案2: 搜索API"降级分支中调用了 `_fetch_videos_via_search_api()`，该函数返回的是 `list[VideoItem]`（视频列表），但 `get_creator_info` 的返回类型是 `CreatorInfo`（博主信息）。**这是类型不匹配的严重bug，会导致运行时错误。**

```python
# 原方案错误代码片段
if creator_name:
    try:
        videos = _fetch_videos_via_search_api(mid, creator_name, cutoff, session)
        if videos:  # ❌ videos 是 list[VideoItem]，不是 CreatorInfo
            return videos  # ❌ 返回类型错误！
    except Exception as e:
        logger.warning("搜索 API 获取视频失败：%s", e)
```

### 1.2 API 降级策略过度简化

原方案建议**完全移除** `space/arc/search` API 的使用，改为仅依赖搜索API获取视频。

**问题**：
- `space/arc/search` 是B站官方UP主空间视频接口，按 `mid` 精确过滤，**准确率100%**
- 搜索API依赖UP主名字匹配，存在以下风险：
  - 同名UP主导致视频混入
  - UP主改名后搜索失效
  - 搜索结果的 `mid` 过滤可能遗漏视频（搜索引擎的索引延迟）

**正确做法**：保留 `space/arc/search` 作为**首选**，优化其调用效率；搜索API作为**降级兜底**。

### 1.3 遗漏 AI 概要并行优化

即使B站API提速60-70%，AI批量生成概要仍是同步阻塞操作。原方案未针对此瓶颈提出有效优化。

### 1.4 缺少缓存机制

博主信息（头像、名字、简介）在短时间内不会变化，每次报告生成都重复请求是浪费。

---

## 二、修正后的优化策略

### 2.1 策略对比表（修正版）

| 维度 | free-video-downloader (现有) | 原优化方案 | 本进阶方案 |
|------|------------------------------|-----------|-----------|
| **Cookie 获取** | 访问首页获取（5-15秒） | 随机UUID生成（瞬间） | 随机UUID生成（瞬间） |
| **获取博主信息** | space/acc/info → card API → 网页解析（3级） | space/acc/info → 搜索API（2级） | space/acc/info → card API（2级，移除网页解析） |
| **获取视频列表** | space/arc/search → 搜索API | 仅搜索API（❌过度简化） | **space/arc/search 首选 → 搜索API降级** |
| **限流策略** | 2.5秒基础 + 自适应（最高10秒） | 1.5秒基础 + 保留自适应 | 1.5秒基础 + 轻量自适应（最高5秒） |
| **重试次数** | 3次 | 2次 | 2次 |
| **AI概要** | 批量同步调用 | 未优化 | **异步并行 + 超时控制** |
| **缓存** | 无 | 无（第三阶段才提） | **第一阶段即引入博主信息缓存** |
| **增量更新** | 无 | 第三阶段 | **第二阶段引入** |

---

## 三、分阶段实施计划（修正版）

### 🟢 第一阶段：低风险核心优化（推荐立即实施）

**目标**：耗时从 4-10 分钟 降至 **1-2 分钟**，成功率保持 95%+

#### 步骤 1：Cookie 自动生成（照搬原方案，正确）

**文件**：`backend/tracker_bilibili_adapter.py`

```python
import uuid

def _init_session() -> requests.Session:
    """初始化Session，自动生成buvid3 Cookie（参考yupi-hot-monitor方案）"""
    global _session, _session_created_at

    now = time.time()
    if _session and (now - _session_created_at) < _SESSION_TTL:
        return _session

    logger.info("初始化B站Session，生成buvid3 Cookie...")
    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)

    # 自动生成buvid3（无需访问首页）
    buvid3 = f"{uuid.uuid4()}infoc"
    sess.cookies.set("buvid3", buvid3, domain=".bilibili.com")
    logger.info("B站Cookie生成成功: buvid3=%s...", buvid3[:20])

    _session = sess
    _session_created_at = now
    return sess
```

**收益**：每博主节省 5-15 秒

---

#### 步骤 2：缩短基础限流 + 轻量自适应

**文件**：`backend/tracker_bilibili_adapter.py`

```python
# 修改前
_MIN_REQUEST_INTERVAL = 2.5  # 最小请求间隔2.5秒

# 修改后
_MIN_REQUEST_INTERVAL = 1.5  # 最小请求间隔1.5秒
_MAX_ADAPTIVE_INTERVAL = 5.0  # 自适应上限从10秒降至5秒
```

同时修改 `_rate_limit_wait`：

```python
def _rate_limit_wait():
    """确保请求间隔不低于阈值，避免触发B站限流"""
    global _last_request_time, _consecutive_failures

    # 轻量自适应：基础1.5秒 + 连续失败惩罚（每次+0.5秒，上限5秒）
    adaptive_interval = min(_MIN_REQUEST_INTERVAL + _consecutive_failures * 0.5, _MAX_ADAPTIVE_INTERVAL)

    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < adaptive_interval:
        wait = adaptive_interval - elapsed
        logger.debug("限流等待 %.1fs (连续失败=%d)", wait, _consecutive_failures)
        time.sleep(wait)
    _last_request_time = time.time()
```

**收益**：总体提速 30-40%，且保留安全防护

---

#### 步骤 3：简化博主信息降级（保留2级，移除网页解析）

**文件**：`backend/tracker_bilibili_adapter.py`

修改 `get_creator_info`，**保留 space/acc/info → card API 两级**，移除网页标题解析（成功率仅3%，耗时却不低）：

```python
def get_creator_info(url: str) -> CreatorInfo:
    """
    输入UP主主页URL，返回博主信息。
    两级降级策略：
    1. space/acc/info API（需buvid3 Cookie，无需WBI签名）
    2. card API（备用，同样需Cookie）
    """
    mid = extract_mid_from_url(url)
    if not mid:
        mid = url.strip().split("/")[-1].split("?")[0]
        if not mid.isdigit():
            raise ValueError("无法从URL中提取B站UP主mid，请输入正确的个人空间链接")

    session = _get_session()

    # === 方案1: space/acc/info ===
    for attempt in range(2):  # 3次→2次
        try:
            _rate_limit_wait()
            resp = session.get(
                SPACE_INFO_API,
                params={"mid": mid},
                timeout=(10, 30),
                headers=DEFAULT_HEADERS,
            )
            data = resp.json()

            if data.get("code") == 0:
                mark_request_success()
                info = data.get("data", {})
                return CreatorInfo(
                    platform="bilibili",
                    platform_id=str(mid),
                    name=info.get("name", "未知UP主"),
                    avatar_url=info.get("face", ""),
                    description=info.get("sign", "")[:200],
                    home_url=f"https://space.bilibili.com/{mid}",
                )

            error_code = data.get("code", -1)
            error_msg = data.get("message", "未知错误")

            if error_code == -799 or "频繁" in error_msg:
                mark_request_failure()
                wait = 4 * (attempt + 1)  # 8秒→4秒
                logger.warning("space/acc/info限流 mid=%s, 等待%ds", mid, wait)
                time.sleep(wait)
                if attempt < 1:
                    _init_session()
                    session = _get_session()
                continue

            logger.warning("space/acc/info错误 code=%s msg=%s", error_code, error_msg)
            break

        except requests.RequestException as e:
            logger.warning("space/acc/info请求异常: %s", e)
            if attempt < 1:
                time.sleep(2 * (2 ** attempt))

    # === 方案2: card API ===
    try:
        _rate_limit_wait()
        resp = session.get(
            CARD_INFO_API,
            params={"mid": mid, "photo": "true"},
            timeout=(10, 30),
            headers=DEFAULT_HEADERS,
        )
        data = resp.json()

        if data.get("code") == 0:
            mark_request_success()
            card = data.get("data", {}).get("card", {})
            return CreatorInfo(
                platform="bilibili",
                platform_id=str(mid),
                name=card.get("name", "未知UP主"),
                avatar_url=card.get("face", ""),
                description=card.get("sign", "")[:200],
                home_url=f"https://space.bilibili.com/{mid}",
            )
        logger.warning("card API失败: code=%s msg=%s", data.get("code"), data.get("message"))
    except Exception as e:
        logger.warning("card API异常: %s", e)

    raise ValueError("获取B站UP主信息失败（2种方案均失败），请稍后重试")
```

**收益**：代码更简洁，每博主节省 3-5 秒

---

#### 步骤 4：保留 space/arc/search 作为视频获取首选

**文件**：`backend/tracker_bilibili_adapter.py`

**关键修正**：原方案建议移除 `_fetch_videos_via_space_api`，这是错误的。

正确做法：保留该函数，但优化其调用效率（Cookie已优化、限流已缩短）：

```python
def get_recent_videos(mid: str, hours: int = 24, creator_name: str = "") -> list[VideoItem]:
    """
    获取UP主近期视频列表。
    策略：
    1. 先尝试 space/arc/search API（精确按mid过滤，最准确）
    2. 降级到搜索API（用UP主名搜索，按mid过滤）
    """
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    session = _get_session()
    videos = []

    # === 方案1: space/arc/search（首选，精确匹配） ===
    try:
        videos = _fetch_videos_via_space_api(mid, cutoff, session)
        if videos:
            return videos
    except Exception as e:
        logger.warning("space API获取视频失败: %s", e)

    # === 方案2: 搜索API降级 ===
    if not creator_name:
        # 尝试从space/acc/info获取名字
        try:
            _rate_limit_wait()
            resp = session.get(
                SPACE_INFO_API,
                params={"mid": mid},
                timeout=(10, 30),
                headers=DEFAULT_HEADERS,
            )
            data = resp.json()
            if data.get("code") == 0:
                creator_name = data["data"].get("name", "")
        except Exception:
            pass

    if creator_name:
        try:
            videos = _fetch_videos_via_search_api(mid, creator_name, cutoff, session)
        except Exception as e:
            logger.warning("搜索API获取视频失败: %s", e)

    return videos
```

**收益**：视频获取准确率保持100%，同时享受Cookie优化和限流缩短的收益

---

#### 步骤 5：引入博主信息缓存（新增）

**文件**：`backend/tracker_bilibili_adapter.py`

新增简单内存缓存，避免重复获取博主信息：

```python
from functools import lru_cache

# 博主信息缓存（10分钟TTL）
_creator_info_cache: dict[str, tuple[CreatorInfo, float]] = {}
_CREATOR_CACHE_TTL = 600  # 10秒

def get_creator_info_cached(url: str) -> CreatorInfo:
    """带缓存的博主信息获取"""
    mid = extract_mid_from_url(url)
    if not mid:
        mid = url.strip().split("/")[-1].split("?")[0]

    now = time.time()
    if mid in _creator_info_cache:
        info, cached_at = _creator_info_cache[mid]
        if now - cached_at < _CREATOR_CACHE_TTL:
            logger.debug("命中博主信息缓存 mid=%s", mid)
            return info

    info = get_creator_info(url)
    _creator_info_cache[mid] = (info, now)
    return info
```

**收益**：同一报告生成过程中，重复博主信息请求降为0

---

#### 步骤 6：调度器参数优化

**文件**：`backend/tracker_scheduler.py`

```python
# 修改前
BATCH_SIZE = 3
BATCH_PAUSE_MIN = 5.0
BATCH_PAUSE_MAX = 10.0
CREATOR_PAUSE_MIN = 2.0
CREATOR_PAUSE_MAX = 4.0

# 修改后
BATCH_SIZE = 5  # 增大批次
BATCH_PAUSE_MIN = 3.0  # 缩短批次间隔
BATCH_PAUSE_MAX = 5.0
CREATOR_PAUSE_MIN = 1.0  # 缩短博主间间隔
CREATOR_PAUSE_MAX = 2.0
BILIBILI_SESSION_REFRESH_INTERVAL = 5  # 从3改为5（Cookie自动生成后，刷新需求降低）
```

**收益**：调度开销减少 30-40%

---

### 🟡 第二阶段：AI 并行优化 + 增量更新（中风险）

**目标**：耗时从 1-2 分钟 降至 **30-60 秒**

#### 步骤 7：AI 概要异步并行（新增）

**文件**：`backend/tracker_scheduler.py`

当前 `_batch_generate_summaries` 是同步阻塞的。优化为**异步调用 + 超时控制**：

```python
import asyncio
import httpx

async def _batch_generate_summaries_async(videos: list) -> dict[str, str]:
    """异步批量生成AI概要，带超时控制"""
    if not videos:
        return {}

    video_list_text = ""
    for i, v in enumerate(videos, 1):
        desc_short = (v.description or "")[:100]
        video_list_text += f"{i}. 标题：{v.title}"
        if desc_short:
            video_list_text += f"  描述：{desc_short}"
        video_list_text += "\n"

    prompt = (
        f"请为以下{len(videos)}个视频分别生成50字左右的扩展概要..."
        # ... 省略，与原prompt相同
    )

    messages = [
        {"role": "system", "content": "你是一个视频内容概括助手..."},
        {"role": "user", "content": prompt},
    ]

    try:
        from summarizer import VideoSummarizer
        summarizer = VideoSummarizer()

        # 使用asyncio.wait_for设置超时（15秒）
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: summarizer.client.chat.completions.create(
                    model=summarizer.model,
                    messages=messages,
                    stream=False,
                    temperature=0.5,
                    max_tokens=200 * len(videos),
                )
            ),
            timeout=15.0
        )
        result_text = response.choices[0].message.content.strip()
        return _parse_batch_result(result_text, videos)
    except asyncio.TimeoutError:
        logger.warning("AI概要生成超时，降级为原始描述")
        return {v.video_id: (v.description[:100] if v.description else v.title) for v in videos}
    except Exception as e:
        logger.warning("AI概要生成失败: %s", e)
        return {v.video_id: (v.description[:100] if v.description else v.title) for v in videos}
```

同时在 `generate_report_for_user` 中，将多个博主的AI概要生成改为**并行**：

```python
# 收集所有需要生成概要的博主
async def generate_report_for_user_async(user_id: int) -> int:
    # ... 前面的代码不变 ...

    # 先并行获取所有博主的视频
    video_tasks = []
    for creator in creators:
        if creator["platform"] == "bilibili":
            task = asyncio.create_task(
                asyncio.to_thread(
                    bilibili_get_videos,
                    creator["platform_id"],
                    hours=REPORT_TIME_RANGE_HOURS,
                    creator_name=creator["name"]
                )
            )
        elif creator["platform"] == "youtube":
            task = asyncio.create_task(
                asyncio.to_thread(
                    youtube_get_videos,
                    creator["platform_id"],
                    hours=REPORT_TIME_RANGE_HOURS
                )
            )
        video_tasks.append((creator, task))

    # 等待所有视频获取完成
    all_videos = []
    for creator, task in video_tasks:
        try:
            videos = await task
            all_videos.append((creator, videos))
        except Exception as e:
            logger.error("获取博主视频失败 name=%s: %s", creator["name"], e)

    # 并行生成所有AI概要
    summary_tasks = []
    for creator, videos in all_videos:
        if videos:
            task = asyncio.create_task(_batch_generate_summaries_async(videos))
            summary_tasks.append((creator, videos, task))

    # 组装报告
    for creator, videos, task in summary_tasks:
        summaries = await task
        # ... 组装markdown ...
```

**注意**：此改动较大，需要同步修改 `api_tracker.py` 中的调用方式。

---

#### 步骤 8：增量更新模式（新增）

**文件**：`backend/tracker_database.py` + `backend/tracker_scheduler.py`

在数据库中记录每个博主的"上次检查时间"，下次只获取该时间之后的新视频：

```python
# tracker_database.py 新增

def get_creator_last_checked(creator_id: int) -> Optional[datetime]:
    """获取博主上次检查时间"""
    # 从数据库查询...

def update_creator_last_checked(creator_id: int, check_time: datetime):
    """更新博主上次检查时间"""
    # 写入数据库...
```

```python
# tracker_scheduler.py 修改

def generate_report_for_user(user_id: int) -> int:
    # ...
    for creator in creators:
        # 计算时间范围：从上一次检查到现在
        last_checked = get_creator_last_checked(creator["id"])
        if last_checked:
            hours_since = (datetime.now(timezone.utc) - last_checked).total_seconds() / 3600
            hours = max(int(hours_since), 1)  # 至少1小时
        else:
            hours = REPORT_TIME_RANGE_HOURS  # 首次检查，用默认值

        videos = bilibili_get_videos(platform_id, hours=hours, creator_name=name)

        # 更新检查时间
        update_creator_last_checked(creator["id"], datetime.now(timezone.utc))
        # ...
```

**收益**：非首次报告生成时，视频获取量大幅减少，速度提升 50%+

---

### 🔴 第三阶段：架构级优化（长期）

#### 步骤 9：后台异步报告生成

当前报告生成是同步阻塞的，用户需要等待。优化为：

1. API 立即返回"生成中"状态
2. 后台任务（可用 `asyncio.create_task` 或引入 Celery）完成实际生成
3. 前端轮询进度

```python
# api_tracker.py
from fastapi import BackgroundTasks

@app.post("/tracker/reports/generate")
async def trigger_report_generation(
    user_id: int,
    background_tasks: BackgroundTasks
):
    report = create_report(user_id, today)
    background_tasks.add_task(generate_report_for_user_async, user_id, report["id"])
    return {"report_id": report["id"], "status": "generating"}
```

#### 步骤 10：持久化缓存（Redis/SQLite）

将博主信息缓存从内存迁移到持久化存储，服务重启后缓存不丢失。

---

## 四、第一阶段实施检查清单

| 步骤 | 文件 | 改动内容 | 验证方式 |
|------|------|----------|----------|
| 1 | `tracker_bilibili_adapter.py` | Cookie自动生成 | 单博主测试 < 5秒 |
| 2 | `tracker_bilibili_adapter.py` | 限流1.5秒 + 轻量自适应 | 连续10次请求不触发-799 |
| 3 | `tracker_bilibili_adapter.py` | 移除网页解析降级 | 代码审查 |
| 4 | `tracker_bilibili_adapter.py` | 保留space/arc/search首选 | 视频获取准确率100% |
| 5 | `tracker_bilibili_adapter.py` | 新增博主信息缓存 | 同一报告内不重复请求 |
| 6 | `tracker_scheduler.py` | 调度参数优化 | 10博主报告 < 2分钟 |

---

## 五、预期效果对比

| 指标 | 优化前 | 第一阶段后 | 第二阶段后 |
|------|--------|-----------|-----------|
| **10博主总耗时** | 4-10分钟 | **1-2分钟** | **30-60秒** |
| **单博主B站API耗时** | 20-40秒 | 4-8秒 | 4-8秒 |
| **请求次数/博主** | 3-6次 | 2-3次 | 2-3次 |
| **视频获取准确率** | 100% | **100%** | 100% |
| **成功率** | ~95% | ~94% | ~93% |

---

## 六、关键风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| buvid3生成方式被B站限制 | 低 | 中 | 保留首页获取Cookie的fallback代码（注释即可） |
| 1.5秒限流触发频繁-799 | 中 | 低 | 轻量自适应机制自动回退到更长间隔 |
| space/arc/search被移除 | 低 | 高 | 搜索API降级已就绪，可无缝切换 |
| AI并行导致API限流 | 中 | 低 | 设置15秒超时，超时时降级为原始描述 |

---

## 七、与原方案的核心差异总结

| 差异点 | 原方案 | 本进阶方案 |
|--------|--------|-----------|
| `get_creator_info` 降级 | 调用 `_fetch_videos_via_search_api`（❌类型错误） | 保留 `card API` 降级（✅类型正确） |
| 视频获取策略 | 仅搜索API（❌可能漏视频） | space/arc/search 首选 + 搜索API降级（✅准确） |
| AI概要优化 | 未涉及 | 异步并行 + 超时控制（✅显著提速） |
| 缓存机制 | 第三阶段才引入 | 第一阶段即引入（✅立竿见影） |
| 增量更新 | 第三阶段才引入 | 第二阶段引入（✅减少重复工作） |

---

## 八、下一步建议

1. **先实施第一阶段**（步骤1-6），风险低、收益高
2. **验证1周后**，监控失败率和耗时指标
3. **再实施第二阶段**（步骤7-8），涉及异步改造，需要更多测试
4. **最后考虑第三阶段**（步骤9-10），架构级改动

---

**文档版本**：v1.0（进阶版）  
**创建时间**：2026-05-15  
**基于**：优化.md v1.0  
**参考项目**：yupi-hot-monitor
