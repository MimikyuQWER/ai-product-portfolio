import { LocalStore } from '../services/LocalStore.js';
import { LogService } from '../services/LogService.js';

/**
 * 访问统计服务
 * 记录页面访问（PV/UV），提供统计查询
 */
export class AnalyticsService {
  constructor(private store: LocalStore) {}

  /**
   * 记录一次页面访问
   */
  async recordPageView(opts: {
    path?: string;
    visitorId?: string;
    ip?: string;
    userAgent?: string;
  }): Promise<void> {
    try {
      const db = this.store.getDb();
      if (!db) return;
      const now = new Date();
      // 上海时区日期
      const date = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric', month: '2-digit', day: '2-digit',
      }).format(now);

      await db.run(
        `INSERT INTO page_views (date, path, visitor_id, ip, user_agent, created_at) VALUES (?, ?, ?, ?, ?, ?)`,
        [date, opts.path || '/', opts.visitorId || '', opts.ip || '', (opts.userAgent || '').slice(0, 200), now.getTime()]
      );
    } catch (err: any) {
      LogService.error(`recordPageView error: ${err.message}`);
    }
  }

  /**
   * 获取统计概览
   */
  async getStats(days = 30): Promise<any> {
    const db = this.store.getDb();
    if (!db) return null;

    // 今日日期（上海时区）
    const today = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(new Date());

    // 今日 PV / UV
    const todayPv = await db.get(`SELECT COUNT(*) as cnt FROM page_views WHERE date = ?`, [today]);
    const todayUv = await db.get(`SELECT COUNT(DISTINCT visitor_id) as cnt FROM page_views WHERE date = ? AND visitor_id != ''`, [today]);

    // 总 PV / UV
    const totalPv = await db.get(`SELECT COUNT(*) as cnt FROM page_views`);
    const totalUv = await db.get(`SELECT COUNT(DISTINCT visitor_id) as cnt FROM page_views WHERE visitor_id != ''`);

    // 近 N 天每日趋势
    const daily = await db.all(
      `SELECT date,
              COUNT(*) as pv,
              COUNT(DISTINCT visitor_id) as uv
       FROM page_views
       GROUP BY date
       ORDER BY date DESC
       LIMIT ?`,
      [days]
    );

    // 订阅者统计
    const subTotal = await db.get(`SELECT COUNT(*) as cnt FROM wave_subscribers`);
    const subUser = await db.get(`SELECT COUNT(*) as cnt FROM wave_subscribers WHERE type = 'user'`);
    const subGroup = await db.get(`SELECT COUNT(*) as cnt FROM wave_subscribers WHERE type = 'group'`);

    return {
      pageViews: {
        today: { pv: todayPv?.cnt || 0, uv: todayUv?.cnt || 0 },
        total: { pv: totalPv?.cnt || 0, uv: totalUv?.cnt || 0 },
        daily: (daily || []).reverse(),
      },
      subscribers: {
        total: subTotal?.cnt || 0,
        user: subUser?.cnt || 0,
        group: subGroup?.cnt || 0,
      },
    };
  }
}
