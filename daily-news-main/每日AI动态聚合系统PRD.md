# 每日 AI 动态聚合系统 PRD

版本：v0.1  
日期：2026-05-26  
目标：给研发评估并实现一个可部署到线上的每日 AI/产品/开源动态聚合服务。

## 1. 背景

我们已经验证了四类信息源：

1. AI HOT：中文 AI 行业动态，含模型、产品、行业、论文、观点。
2. Follow Builders：AI builders 的 X/Twitter、播客、博客内容，偏人物观点和一线 builder 视角。
3. Product Hunt：前一天产品发布 Top 10，按 votes/score 排序。
4. GitHub Trending：最近 7 天热门开源项目。

当前这些能力一部分以 Codex skill 形式存在，但线上部署不能依赖本地 skill 运行环境。因此本项目要把它们抽象成可部署的 collector + normalizer + AI editor + web/API 输出系统。

## 2. 产品目标

每天自动生成一份中文动态简报，按以下栏目重新归类：

1. 产品动态
2. GitHub 动态
3. 模型/技术发展动态
4. 新闻/观点

每条内容必须包含来源链接，并尽量说明：

- 这是什么
- 目标用户是谁
- 解决什么需求
- 为什么值得关注

## 3. 非目标

MVP 不做：

- 用户登录
- 个性化推荐
- 复杂订阅系统
- 评论情绪分析
- 实时资讯流
- 多语言版本
- 完整后台 CMS

## 4. 四个数据源

### 4.1 AI HOT

用途：中文 AI 行业主源。

推荐接口：

```text
GET https://aihot.virxact.com/api/public/items?mode=selected&since=<ISO>&take=100
GET https://aihot.virxact.com/api/public/daily
```

注意：

- API 端点要求带浏览器 User-Agent。
- 默认拉精选 `mode=selected`。
- `items` 端点更适合滚动时间窗。
- `daily` 更像编辑成品，可作为补充或兜底。

字段映射：

| 原字段 | 统一字段 |
|---|---|
| title | title |
| summary | summary |
| url | url |
| source | source_name |
| publishedAt | published_at |
| category | source_category |

分类映射：

| AI HOT category | 系统栏目 |
|---|---|
| ai-products | 产品动态 |
| ai-models | 模型/技术发展动态 |
| paper | 模型/技术发展动态 |
| industry | 新闻/观点 |
| tip | 新闻/观点 |

### 4.2 Follow Builders

用途：捕捉 AI builders 正在说什么、做什么、发布什么。它是四个源里最适合补充“观点”和“早期信号”的源。

#### 4.2.1 当前形态

本地 skill 的核心不是 agent 行为，而是一个 deterministic prepare script。该脚本做三件事：

1. 拉远程 feed JSON
2. 拉远程 prompts
3. 输出一个可供 LLM remix 的 JSON

已验证的远程 feed：

```text
https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json
https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json
https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json
```

本地脚本里也明确使用这些 URL：

```js
const FEED_X_URL = 'https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json';
const FEED_PODCASTS_URL = 'https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json';
const FEED_BLOGS_URL = 'https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json';
```

因此线上系统不需要运行 skill，也不需要模拟 Codex。可以直接把 Follow Builders 抽象为一个远程 JSON collector。

#### 4.2.2 Follow Builders 抽象方案

将 Follow Builders 抽象成三个 collector：

1. `follow_builders_x_collector`
2. `follow_builders_podcast_collector`
3. `follow_builders_blog_collector`

Collector 职责：

- 定时抓取 GitHub raw JSON。
- 校验 `generatedAt`、`lookbackHours`、`stats`。
- 展开 builder/tweet、podcast episode、blog post。
- 写入统一 `raw_items` 表。
- 不在 collector 阶段做深度改写。

为什么不直接使用 Follow Builders 的 digest：

- 原 digest 是面向单次阅读的成品，不利于与 AI HOT、Product Hunt、GitHub Trending 做去重和跨源归类。
- 我们需要 item-level 数据，后续 AI editor 才能把它们重新分到“产品动态 / GitHub 动态 / 模型技术 / 新闻观点”。
- X、podcast、blog 的权重不同，需要独立处理。

#### 4.2.3 Follow Builders 数据结构

`feed-x.json` 结构示例：

