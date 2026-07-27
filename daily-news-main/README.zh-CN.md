# 每日 AI 动态

当前有效应用由两部分组成：

- 后端：Fastify + TypeScript，入口 `src/index.ts`
- 前端：Vite + React，代码在 `frontend/`

旧版原生 HTTP 服务和静态页面已经移除。不要再使用 `src/server.js`、`src/cli.js`、`public/` 或 `src/static/`。

## 本地开发

```bash
npm install
npm --prefix frontend install
JWT_SECRET=local-dev-secret PORT=3456 npm run dev
```

另开一个终端：

```bash
npm run dev:frontend
```

打开：

```text
http://localhost:5173/generation
```

前端 dev server 会把 `/api`、`/daily`、`/daily-assets` 代理到后端端口。

## 构建

```bash
npm run build:all
```

## 日报生成

```bash
npm run daily:rss
```

日报 Markdown 输出在 `daily/`，图片资源输出在 `daily-assets/`。

## Titan

Titan supervisor 当前启动：

- 后端：`npx tsx --watch src/index.ts`，`PORT=51031`
- 前端：`npx vite --port 51030 --host 0.0.0.0`

Docker 生产模式下，后端会从 `frontend/dist` 提供前端构建产物。

## Wave 回调

回调地址：

```text
POST /api/wave/callback
```

部署环境变量：

```text
WAVE_APP_ID=
WAVE_APP_SECRET=
WAVE_AES_KEY=
WAVE_SIGN_TOKEN=
WAVE_API_BASE_URL=https://open.hoyowave.com
DAILY_VIEW_BASE_URL=
```

不要把真实密钥提交到仓库。也可以通过 `/api/wave/config` 保存配置，数据库配置会覆盖环境变量。
