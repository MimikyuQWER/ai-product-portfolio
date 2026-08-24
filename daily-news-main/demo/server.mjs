import http from 'node:http';
import { createReadStream, existsSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import dotenv from 'dotenv';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(ROOT, '.env') });

const DEFAULT_URL = 'https://api.deepseek.com';
const DEFAULT_MODEL = 'deepseek-chat';
const MAX_BODY_BYTES = 700 * 1024;
const AI_TIMEOUT_MS = 75_000;
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.avif': 'image/avif',
};

export function getPublicConfig(env = process.env) {
  return {
    configured: Boolean(env.AI_API_KEY?.trim()),
    provider: 'OpenAI-compatible',
    model: env.AI_MODEL?.trim() || DEFAULT_MODEL,
    baseUrl: env.AI_API_URL?.trim() || DEFAULT_URL,
  };
}

export function splitMarkdownSections(markdown) {
  const matches = [...markdown.matchAll(/^##\s+.+$/gm)];
  if (!matches.length) return [{ title: '全文', content: markdown }];
  const result = [];
  if ((matches[0].index || 0) > 0) {
    result.push({ title: '导语', content: markdown.slice(0, matches[0].index) });
  }
  matches.forEach((match, index) => {
    const start = match.index || 0;
    const end = matches[index + 1]?.index ?? markdown.length;
    result.push({ title: match[0].replace(/^##\s+/, ''), content: markdown.slice(start, end) });
  });
  return result;
}

export function safeResolve(root, requestPath) {
  let decoded;
  try {
    decoded = decodeURIComponent(requestPath.split('?')[0]);
  } catch {
    return null;
  }
  const normalized = decoded.replace(/^[/\\]+/, '');
  const resolved = path.resolve(root, normalized);
  const relative = path.relative(path.resolve(root), resolved);
  if (relative.startsWith('..') || path.isAbsolute(relative)) return null;
  return resolved;
}

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload),
    'Cache-Control': 'no-store',
  });
  res.end(payload);
}

function sendImagePlaceholder(res) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630"><rect width="1200" height="630" fill="#f0f0ec"/><rect x="420" y="205" width="360" height="220" rx="18" fill="none" stroke="#c5c5bd" stroke-width="4"/><circle cx="515" cy="285" r="30" fill="#c5c5bd"/><path d="M445 390l115-110 75 70 48-46 72 86z" fill="#c5c5bd"/><text x="600" y="490" text-anchor="middle" fill="#777770" font-family="Arial,sans-serif" font-size="28">历史图片未随快照保留</text></svg>`;
  res.writeHead(200, {
    'Content-Type': 'image/svg+xml; charset=utf-8',
    'Content-Length': Buffer.byteLength(svg),
    'Cache-Control': 'public, max-age=86400',
    'X-Demo-Asset-Fallback': 'true',
    'X-Content-Type-Options': 'nosniff',
  });
  res.end(svg);
}

async function readJson(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > MAX_BODY_BYTES) {
      const error = new Error('请求内容超过 700 KB 限制');
      error.status = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    const error = new Error('请求体必须是有效 JSON');
    error.status = 400;
    throw error;
  }
}

function cleanModelMarkdown(value) {
  const text = String(value || '').trim();
  const fenced = text.match(/^```(?:markdown|md)?\s*\n([\s\S]*?)\n```$/i);
  return (fenced ? fenced[1] : text).trimEnd();
}