```json
{
  "generatedAt": "2026-05-25T07:55:59.650Z",
  "lookbackHours": 24,
  "stats": {},
  "x": [
    {
      "source": "x",
      "name": "Peter Yang",
      "handle": "petergyang",
      "bio": "...",
      "tweets": [
        {
          "id": "2058555226479866312",
          "text": "...",
          "createdAt": "2026-05-24T14:26:26.000Z",
          "url": "https://x.com/petergyang/status/2058555226479866312",
          "likes": 164,
          "retweets": 13,
          "replies": 23,
          "isQuote": false,
          "quotedTweetId": null
        }
      ]
    }
  ]
}
```

统一成：

```json
{
  "source": "follow_builders_x",
  "source_item_id": "x:2058555226479866312",
  "title": "Peter Yang: We used to say build the MVP...",
  "summary": null,
  "body": "tweet full text",
  "url": "https://x.com/petergyang/status/2058555226479866312",
  "author_name": "Peter Yang",
  "author_handle": "petergyang",
  "author_bio": "...",
  "published_at": "2026-05-24T14:26:26.000Z",
  "metrics": {
    "likes": 164,
    "retweets": 13,
    "replies": 23
  },
  "raw_json": {}
}
```

`feed-podcasts.json` 结构示例：

```json
{
  "podcasts": [
    {
      "source": "podcast",
      "name": "Unsupervised Learning",
      "title": "Ep 86: Yann LeCun...",
      "guid": "...",
      "url": "https://www.youtube.com/@RedpointAI",
      "publishedAt": "2026-05-15T12:50:21.000Z",
      "transcript": "..."
    }
  ]
}
```

统一成：

```json
{
  "source": "follow_builders_podcast",
  "source_item_id": "podcast:<guid>",
  "title": "Ep 86: Yann LeCun...",
  "summary": null,
  "body": "transcript",
  "url": "https://www.youtube.com/@RedpointAI",
  "author_name": "Unsupervised Learning",
  "published_at": "2026-05-15T12:50:21.000Z",
  "metadata": {
    "content_type": "podcast_transcript"
  }
}
```

注意：当前 podcast `url` 可能是频道 URL，不一定是具体视频 URL。研发要保留原始字段，不要把它伪装成 episode URL。后续可增加 `episode_url` 修复逻辑。

`feed-blogs.json` 当前可能为空，但仍保留 collector：

```json
{
  "source": "follow_builders_blog",
  "source_item_id": "blog:<url-or-guid>",
  "title": "...",
  "summary": "...",
  "body": "...",
  "url": "...",
  "author_name": "...",
  "published_at": "..."
}
```

#### 4.2.4 Follow Builders 分类规则

Follow Builders 先进入候选池，再由 AI editor 归类。

初始 heuristic：

| 内容特征 | 默认栏目 |
|---|---|
| 明确产品发布、工具发布、startup workflow | 产品动态 |
| 代码 agent、developer tooling、open source tool | GitHub 动态或模型/技术发展动态 |
| 模型、agent architecture、world model、benchmark、paper | 模型/技术发展动态 |
| CEO/Founder 对行业、组织、AI adoption 的观点 | 新闻/观点 |
| podcast transcript | 默认新闻/观点，若技术密度高可进模型/技术 |

#### 4.2.5 Follow Builders 摘要策略

不要在 collector 阶段调用 LLM。统一进入 AI editor 后处理。

但是 Follow Builders 内容较长，尤其 podcast transcript 可能非常长。建议增加中间层 `source_summarizer`：

1. X tweets：按 builder 合并，生成 2-4 句 source summary。
2. podcast transcript：先生成 400-800 字 source summary，再进入全局 editor。
3. blog posts：保留原 summary；无 summary 时再生成。

这样可以降低全局 AI editor 的 token 压力。

#### 4.2.6 Follow Builders 稳定性和风险

风险：

- GitHub raw feed 是第三方项目维护，不是正式 SaaS SLA。
- X 数据可能受上游抓取限制影响。
- podcast URL 当前可能不够精确。
- feed 可能变更 schema。

应对：

- 每次抓取保存完整 raw JSON。
- collector 加 schema version 和宽松解析。
- 如果某个 feed 抓取失败，不影响其他三个源。
- `feedGeneratedAt` 超过 48 小时则标记 stale。
- dashboard 显示每个 source 的最后成功抓取时间。

