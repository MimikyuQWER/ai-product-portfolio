import { execSync } from 'child_process';
import { LogService } from '../services/LogService.js';

/**
 * 从 GitHub 同步日报内容（已禁用）
 * 现在日报由 Titan 内网直接生成，不再需要从 GitHub 拉取
 * 保留此函数以便未来需要时重新启用
 */
export function syncDailyFromGitHub(): { success: boolean; message: string } {
  // 已禁用：日报现在由本地 AthenAI 生成，不再从 GitHub 同步
  // 避免 GitHub 上的旧版英文日报覆盖本地中文版
  LogService.info('GitHub sync disabled: daily reports are now generated locally via AthenAI');
  return { success: true, message: 'Sync disabled - using local generation' };
}