async function polishSection(section, config, fetchImpl = fetch) {
  const endpoint = `${config.baseUrl.replace(/\/+$/, '')}/v1/chat/completions`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), AI_TIMEOUT_MS);
  try {
    const response = await fetchImpl(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${process.env.AI_API_KEY}`,
      },
      signal: controller.signal,
      body: JSON.stringify({
        model: config.model,
        temperature: 0.25,
        messages: [
          {
            role: 'system',
            content: [
              '你是严谨的中文科技资讯编辑。请润色输入的 Markdown 章节，使中文更自然、摘要更凝练。',
              '必须完整保留所有事实、数字、专有名词、Markdown 标题层级、链接 URL、图片路径、引用和列表结构。',
              '不得增加未经原文支持的信息，不得删除新闻条目，不得把链接或图片改写成纯文本。',
              '只输出润色后的 Markdown，不要解释，不要使用代码围栏。',
            ].join('\n'),
          },
          { role: 'user', content: section.content },
        ],
      }),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`上游接口返回 ${response.status}${detail ? `：${detail.slice(0, 120)}` : ''}`);
    }
    const data = await response.json();
    const content = data?.choices?.[0]?.message?.content;
    if (!content) throw new Error('上游接口未返回正文');
    return cleanModelMarkdown(content);
  } finally {
    clearTimeout(timeout);
  }
}

export async function polishMarkdown(markdown, config, onEvent = () => {}, fetchImpl = fetch) {
  const sections = splitMarkdownSections(markdown);
  const output = [];
  const failures = [];
  onEvent({ type: 'start', total: sections.length });
  for (let index = 0; index < sections.length; index += 1) {
    const section = sections[index];
    try {
      const polished = await polishSection(section, config, fetchImpl);
      output.push(polished);
      onEvent({ type: 'progress', current: index + 1, total: sections.length, title: section.title });
    } catch (error) {
      output.push(section.content.trimEnd());
      failures.push(section.title);
      onEvent({ type: 'warning', current: index + 1, total: sections.length, title: section.title, message: error.name === 'AbortError' ? '请求超时，已保留原文' : '处理失败，已保留原文' });
    }
  }
  return { markdown: output.join('\n\n').trimEnd() + '\n', failures };
}

function writeNdjson(res, event) {
  res.write(`${JSON.stringify(event)}\n`);
}

async function handlePolish(req, res) {
  const config = getPublicConfig();
  if (!config.configured) {
    sendJson(res, 503, { error: 'AI 尚未配置，请先复制 .env.example 为 .env 并填写 AI_API_KEY。' });
    return;
  }
  let body;
  try {
    body = await readJson(req);
  } catch (error) {
    sendJson(res, error.status || 400, { error: error.message });
    return;
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(body?.date || '') || typeof body?.markdown !== 'string' || !body.markdown.trim()) {
    sendJson(res, 400, { error: 'date 或 markdown 参数无效。' });
    return;
  }
  res.writeHead(200, {
    'Content-Type': 'application/x-ndjson; charset=utf-8',
    'Cache-Control': 'no-store',
    Connection: 'keep-alive',
    'X-Content-Type-Options': 'nosniff',
  });
  try {
    const result = await polishMarkdown(body.markdown, config, (event) => writeNdjson(res, event));
    writeNdjson(res, { type: 'complete', ...result });
  } catch {
    writeNdjson(res, { type: 'error', message: 'AI 润色未完成，请稍后重试。' });
  }
  res.end();
}

async function serveFile(res, filePath, cache = false) {
  try {
    const info = await stat(filePath);
    if (!info.isFile()) return false;
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream',
      'Content-Length': info.size,
      'Cache-Control': cache ? 'public, max-age=86400' : 'no-cache',
      'X-Content-Type-Options': 'nosniff',
    });
    createReadStream(filePath).pipe(res);
    return true;
  } catch {
    return false;
  }
}

export async function createAppServer({ dev = false } = {}) {
  const vite = dev
    ? await (await import('vite')).createServer({ root: ROOT, server: { middlewareMode: true }, appType: 'spa' })
    : null;
  return http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', 'http://localhost');
    if (req.method === 'GET' && url.pathname === '/api/health') {
      sendJson(res, 200, { ok: true, demo: true });
      return;
    }
    if (req.method === 'GET' && url.pathname === '/api/config/status') {
      sendJson(res, 200, getPublicConfig());
      return;
    }
    if (req.method === 'POST' && url.pathname === '/api/ai/polish') {
      await handlePolish(req, res);
      return;
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      sendJson(res, 405, { error: 'Method not allowed' });
      return;
    }

    if (url.pathname.startsWith('/daily/') || url.pathname.startsWith('/daily-assets/') || url.pathname === '/daily-index.json') {
      const target = safeResolve(path.join(ROOT, 'public'), url.pathname);
      if (!target) {
        sendJson(res, 404, { error: '资源不存在' });
      } else if (!(await serveFile(res, target, url.pathname.startsWith('/daily-assets/')))) {
        if (url.pathname.startsWith('/daily-assets/')) sendImagePlaceholder(res);
        else sendJson(res, 404, { error: '资源不存在' });
      }
      return;
    }
    if (vite) {
      vite.middlewares(req, res, () => sendJson(res, 404, { error: '页面不存在' }));
      return;
    }
    const dist = path.join(ROOT, 'dist');
    const target = safeResolve(dist, url.pathname === '/' ? 'index.html' : url.pathname);
    if (target && (await serveFile(res, target))) return;
    await serveFile(res, path.join(dist, 'index.html')) || sendJson(res, 404, { error: '请先运行 npm run build' });
  });
}

async function main() {
  const dev = process.argv.includes('--dev');
  const host = process.env.HOST?.trim() || '127.0.0.1';
  const port = Number(process.env.PORT || (dev ? 5173 : 4173));
  const server = await createAppServer({ dev });
  server.listen(port, host, () => {
    const mode = dev ? '开发' : '生产';
    console.log(`AI 资讯日报 Demo（${mode}模式）已启动：http://${host}:${port}`);
    console.log(`AI 润色：${getPublicConfig().configured ? '已配置' : '未配置（快照浏览不受影响）'}`);
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : '服务启动失败');
    process.exitCode = 1;
  });
}
