import dotenv from 'dotenv';
import cron from 'node-cron';
import fs from 'fs';
import path from 'path';
import { createServer } from './api/server.js';
import { LocalStore } from './services/LocalStore.js';
import { ServiceContext } from './services/ServiceContext.js';
import { LogService } from './services/LogService.js';
import { syncDailyFromGitHub } from './scripts/syncDaily.js';
import { pushDailyToWave } from './scripts/pushWave.js';


dotenv.config();

// Global error handlers to prevent process crash
process.on('uncaughtException', (error) => {
  LogService.error(`Uncaught Exception: ${error.message}`);
  if (error.stack) LogService.error(error.stack);
  // Do not exit, try to keep the service running
});

process.on('unhandledRejection', (reason, promise) => {
  LogService.error(`Unhandled Rejection at: ${promise}, reason: ${reason}`);
});

function getShanghaiParts() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hour12: false,
  }).formatToParts(new Date());

  const get = (type: string) => parts.find((part) => part.type === type)?.value || '';
  return {
    date: `${get('year')}-${get('month')}-${get('day')}`,
    hour: Number(get('hour')),
  };
}

async function generateDailyReport(reason: string) {
  LogService.info(`Daily generation started (${reason})...`);
  try {
    const { execFileSync } = await import('child_process');
    execFileSync('/usr/bin/npx', ['tsx', 'src/scripts/generateDailyRss.ts'], {
      cwd: process.cwd(),
      timeout: 600000,
      stdio: 'pipe',
      env: { ...process.env, PATH: process.env.PATH || '/usr/bin:/usr/local/bin:/bin' },
    });
    LogService.info(`Daily generation finished (${reason})`);

    await pushDailyToWave();
  } catch (err: any) {
    const stderr = err?.stderr ? Buffer.from(err.stderr).toString('utf8') : '';
    const stdout = err?.stdout ? Buffer.from(err.stdout).toString('utf8') : '';
    LogService.error(`Daily generation failed (${reason}): ${err.message}`);
    if (stdout.trim()) LogService.error(`Daily generation stdout: ${stdout.slice(-1000)}`);
    if (stderr.trim()) LogService.error(`Daily generation stderr: ${stderr.slice(-1000)}`);
  }
}

async function generateMissingTodayAfterNine() {
  const { date, hour } = getShanghaiParts();
  if (hour < 9) return;

  const filePath = path.resolve(process.cwd(), 'daily', `${date}.md`);
  if (fs.existsSync(filePath)) {
    LogService.info(`Daily report already exists for ${date}, startup catch-up skipped`);
    return;
  }

  await generateDailyReport(`startup catch-up for ${date}`);
}

async function bootstrap() {
  const store = new LocalStore();
  await store.init();

  // --- Initialize Service Context (Singleton) ---
  const context = await ServiceContext.getInstance(store);

  const server = await createServer(store);

  const port = parseInt(process.env.PORT || '3000');

  try {
    await server.listen({ port, host: '0.0.0.0' });
    console.log(`Server listening on port ${port}`);

    // --- 启动时立即同步一次 GitHub 日报内容 ---
    syncDailyFromGitHub();

    // --- 每 30 分钟自动从 GitHub 拉取最新日报 ---
    cron.schedule('*/30 * * * *', () => {
      LogService.info('Cron: syncing daily content from GitHub...');
      syncDailyFromGitHub();
    });

    generateMissingTodayAfterNine().catch((err) => {
      LogService.error(`Startup daily catch-up failed: ${err.message}`);
    });

    // --- 每天早上 9:00 (北京时间) 自动生成当日 AI 日报 ---
    cron.schedule('0 9 * * *', async () => {
      await generateDailyReport('scheduled 09:00 Asia/Shanghai');
    }, { timezone: 'Asia/Shanghai' });

  } catch (err) {
    server.log.error(err);
    process.exit(1);
  }
}

bootstrap();
