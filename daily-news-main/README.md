# Daily News

AI daily news dashboard and generator.

The active application has two parts:

- Backend: Fastify + TypeScript, entrypoint `src/index.ts`
- Frontend: Vite + React, source under `frontend/`

Legacy native HTTP/static-page entrypoints have been removed. Do not use `src/server.js`, `src/cli.js`, `public/`, or `src/static/`; they are intentionally no longer part of this project.

## Local Development

```bash
npm install
npm --prefix frontend install
JWT_SECRET=local-dev-secret PORT=3456 npm run dev
```

In another terminal:

```bash
npm run dev:frontend
```

Open:

```text
http://localhost:5173/generation
```

The frontend dev server proxies `/api`, `/daily`, and `/daily-assets` to the backend port.

## Build

```bash
npm run build
npm run build:frontend
```

or:

```bash
npm run build:all
```

## Daily Content

Generate RSS-based daily markdown:

```bash
npm run daily:rss
```

Generated markdown lives in `daily/`; generated images live in `daily-assets/`.

## Titan

Titan supervisor starts:

- Backend: `npx tsx --watch src/index.ts` on `PORT=51031`
- Frontend: `npx vite --port 51030 --host 0.0.0.0`

The backend also serves the production frontend build from `frontend/dist` when running from Docker.

## Wave Callback

Callback route:

```text
POST /api/wave/callback
```

Deploy-time environment variables:

```text
WAVE_APP_ID=
WAVE_APP_SECRET=
WAVE_AES_KEY=
WAVE_SIGN_TOKEN=
WAVE_API_BASE_URL=https://open.hoyowave.com
DAILY_VIEW_BASE_URL=
```

Do not commit real secrets. The app can also save Wave config through `/api/wave/config`; saved config overrides environment values.
