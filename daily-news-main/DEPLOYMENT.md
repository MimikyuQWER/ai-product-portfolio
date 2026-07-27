# 部署说明

当前项目部署的是 Vite 前端 + Fastify 后端，不再使用旧版 GitHub Pages 静态站。

## Titan 沙箱

Supervisor 配置在 `.titan/supervisord/`：

- `backend.conf`：启动 `src/index.ts`，监听 `51031`
- `frontend.conf`：启动 Vite，监听 `51030`，并代理到后端 `51031`

HoYowave 回调应填写：

```text
https://<titan-domain>/api/wave/callback
```

## Docker

Dockerfile 会先编译后端，再构建 `frontend/dist`，运行时使用：

```bash
node dist/index.js
```

生产容器内后端会直接服务 `frontend/dist`。

## 必要环境变量

```text
JWT_SECRET=
PORT=
DATABASE_PATH=
```

Wave 机器人相关：

```text
WAVE_APP_ID=
WAVE_APP_SECRET=
WAVE_AES_KEY=
WAVE_SIGN_TOKEN=
WAVE_API_BASE_URL=https://open.hoyowave.com
DAILY_VIEW_BASE_URL=
```

这些值只放部署环境或未提交的 `.env`，不要写入仓库。

## 验证

```bash
npm run build:all
```

本地开发：

```bash
JWT_SECRET=local-dev-secret PORT=3456 npm run dev
npm run dev:frontend
```

访问：

```text
http://localhost:5173/generation
```
