import 'dotenv/config';
import fs from 'fs';
import path from 'path';

/**
 * 将 AI 日报推送到飞书自定义机器人 Webhook
 *
 * 使用方式：
 *   npx tsx src/scripts/pushToFeishu.ts --date=2026-07-29
 *   npx tsx src/scripts/pushToFeishu.ts                  # 默认今天
 *
 * 环境变量：
 *   FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
 */

function getArg(name: string): string | undefined {
  const prefix = `--${name}=`;
  const found = process.argv.find((arg) => arg.startsWith(prefix));
  return found ? found.slice(prefix.length) : undefined;
}

function getTodayShanghai(): string {
  const now = new Date();
  const shanghai = new Date(now.getTime() + 8 * 3600 * 1000);
  return shanghai.toISOString().slice(0, 10);
}

function extractSections(markdown: string): { summary: string; highlights: string[]; sections: { title: string; items: string[] }[] } {
  const lines = markdown.split('\n');

  // 提取摘要
  let summary = '';
  let inSummary = false;
  for (const line of lines) {
    if (line.startsWith('```') && inSummary) break;
    if (inSummary) summary += line.trim() + '\n';
    if (line.startsWith('```') && !inSummary) inSummary = true;
  }

  // 提取各栏目头条（取每个 ## 栏目的前 3 条）
  const highlights: string[] = [];
  const sections: { title: string; items: string[] }[] = [];
  let currentSection = '';
  let currentItems: string[] = [];

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (currentSection && currentItems.length > 0) {
        sections.push({ title: currentSection, items: currentItems.slice(0, 3) });
      }
      currentSection = line.replace('## ', '').trim();
      currentItems = [];
    }
    // 匹配 "1. **[标题]" 格式
    const itemMatch = line.match(/^\d+\.\s+\*\*\[(.+?)\]\((.+?)\)\*\*/);
    if (itemMatch && currentSection) {
      currentItems.push(itemMatch[1]);
      if (highlights.length < 12) {
        highlights.push(`${itemMatch[1]}（${currentSection}）`);
      }
    }
  }
  if (currentSection && currentItems.length > 0) {
    sections.push({ title: currentSection, items: currentItems.slice(0, 3) });
  }

  return { summary: summary.trim(), highlights: highlights.slice(0, 12), sections };
}

function buildFeishuCard(date: string, markdown: string, viewUrl: string): object {
  const { summary, highlights } = extractSections(markdown);

  const highlightText = highlights.length > 0
    ? highlights.map((h, i) => `${i + 1}. ${h}`).join('\n')
    : '今日 AI 资讯已生成，请查看完整日报。';

  return {
    msg_type: 'interactive',
    card: {
      header: {
        title: { tag: 'plain_text', content: `📰 AI 资讯日报 ${date}` },
        template: 'blue',
      },
      elements: [
        {
          tag: 'markdown',
          content: `**📋 今日摘要**\n${summary || '今日 AI 资讯已生成'}`,
        },
        {
          tag: 'hr',
        },
        {
          tag: 'markdown',
          content: `🔥 **今日热点**\n${highlightText}`,
        },
        {
          tag: 'action',
          actions: [
            {
              tag: 'button',
              text: { tag: 'plain_text', content: '📖 查看完整日报' },
              type: 'primary',
              url: viewUrl,
            },
          ],
        },
        {
          tag: 'note',
          elements: [
            { tag: 'plain_text', content: '🤖 由 PrismFlowAgent (流光) 自动生成' },
          ],
        },
      ],
    },
  };
}

function buildFallbackText(date: string, markdown: string): string {
  const { summary, highlights } = extractSections(markdown);

  const lines = [
    `📰 AI 资讯日报 ${date}`,
    '',
    `📋 今日摘要：`,
    summary || '今日 AI 资讯已生成',
    '',
    '🔥 今日热点：',
    ...(highlights.length > 0 ? highlights.map((h, i) => `${i + 1}. ${h}`) : ['暂无']),
  ];

  return lines.join('\n');
}

async function main() {
  const webhookUrl = process.env.FEISHU_WEBHOOK_URL;
  if (!webhookUrl) {
    console.error('[push:feishu] 请在 .env 中设置 FEISHU_WEBHOOK_URL');
    console.error('  获取方式：飞书群 → 设置 → 群机器人 → 添加自定义机器人 → 复制 Webhook 地址');
    process.exit(1);
  }

  const date = getArg('date') || getTodayShanghai();
  const dailyFile = path.resolve(`daily/${date}.md`);

  if (!fs.existsSync(dailyFile)) {
    console.error(`[push:feishu] 日报文件不存在: ${dailyFile}`);
    console.error('  请先运行: npm run daily:rss -- --date=' + date);
    process.exit(1);
  }

  const markdown = fs.readFileSync(dailyFile, 'utf-8');
  const viewBaseUrl = process.env.DAILY_VIEW_BASE_URL || 'http://localhost:5173';
  const viewUrl = `${viewBaseUrl}/generation?date=${date}`;

  try {
    // 优先使用卡片消息
    const card = buildFeishuCard(date, markdown, viewUrl);
    const cardResponse = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(card),
    });

    const cardResult = await cardResponse.json() as any;

    if (cardResult.code === 0 || cardResult.StatusCode === 0) {
      console.log(`[push:feishu] ✅ 卡片消息推送成功 (${date})`);
    } else {
      // 卡片失败时降级为文本消息
      console.warn(`[push:feishu] 卡片消息失败: ${JSON.stringify(cardResult)}，降级为文本`);
      const text = buildFallbackText(date, markdown);
      const textResponse = await fetch(webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ msg_type: 'text', content: { text } }),
      });
      const textResult = await textResponse.json() as any;
      if (textResult.code === 0 || textResult.StatusCode === 0) {
        console.log(`[push:feishu] ✅ 文本消息推送成功 (${date})`);
      } else {
        console.error(`[push:feishu] ❌ 推送失败: ${JSON.stringify(textResult)}`);
        process.exit(1);
      }
    }
  } catch (err: any) {
    console.error(`[push:feishu] ❌ 请求失败: ${err.message}`);
    process.exit(1);
  }
}

main();
