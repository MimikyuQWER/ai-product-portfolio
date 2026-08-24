import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (await Promise.all(entries.map((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(target) : [target];
  }))).flat();
}

test('快照数量与日期索引完整', async () => {
  const daily = (await walk(path.join(root, 'public', 'daily'))).filter((file) => file.endsWith('.md'));
  const index = JSON.parse(await readFile(path.join(root, 'public', 'daily-index.json'), 'utf8'));
  assert.equal(daily.length, 19);
  assert.equal(index.dates.length, 18);
  assert.deepEqual(index.archives, ['2026-05-29-v2.md']);
  for (const date of index.dates) assert.ok(existsSync(path.join(root, 'public', 'daily', `${date}.md`)), `缺少 ${date}.md`);
});

test('401 个原始图片资源均保留，遗留缺图范围仅限 2026-05-27', async () => {
  const assets = await walk(path.join(root, 'public', 'daily-assets'));
  const daily = (await walk(path.join(root, 'public', 'daily'))).filter((file) => file.endsWith('.md'));
  assert.equal(assets.length, 401);
  const missing = new Set();
  for (const file of daily) {
    const markdown = await readFile(file, 'utf8');
    const references = [
      ...markdown.matchAll(/!\[[^\]]*\]\((\/daily-assets\/[^)\s]+)(?:\s+"[^"]*")?\)/g),
      ...markdown.matchAll(/<img[^>]+src=["'](\/daily-assets\/[^"']+)["']/g),
    ];
    for (const match of references) {
      const target = path.join(root, 'public', decodeURIComponent(match[1]).replace(/^[/\\]+/, ''));
      if (!existsSync(target)) missing.add(`${path.basename(file)} → ${match[1]}`);
    }
  }
  assert.equal(missing.size, 20);
  assert.ok([...missing].every((item) => item.includes('2026-05-27.md → /daily-assets/2026-05-27/')));
});

test('Demo 不包含真实密钥或敏感业务文件', async () => {
  const files = (await walk(root)).filter((file) => !file.includes(`${path.sep}node_modules${path.sep}`) && !file.includes(`${path.sep}dist${path.sep}`));
  const forbiddenNames = /(?:^|[\\/])(?:\.env|.*\.sqlite3?|.*\.db|.*\.log|PRD[^\\/]*)$/i;
  const forbiddenSecret = /\bsk-[A-Za-z0-9_-]{16,}\b/g;
  const violations = [];
  for (const file of files) {
    const relative = path.relative(root, file);
    if (relative !== '.env.example' && forbiddenNames.test(file)) violations.push(relative);
    if (/\.(?:md|mjs|js|jsx|ts|tsx|json|html|css|env|example)$/i.test(file)) {
      const text = await readFile(file, 'utf8');
      if (forbiddenSecret.test(text)) violations.push(`${relative}:secret`);
      forbiddenSecret.lastIndex = 0;
    }
  }
  assert.deepEqual(violations, []);
});

test('2026-08-24 快照符合中文日报格式约束且无抓取乱码', async () => {
  const markdown = await readFile(path.join(root, 'public', 'daily', '2026-08-24.md'), 'utf8');
  const entries = [...markdown.matchAll(/^\d+\.\s+\*\*\[/gm)].length;
  const why = [...markdown.matchAll(/\*\*为什么重要：\*\*/g)].length;
  const tags = [...markdown.matchAll(/^\s+标签：/gm)].length;
  assert.equal(entries, 33);
  assert.equal(why, entries);
  assert.equal(tags, entries);
  assert.doesNotMatch(markdown, /iframe|frameborder|allowfullscreen|padding:0|AI''s|Vercel''s|�/i);
});
