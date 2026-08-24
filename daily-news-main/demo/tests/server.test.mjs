import assert from 'node:assert/strict';
import path from 'node:path';
import test from 'node:test';
import { createAppServer, getPublicConfig, polishMarkdown, safeResolve, splitMarkdownSections } from '../server.mjs';

test('按二级标题拆分，并保留导语', () => {
  const input = '# 日报\n\n导语\n\n## 新闻\n正文\n\n## 产品\n内容\n';
  const sections = splitMarkdownSections(input);
  assert.equal(sections.length, 3);
  assert.equal(sections[0].title, '导语');
  assert.match(sections[1].content, /^## 新闻/);
  assert.match(sections[2].content, /^## 产品/);
});

test('没有二级标题时按全文处理', () => {
  const sections = splitMarkdownSections('# 只有标题\n正文');
  assert.deepEqual(sections, [{ title: '全文', content: '# 只有标题\n正文' }]);
});

test('静态资源路径不能越出根目录', () => {
  const root = path.resolve('public');
  assert.equal(safeResolve(root, '/../server.mjs'), null);
  assert.equal(safeResolve(root, '/%2e%2e/server.mjs'), null);
  assert.equal(safeResolve(root, '/daily/2026-08-24.md'), path.join(root, 'daily', '2026-08-24.md'));
});

test('公开配置只含脱敏状态，不泄露密钥', () => {
  const config = getPublicConfig({ AI_API_KEY: 'secret-value', AI_API_URL: 'http://localhost:9999', AI_MODEL: 'mock' });
  assert.deepEqual(config, { configured: true, provider: 'OpenAI-compatible', model: 'mock', baseUrl: 'http://localhost:9999' });
  assert.equal(JSON.stringify(config).includes('secret-value'), false);
});

test('AI 单章节失败时保留原文并继续合并', async () => {
  const input = '## 成功章节\n原文 A\n\n## 失败章节\n原文 B\n';
  let calls = 0;
  const fetchMock = async () => {
    calls += 1;
    if (calls === 2) return new Response('mock failed', { status: 500 });
    return Response.json({ choices: [{ message: { content: '## 成功章节\n润色 A' } }] });
  };
  const events = [];
  const oldKey = process.env.AI_API_KEY;
  process.env.AI_API_KEY = 'mock-key';
  try {
    const result = await polishMarkdown(input, { configured: true, provider: 'OpenAI-compatible', model: 'mock', baseUrl: 'http://mock.local' }, (event) => events.push(event), fetchMock);
    assert.match(result.markdown, /润色 A/);
    assert.match(result.markdown, /## 失败章节\n原文 B/);
    assert.deepEqual(result.failures, ['失败章节']);
    assert.ok(events.some((event) => event.type === 'warning'));
  } finally {
    if (oldKey === undefined) delete process.env.AI_API_KEY;
    else process.env.AI_API_KEY = oldKey;
  }
});

test('历史失效图片由本地占位图兜底而非返回 404', async () => {
  const server = await createAppServer();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const address = server.address();
    const response = await fetch(`http://127.0.0.1:${address.port}/daily-assets/2026-05-27/missing.png`);
    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /^image\/svg\+xml/);
    assert.equal(response.headers.get('x-demo-asset-fallback'), 'true');
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});

test('日报不使用长期缓存，图片资源可以缓存', async () => {
  const server = await createAppServer();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const address = server.address();
    const origin = `http://127.0.0.1:${address.port}`;
    const daily = await fetch(`${origin}/daily/2026-08-24.md`);
    const image = await fetch(`${origin}/daily-assets/2026-05-27/missing.png`);
    assert.equal(daily.headers.get('cache-control'), 'no-cache');
    assert.match(image.headers.get('cache-control'), /max-age=86400/);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});
