import { WaveService } from './WaveService.js';
import { LogService } from '../../../../services/LogService.js';

export interface WaveSubscriber {
  id: string;           // open_id 或 chat_id
  type: 'user' | 'group';
  name?: string;
  subscribedAt: string;
}

/**
 * Wave Publisher 插件
 * 实现向订阅用户/群推送 AI 日报卡片
 */
export class WavePublisher {
  static metadata = {
    id: 'wave',
    name: 'Wave 机器人推送',
    description: '通过 Wave 机器人推送 AI 日报卡片消息到个人和群聊',
    icon: '🤖',
    type: 'publisher' as const,
    configFields: [
      { key: 'appId', label: 'App ID', type: 'text' as const, required: true },
      { key: 'appSecret', label: 'App Secret', type: 'password' as const, required: true },
      { key: 'aesKey', label: '加密 AES Key', type: 'password' as const, required: true },
      { key: 'signToken', label: '签名 Token', type: 'password' as const, required: true },
      { key: 'apiBaseUrl', label: 'API Base URL', type: 'text' as const, required: true },
      { key: 'dailyViewBaseUrl', label: '日报查看地址（前端地址）', type: 'text' as const, required: true },
    ],
  };

  private waveService: WaveService | null = null;
  private config: any;
  private store: any;

  constructor(store: any) {
    this.store = store;
  }

  /**
   * 初始化 Wave 服务
   */
  initialize(config: any) {
    this.config = config;
    if (config.appId && config.appSecret && config.aesKey && config.signToken) {
      this.waveService = new WaveService({
        appId: config.appId,
        appSecret: config.appSecret,
        aesKey: config.aesKey,
        signToken: config.signToken,
        apiBaseUrl: config.apiBaseUrl || 'https://open.hoyowave.com',
      });
      LogService.info('Wave Publisher initialized');
    }
  }

  getService(): WaveService | null {
    return this.waveService;
  }

  // ==================== 订阅者管理 ====================

  /**
   * 获取所有订阅者列表
   */
  async getSubscribers(): Promise<WaveSubscriber[]> {
    try {
      const db = this.store.getDb();
      const rows = await db.all('SELECT * FROM wave_subscribers ORDER BY subscribed_at DESC');
      return rows || [];
    } catch {
      return [];
    }
  }

  /**
   * 添加订阅者
   */
  async addSubscriber(subscriber: WaveSubscriber): Promise<void> {
    const db = this.store.getDb();
    await db.run(
      `INSERT OR REPLACE INTO wave_subscribers (id, type, name, subscribed_at) VALUES (?, ?, ?, ?)`,
      [subscriber.id, subscriber.type, subscriber.name || '', subscriber.subscribedAt]
    );
    LogService.info(`Wave subscriber added: ${subscriber.type}:${subscriber.id} (${subscriber.name})`);
  }

  /**
   * 移除订阅者
   */
  async removeSubscriber(id: string): Promise<void> {
    const db = this.store.getDb();
    await db.run('DELETE FROM wave_subscribers WHERE id = ?', [id]);
    LogService.info(`Wave subscriber removed: ${id}`);
  }

  // ==================== 推送日报 ====================

  /**
   * 向所有订阅者推送日报
   */
  async publishDaily(options: {
    title: string;
    date: string;
    summary: string;
    highlights: string[];
  }): Promise<{ success: number; failed: number; errors: string[] }> {
    if (!this.waveService) {
      throw new Error('Wave service not initialized. Please configure Wave settings first.');
    }

    const viewUrl = `${this.config.dailyViewBaseUrl}/generation?date=${options.date}`;
    const card = this.waveService.buildDailyCard({ ...options, viewUrl });
    const subscribers = await this.getSubscribers();

    let success = 0;
    let failed = 0;
    const errors: string[] = [];

    for (const sub of subscribers) {
      try {
        const receiverIdType = sub.type === 'user' ? 'union_id' : 'chat_id';
        await this.waveService.sendCardMessage(sub.id, receiverIdType, card);
        success++;
      } catch (err: any) {
        failed++;
        errors.push(`${sub.type}:${sub.id} - ${err.message}`);
      }
    }

    LogService.info(`Wave daily published: ${success} success, ${failed} failed`);
    return { success, failed, errors };
  }

  // ==================== 事件处理 ====================

  /**
   * 处理 Wave 事件回调
   */
  async handleEvent(eventBody: any): Promise<void> {
    const { header, event } = eventBody;
    const eventType = header?.event_type;
    const appId = header?.app_id;

    LogService.info(`Wave event received: ${eventType}`);

    switch (eventType) {
      // 用户进入应用机器人单聊会话 → 订阅
      case 'im.chat.bot.entered_v1':
        await this.handleBotEntered(event);
        break;

      // 用户/机器人加入群组 → 机器人被拉进群则订阅该群
      case 'im.chat.members.added_v1':
        await this.handleMembersAdded(event, appId);
        break;

      // 用户/机器人退出群组 → 机器人被移出则取消该群订阅
      case 'im.chat.members.deleted_v1':
        await this.handleMembersDeleted(event, appId);
        break;

      // 群组解散 → 取消该群订阅
      case 'im.chat.disbanded_v1':
        await this.handleChatDisbanded(event);
        break;

      default:
        LogService.info(`Wave unhandled event type: ${eventType}`);
    }
  }

  /** 用户进入机器人单聊会话，记录为订阅者 */
  private async handleBotEntered(event: any): Promise<void> {
    const userId = event?.operator?.id;
    const idType = event?.operator?.id_type || 'union_id';
    if (userId) {
      await this.addSubscriber({
        id: userId,
        type: 'user',
        name: idType,
        subscribedAt: new Date().toISOString(),
      });
    }
  }

  /** 机器人被拉进群，记录群为订阅者 */
  private async handleMembersAdded(event: any, appId?: string): Promise<void> {
    const chatId = event?.chat_id;
    if (!chatId) return;
    // 检查加入成员中是否包含本机器人（id_type=app_id 且 id 匹配）
    const members = event?.members || [];
    const botJoined = members.some((m: any) => m.id_type === 'app_id' && (!appId || m.id === appId));
    if (botJoined) {
      await this.addSubscriber({
        id: chatId,
        type: 'group',
        name: '群聊',
        subscribedAt: new Date().toISOString(),
      });
    }
  }

  /** 机器人被移出群，取消订阅 */
  private async handleMembersDeleted(event: any, appId?: string): Promise<void> {
    const chatId = event?.chat_id;
    if (!chatId) return;
    const members = event?.members || [];
    const botRemoved = members.some((m: any) => m.id_type === 'app_id' && (!appId || m.id === appId));
    if (botRemoved) {
      await this.removeSubscriber(chatId);
    }
  }

  /** 群组解散，取消订阅 */
  private async handleChatDisbanded(event: any): Promise<void> {
    const chatId = event?.chat_id;
    if (chatId) {
      await this.removeSubscriber(chatId);
    }
  }
}
