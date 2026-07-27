import fs from 'fs';
import path from 'path';
import { LogService } from '../services/LogService.js';
import { WaveService } from '../plugins/builtin/publishers/wave/WaveService.js';
import { WavePublisher } from '../plugins/builtin/publishers/wave/WavePublisher.js';

const getDailyViewUrl = () => process.env.WAVE_DAILY_VIEW_URL || process.env.DAILY_VIEW_URL || process.env.PUBLIC_BASE_URL || '';

const SECTION_ICONS: Record<string, string> = {
  'OpenAI / Google / Anthropic 公司动态': '🏢',
  '公司动态': '🏢',
  '每日产品': '📦',
  'GitHub 项目': '⭐',
  '论文与模型': '📝',
  '从业者观点': '💬',
  '社区热点': '🌐',
};

// 这些分类展示全部条目 + 完整描述；其他分类精简（前3条 + 短描述）
const FULL_SECTIONS = ['OpenAI / Google / Anthropic 公司动态', '公司动态', '每日产品', 'GitHub 项目'];

interface DailyDigest {
  title: string;
  sections: { name: string; icon: string; items: { title: string; desc: string; url: string; imagePath?: string }[]; total: number }[];
  totalCount: number;
}

// 需要展示图片的分类
const IMAGE_SECTIONS = ['每日产品'];

export function parseDailyDigest(markdown: string, date: string): DailyDigest {
  const title = markdown.match(/^#\s+(.+)$/m)?.[1] || `AI 资讯日报 ${date}`;

  const sectionRegex = /^## (.+)$/gm;
  const sectionPos: { name: string; start: number }[] = [];
  let match;
  while ((match = sectionRegex.exec(markdown)) !== null) {
    if (match[1] === '今日摘要') continue;
    sectionPos.push({ name: match[1], start: match.index });
  }

  const sections: DailyDigest['sections'] = [];
  let totalCount = 0;

  for (let i = 0; i < sectionPos.length; i++) {
    const start = sectionPos[i].start;
    const end = i + 1 < sectionPos.length ? sectionPos[i + 1].start : markdown.length;
    const content = markdown.slice(start, end);

    const entries = [...content.matchAll(/^\d+\.\s+\*\*\[([^\]]+)\]\(([^)]+)\)/gm)];
    if (entries.length === 0) continue;

    const sectionName = sectionPos[i].name;
    const isFull = FULL_SECTIONS.includes(sectionName);
    // 完整分类：全部条目；精简分类：前 3 条
    const pickEntries = isFull ? entries : entries.slice(0, 3);

    const items: { title: string; desc: string; url: string; imagePath?: string }[] = [];
    const withImage = IMAGE_SECTIONS.includes(sectionName);
    for (const entry of pickEntries) {
      const entryTitle = entry[1];
      const entryUrl = entry[2];
      const titlePos = content.indexOf(entry[0], (entry.index || 0) - start);
      // 取到下一条目之前的区块，用于提取描述和图片
      const blockEnd = content.indexOf('\n\n', titlePos + entry[0].length);
      const block = content.slice(titlePos, titlePos + 1200);
      const afterTitle = content.slice(titlePos + entry[0].length, titlePos + entry[0].length + 800);
      const descMatch = afterTitle.match(/\n\n\s+(.+?)(?:\n|$)/);
      let desc = '';
      if (descMatch && !descMatch[1].includes('为什么重要') && !descMatch[1].includes('标签')) {
        desc = descMatch[1].replace(/\*\*/g, '').trim();
        // 精简分类截 50 字；完整分类不截断
        if (!isFull && desc.length > 50) desc = desc.slice(0, 47) + '...';
      }
      let imagePath: string | undefined;
      if (withImage) {
        const imgMatch = block.match(/!\[[^\]]*\]\((\/daily-assets\/[^)]+)\)/);
        if (imgMatch) imagePath = imgMatch[1];
      }
      items.push({ title: entryTitle, desc, url: entryUrl, imagePath });
    }

    sections.push({
      name: sectionName,
      icon: SECTION_ICONS[sectionName] || '📌',
      items,
      total: entries.length,
    });
    totalCount += entries.length;
  }

  return { title, sections, totalCount };
}