### 4.3 Product Hunt

用途：前一天产品发布 Top 10。

推荐：

- 使用官方 GraphQL API。
- 需要服务端环境变量 `PRODUCT_HUNT_TOKEN`。
- 不要把 token 暴露给前端。
- Product Hunt 日期按 `America/Los_Angeles`。
- 每天取前一个 Product Hunt 自然日。

GraphQL 字段：

```graphql
posts(postedAfter, postedBefore, first: 10, order: VOTES) {
  edges {
    node {
      id
      name
      slug
      tagline
      description
      url
      website
      votesCount
      commentsCount
      dailyRank
      latestScore
      featuredAt
      createdAt
      topics(first: 5) { edges { node { name slug } } }
    }
  }
}
```

统一字段：

```json
{
  "source": "product_hunt",
  "source_item_id": "ph:<id>",
  "title": "Unabyss",
  "summary": "MCP-native self-updating context layer for your AI",
  "body": "description",
  "url": "https://www.producthunt.com/products/unabyss",
  "published_at": "2026-05-25T...",
  "metrics": {
    "votes": 520,
    "comments": 118,
    "daily_rank": 1
  },
  "metadata": {
    "topics": ["Productivity", "Artificial Intelligence"]
  }
}
```

### 4.4 GitHub Trending

用途：最近 7 天热门开源项目。

主源：

```text
https://rsshub.rssforever.com/github/trending/weekly/any
```

备源：

```text
https://mshibanami.github.io/GitHubTrendingRSS/weekly/all.xml
```

选择理由：

- RSSHub 输出更干净，适合作为主源。
- GitHubTrendingRSS 内容会把 README 长文塞进 description，清洗成本高，适合兜底。

统一字段：

```json
{
  "source": "github_trending",
  "source_item_id": "github:owner/repo",
  "title": "owner/repo",
  "summary": "repo description",
  "url": "https://github.com/owner/repo",
  "metrics": {
    "stars": 25643,
    "forks": 1418
  },
  "metadata": {
    "language": "TypeScript",
    "period": "weekly"
  }
}
```

## 5. 系统架构

推荐 MVP 架构：

```text
Cron Scheduler
  -> Source Collectors
  -> Raw Item Store
  -> Normalizer
  -> Deduper
  -> Source Summarizer
  -> AI Editor
  -> Digest Store
  -> Web / Public API / RSS
```

推荐技术栈：

方案 A：

```text
Next.js + Vercel Cron + Postgres
```

优点：部署简单，网页和 API 一体。

方案 B：

```text
Python FastAPI + APScheduler/Cron + Postgres
```

优点：collector 和数据处理更顺手。

如果研发团队熟悉 TypeScript，建议选方案 A。MVP 里 Next.js API route 或 server action 足够。

## 6. 数据模型

### 6.1 raw_items

保存源数据，便于重跑。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 主键 |
| source | text | aihot / follow_builders_x / product_hunt / github_trending |
| source_item_id | text | 源内唯一 ID |
| title | text | 原始标题 |
| url | text | 原始链接 |
| published_at | timestamptz | 发布时间 |
| fetched_at | timestamptz | 抓取时间 |
| raw_json | jsonb | 完整源数据 |

唯一索引：

```sql
unique(source, source_item_id)
```

### 6.2 normalized_items

统一后的 item。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 主键 |
| raw_item_id | uuid | 对应 raw item |
| canonical_title | text | 标准标题 |
| canonical_url | text | 标准链接 |
| source | text | 来源 |
| source_category | text | 原始分类 |
| system_category | text | 产品/GitHub/模型技术/新闻观点 |
| summary | text | 原始或初步摘要 |
| body | text | 正文或 transcript |
| author_name | text | 作者/来源名 |
| published_at | timestamptz | 发布时间 |
| metrics | jsonb | votes/stars/likes 等 |
| metadata | jsonb | 语言、topics 等 |
| duplicate_group_id | uuid | 去重分组 |

### 6.3 source_summaries

专门保存长内容摘要，尤其 Follow Builders。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 主键 |
| normalized_item_id | uuid | item |
| model | text | 使用模型 |
| summary | text | 摘要 |
| key_points | jsonb | 要点数组 |
| generated_at | timestamptz | 生成时间 |

### 6.4 digests

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 主键 |
| date | date | 日报日期 |
| title | text | 标题 |
| markdown | text | Markdown 正文 |
| json | jsonb | 结构化正文 |
| model | text | 使用模型 |
| generated_at | timestamptz | 生成时间 |
| status | text | draft/published/failed |

## 7. Collector 设计

所有 collector 实现统一接口：

```ts
type CollectorResult = {
  source: string;
  fetchedAt: string;
  sourceGeneratedAt?: string;
  items: RawItemInput[];
  errors?: string[];
};

interface Collector {
  name: string;
  collect(params: CollectParams): Promise<CollectorResult>;
}
```

建议 collector：

```text
collectAihotItems()
collectFollowBuildersX()
collectFollowBuildersPodcasts()
collectFollowBuildersBlogs()
collectProductHuntTop10()
collectGithubTrendingWeekly()
```

每个 collector 独立失败，不能让一个源拖垮整份日报。

## 8. 去重和合并

第一版做简单去重：

1. URL 完全相同。
2. 标题规范化后相似度高。
3. Product Hunt 与 AI HOT 出现同一产品名。
4. GitHub repo URL 相同。
5. Follow Builders tweet 链接到同一产品或 repo。

建议用：

- URL canonicalization
- title lowercase + 去符号
- repo full_name 精确匹配
- 产品名精确/近似匹配

同一 duplicate group 内：

- 保留所有 source links。
- 主标题优先级：官方源 > Product Hunt > GitHub > AI HOT > X。
- metrics 合并。

## 9. AI Editor 设计

### 9.1 输入

AI editor 输入应是清洗后的 item list，不直接塞完整 raw JSON。

示例：

```json
{
  "date": "2026-05-26",
  "items": [
    {
      "title": "Unabyss",
      "url": "...",
      "source": "product_hunt",
      "summary": "...",
      "body_or_source_summary": "...",
      "metrics": {"votes": 520, "comments": 118},
      "metadata": {"topics": ["AI", "Productivity"]}
    }
  ]
}
```

### 9.2 输出

AI editor 输出 JSON + Markdown。

JSON schema：

```json
{
  "date": "2026-05-26",
  "sections": [
    {
      "key": "product",
      "title": "产品动态",
      "items": [
        {
          "title": "Unabyss",
          "url": "...",
          "sources": ["product_hunt"],
          "one_liner": "...",
          "features": "...",
          "target_users": "...",
          "user_need": "...",
          "why_it_matters": "...",
          "metrics": "520 votes / 118 comments"
        }
      ]
    }
  ]
}
```

### 9.3 AI 规则

必须遵守：

- 每条必须有 URL。
- 不得编造未出现在源数据里的事实。
- 目标用户和用户需求可以推断，但必须基于 tagline/description/source summary。
- 对爆料类信息标记“未官宣/传闻/报道”。
- 多源重复事件合并展示。
- 中文表达自然，不要机器翻译腔。

## 10. 日报输出格式

```md
# 每日 AI/产品/开源动态 - 2026-05-26

## 产品动态

1. [Unabyss](...)
   - 来源：Product Hunt
   - 热度：520 votes / 118 comments
   - 定位：...
   - 功能：...
   - 目标用户：...
   - 解决需求：...
   - 为什么值得看：...

## GitHub 动态

1. [owner/repo](...)
   - 语言：TypeScript
   - 热度：25.6k stars / 1.4k forks
   - 功能：...
   - 目标用户：...
   - 解决需求：...

## 模型/技术发展动态

## 新闻/观点
```

## 11. 调度策略

建议每日北京时间 16:00 生成日报。

理由：

- Product Hunt 使用 America/Los_Angeles 日期。
- 北京时间上午对应太平洋前一天晚上，数据可能还在变化。
- 16:00 北京时间更接近太平洋当天凌晨后，前一天榜单更稳定。

可选：

- 10:30 先生成 morning draft。
- 16:00 生成 final version。

MVP 只做 16:00 final version。

## 12. 环境变量

```text
PRODUCT_HUNT_TOKEN=...
OPENAI_API_KEY=...
DATABASE_URL=...
AIHOT_USER_AGENT=Mozilla/5.0 ... daily-ai-digest/0.1
```

注意：