/**
 * 上传本地图片到 Wave，返回 file_key（失败返回 null）
 * avif 等格式会先转成 png
 */
async function uploadImageToWave(localPath: string): Promise<string | null> {
  try {
    const fullPath = path.resolve(process.cwd(), localPath.replace(/^\//, ''));
    if (!fs.existsSync(fullPath)) return null;

    // 转成 png（Wave 不识别 avif/svg 显示）
    const sharp = (await import('sharp')).default;
    const pngBuffer = await sharp(fullPath).png().toBuffer();

    const token = process.env.__WAVE_TOKEN__ || '';
    if (!token) return null;

    const form = new FormData();
    form.append('file', new Blob([new Uint8Array(pngBuffer)], { type: 'image/png' }), 'image.png');

    const apiBase = process.env.WAVE_API_BASE_URL || 'https://open.hoyowave.com';
    const resp = await fetch(`${apiBase}/openapi/file/v1/upload`, {
      method: 'POST',
      headers: { Authorization: token },
      body: form as any,
    });
    const data = await resp.json() as any;
    if (data.retcode === 0 && data.data?.file_key) {
      return data.data.file_key;
    }
    return null;
  } catch (err: any) {
    LogService.error(`Wave image upload failed for ${localPath}: ${err.message}`);
    return null;
  }
}

/**
 * 构建 Wave 日报卡片 JSON
 * 注意：Wave 卡片组件数量上限约 20 个，需控制 element 总数
 * 策略：每个分类的文字合并成 1 个 markdown；每日产品图片单独放（最多 MAX_IMAGES 张）
 */
const MAX_PRODUCT_IMAGES = 5;

export async function buildDailyCard(digest: DailyDigest, viewUrl: string): Promise<object> {
  const elements: any[] = [];

  for (const section of digest.sections) {
    const isImageSection = IMAGE_SECTIONS.includes(section.name);

    if (isImageSection) {
      // 每日产品：标题独立 + 前 N 条图文穿插，其余条目合并到一个 markdown
      elements.push({ tag: 'markdown', text: `**${section.icon} ${section.name}**` });
      let imgCount = 0;
      const restLines: string[] = [];
      for (const item of section.items) {
        const titleLine = item.url ? `[${item.title}](${item.url})` : `**${item.title}**`;
        const descLine = item.desc ? `\n<font color="comment">${item.desc}</font>` : '';
        if (item.imagePath && imgCount < MAX_PRODUCT_IMAGES) {
          const fileKey = await uploadImageToWave(item.imagePath);
          if (fileKey) {
            elements.push({ tag: 'markdown', text: `${titleLine}${descLine}` });
            elements.push({ tag: 'image', image_url: fileKey, mode: 'horizontal' });
            imgCount++;
            continue;
          }
        }
        // 无图或超过图片上限的，归入合并列表
        restLines.push(`${titleLine}${descLine}`);
      }
      if (restLines.length > 0) {
        elements.push({ tag: 'markdown', text: restLines.join('\n\n') });
      }
    } else {
      // 其他分类：所有条目合并成 1 个 markdown 组件（节省组件数）
      const lines = section.items.map((item) => {
        const titleLine = item.url ? `[${item.title}](${item.url})` : `**${item.title}**`;
        const descLine = item.desc ? `\n<font color="comment">${item.desc}</font>` : '';
        return `${titleLine}${descLine}`;
      });
      const more = section.total > section.items.length ? `\n<font color="comment">...等 ${section.total} 条</font>` : '';
      elements.push({
        tag: 'markdown',
        text: `**${section.icon} ${section.name}**\n\n${lines.join('\n\n')}${more}`,
      });
    }
  }

  elements.push({
    tag: 'markdown',
    text: `━━━━━━━━━━━━━━━━\n📊 今日共 **${digest.totalCount}** 条 AI 资讯`,
  });

  if (viewUrl) {
    elements.push({
      tag: 'button',
      text: '📖 查看完整图文日报',
      style: 'primary',
      option: {
        tag: 'url',
        multi_url: { url: viewUrl, ios_url: viewUrl, android_url: viewUrl },
      },
    });
  }

  return {
    header: { title: `📰 ${digest.title}`, template: 'blue' },
    card: { tag: 'column', elements },
    config: { disable_forward: false },
    ...(viewUrl ? { card_action: { url: viewUrl, ios_url: viewUrl, android_url: viewUrl } } : {}),
  };
}

function createWaveService(): WaveService | null {
  const appId = process.env.WAVE_APP_ID;
  const appSecret = process.env.WAVE_APP_SECRET;
  const aesKey = process.env.WAVE_AES_KEY;
  const signToken = process.env.WAVE_SIGN_TOKEN;
  if (!appId || !appSecret || !aesKey || !signToken) {
    return null;
  }
  return new WaveService({
    appId,
    appSecret,
    aesKey,
    signToken,
    apiBaseUrl: process.env.WAVE_API_BASE_URL || 'https://open.hoyowave.com',
  });
}

/**
 * 推送日报卡片到所有订阅者（应用机器人）
 */
export async function pushDailyToWave(date?: string): Promise<{ success: boolean; message: string }> {
  const targetDate = date || new Date().toISOString().split('T')[0];
  const dailyDir = path.resolve(process.cwd(), 'daily');
  const filePath = path.join(dailyDir, `${targetDate}.md`);

  if (!fs.existsSync(filePath)) {
    const msg = `Daily file not found: ${filePath}`;
    LogService.error(msg);
    return { success: false, message: msg };
  }

  const waveService = createWaveService();
  if (!waveService) {
    const msg = 'Wave app credentials not configured';
    LogService.error(msg);
    return { success: false, message: msg };
  }

  const markdown = fs.readFileSync(filePath, 'utf-8');
  const digest = parseDailyDigest(markdown, targetDate);
  const viewUrl = getDailyViewUrl();

  // 预先获取 token 供图片上传使用
  try {
    process.env.__WAVE_TOKEN__ = await waveService.getAccessToken();
  } catch {
    LogService.error('Wave: failed to get token for image upload');
  }

  const card = await buildDailyCard(digest, viewUrl);

  // 获取订阅者列表（通过 WavePublisher 访问数据库）
  const { ServiceContext } = await import('../services/ServiceContext.js');
  let store = ServiceContext.getCurrent()?.getStore();
  if (!store) {
    // 命令行独立运行时，初始化一个 store
    const { LocalStore } = await import('../services/LocalStore.js');
    store = new LocalStore();
    await store.init();
  }

  const publisher = new WavePublisher(store);
  const subscribers = await publisher.getSubscribers();

  if (subscribers.length === 0) {
    LogService.info('Wave: no subscribers to push to');
    return { success: true, message: 'No subscribers' };
  }

  let success = 0;
  let failed = 0;
  for (const sub of subscribers) {
    try {
      const receiverIdType = sub.type === 'user' ? 'union_id' : 'chat_id';
      await waveService.sendCardMessage(sub.id, receiverIdType, card);
      success++;
    } catch (err: any) {
      failed++;
      LogService.error(`Wave push to ${sub.type}:${sub.id} failed: ${err.message}`);
    }
    await new Promise((r) => setTimeout(r, 300));
  }

  LogService.info(`Wave daily ${targetDate} pushed: ${success} success, ${failed} failed`);
  return { success: true, message: `Pushed to ${success}/${subscribers.length} subscribers` };
}