- Product Hunt token 只放服务端。
- 不要进入前端 bundle。
- 不要写入日志。

## 13. API 设计

内部：

```text
POST /api/jobs/collect
POST /api/jobs/generate
POST /api/jobs/publish
```

公开：

```text
GET /api/public/daily
GET /api/public/daily/:date
GET /api/public/items?date=YYYY-MM-DD&category=product
GET /api/public/rss
```

管理/调试：

```text
GET /api/admin/source-status
GET /api/admin/raw-items?source=follow_builders_x&date=YYYY-MM-DD
```

## 14. 页面设计

MVP 页面：

1. 首页展示最新日报。
2. 历史日报列表。
3. 单篇日报页。
4. 每条显示来源链接。

不需要复杂 UI。重点是内容质量。

## 15. Follow Builders 研发实现细节

建议实现文件：

```text
src/collectors/followBuilders.ts
src/normalizers/followBuilders.ts
src/summarizers/followBuilders.ts
```

伪代码：

```ts
const FEEDS = {
  x: 'https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json',
  podcasts: 'https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-podcasts.json',
  blogs: 'https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-blogs.json',
};

export async function collectFollowBuildersX() {
  const feed = await fetchJson(FEEDS.x);
  const items = [];

  for (const builder of feed.x ?? []) {
    for (const tweet of builder.tweets ?? []) {
      items.push({
        source: 'follow_builders_x',
        sourceItemId: `x:${tweet.id}`,
        title: `${builder.name}: ${tweet.text.slice(0, 80)}`,
        url: tweet.url,
        publishedAt: tweet.createdAt,
        rawJson: { builder, tweet },
      });
    }
  }

  return {
    source: 'follow_builders_x',
    sourceGeneratedAt: feed.generatedAt,
    items,
  };
}
```

Podcast collector：

```ts
export async function collectFollowBuildersPodcasts() {
  const feed = await fetchJson(FEEDS.podcasts);
  return (feed.podcasts ?? []).map((episode) => ({
    source: 'follow_builders_podcast',
    sourceItemId: `podcast:${episode.guid ?? episode.url}`,
    title: episode.title,
    url: episode.url,
    publishedAt: episode.publishedAt,
    rawJson: episode,
  }));
}
```

Summarizer：

```ts
if (item.source === 'follow_builders_podcast') {
  // transcript 很长，先生成 source summary
  // 再交给全局 AI editor
}

if (item.source === 'follow_builders_x') {
  // 同一 builder 当天多条 tweet 可合并摘要
}
```

## 16. 验收标准

MVP 验收：

- 能每天成功抓取四个源。
- Follow Builders 不依赖本地 skill，可直接服务端抓 GitHub raw feed。
- Product Hunt 使用官方 API 返回前一天 Top 10。
- GitHub Trending 使用 RSSHub weekly。
- AI HOT 使用公开 API。
- 能生成四栏目中文日报。
- 每条都有 URL。
- 重复事件不会重复出现。
- 源失败时日报仍可生成，并在内部状态里标记失败源。
- 最新日报可通过网页和 API 访问。

## 17. 研发里程碑

### Milestone 1：Collector MVP

- 实现四个源 collector。
- raw_items 入库。
- source-status 可查看。

### Milestone 2：Normalizer + Deduper

- 统一字段。
- URL/title/repo 去重。
- normalized_items 入库。

### Milestone 3：AI Editor

- 实现 source summarizer。
- 实现四栏目日报生成。
- digests 入库。

### Milestone 4：Web + API

- 最新日报页面。
- 历史日报页面。
- public daily API。
- RSS 输出。

### Milestone 5：质量优化

- 增加源失败告警。
- 增加人工重新生成按钮。
- 增加 prompt 版本管理。

## 18. 推荐结论

Follow Builders 的正确抽象不是“在线运行 skill”，而是：

```text
Follow Builders GitHub raw feeds
  -> server-side collector
  -> normalized item store
  -> source summarizer
  -> global AI editor
```

这样它就和 AI HOT、Product Hunt、GitHub Trending 一样，成为统一数据管线里的一个 source provider。

第一版不要追求 Follow Builders 的完整原始 digest 效果，而要保留它的 item-level 信号：谁说了什么、链接是什么、热度如何、它应该归到哪个栏目。最终由统一 AI editor 来负责跨源整合和改写。
