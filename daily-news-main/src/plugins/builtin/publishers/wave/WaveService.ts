import crypto from 'crypto';
import { LogService } from '../../../../services/LogService.js';

/**
 * Wave 开放平台服务
 * 处理事件解密、验签、Token 管理、消息发送
 */
export class WaveService {
  private appId: string;
  private appSecret: string;
  private aesKey: string;
  private signToken: string;
  private apiBaseUrl: string;
  private accessToken: string = '';
  private tokenExpireTime: number = 0;

  constructor(config: {
    appId: string;
    appSecret: string;
    aesKey: string;
    signToken: string;
    apiBaseUrl: string;
  }) {
    this.appId = config.appId;
    this.appSecret = config.appSecret;
    this.aesKey = config.aesKey;
    this.signToken = config.signToken;
    this.apiBaseUrl = config.apiBaseUrl || 'https://open.hoyowave.com';
  }

  // ==================== 事件解密 ====================

  /**
   * 解密事件 Body（AES-CBC）
   * 根据 key 长度自动选择 aes-128/192/256
   * secretKey = aesKey，iv = secretKey[0:16]
   */
  decrypt(encryptStr: string): string {
    try {
      const key = Buffer.from(this.aesKey, 'utf-8');
      const iv = key.slice(0, 16);

      // 根据 key 长度选择算法：16=aes-128, 24=aes-192, 32=aes-256
      let algorithm: string;
      if (key.length === 16) algorithm = 'aes-128-cbc';
      else if (key.length === 24) algorithm = 'aes-192-cbc';
      else if (key.length === 32) algorithm = 'aes-256-cbc';
      else throw new Error(`Invalid AES key length: ${key.length}, must be 16/24/32 bytes`);

      const src = Buffer.from(encryptStr, 'base64');
      const decipher = crypto.createDecipheriv(algorithm, key, iv);
      decipher.setAutoPadding(true);
      let decrypted = decipher.update(src);
      decrypted = Buffer.concat([decrypted, decipher.final()]);

      return decrypted.toString('utf-8');
    } catch (err: any) {
      LogService.error(`Wave decrypt error: ${err.message}`);
      throw new Error('Failed to decrypt Wave event');
    }
  }

  // ==================== 签名验证 ====================

  /**
   * 计算事件签名
   * signature = sha256(timestamp + nonce + body + signatureKey)
   */
  computeSignature(timestamp: string, nonce: string, body: string): string {
    return crypto
      .createHash('sha256')
      .update(timestamp + nonce + body + this.signToken)
      .digest('hex');
  }

  /**
   * 验证事件签名
   * signature = sha256(timestamp + nonce + body + signatureKey)
   */
  verifySignature(timestamp: string, nonce: string, body: string, signature: string): boolean {
    return this.computeSignature(timestamp, nonce, body) === signature;
  }

  // ==================== Token 管理 ====================

  /**
   * 获取 access_token（带缓存）
   */
  async getAccessToken(): Promise<string> {
    if (this.accessToken && Date.now() < this.tokenExpireTime) {
      return this.accessToken;
    }

    try {
      const response = await fetch(`${this.apiBaseUrl}/openapi/auth/v1/access_token/internal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          app_id: this.appId,
          app_secret: this.appSecret,
        }),
      });

      const data = await response.json() as any;
      if (data.retcode !== 0) {
        throw new Error(`Get token failed: ${data.message}`);
      }

      this.accessToken = data.data.access_token;
      // 提前 5 分钟过期（expire 单位为秒，绝对时间戳）
      this.tokenExpireTime = data.data.expire * 1000 - 300 * 1000;
      LogService.info('Wave access token refreshed');
      return this.accessToken;
    } catch (err: any) {
      LogService.error(`Wave getAccessToken error: ${err.message}`);
      throw err;
    }
  }

  // ==================== 发送消息 ====================

  /**
   * 发送消息卡片到指定会话（个人/群）
   * @param receiverId - 接收者 ID（union_id / user_id / chat_id）
   * @param receiverIdType - "union_id" | "user_id" | "chat_id"
   * @param card - 卡片 JSON 对象
   */
  async sendCardMessage(receiverId: string, receiverIdType: 'union_id' | 'user_id' | 'chat_id', card: object): Promise<any> {
    const token = await this.getAccessToken();

    const response = await fetch(
      `${this.apiBaseUrl}/openapi/im/v1/message/send`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token,
        },
        body: JSON.stringify({
          receiver_id: receiverId,
          receiver_id_type: receiverIdType,
          msg_type: 'card',
          content: JSON.stringify(card),
        }),
      }
    );

    const data = await response.json() as any;
    if (data.retcode !== 0) {
      LogService.error(`Wave sendCardMessage failed: ${JSON.stringify(data)}`);
      throw new Error(`Send message failed: ${data.message}`);
    }

    LogService.info(`Wave message sent to ${receiverIdType}:${receiverId}`);
    return data;
  }

  /**
   * 构建 AI 日报卡片 JSON
   */
  buildDailyCard(options: {
    title: string;
    date: string;
    summary: string;
    highlights: string[];
    viewUrl: string;
  }): object {
    const highlightsMarkdown = options.highlights
      .map((h, i) => `**${i + 1}.** ${h}`)
      .join('\n');

    return {
      header: {
        title: `📰 ${options.title}`,
        template: 'blue',
      },
      config: {
        disable_forward: false,
      },
      card: {
        tag: 'column',
        elements: [
          {
            tag: 'markdown',
            text: `📅 **${options.date}**\n\n${options.summary}`,
            text_align: 'left',
          },
          {
            tag: 'markdown',
            text: `---\n\n🔥 **今日热点**\n\n${highlightsMarkdown}`,
            text_align: 'left',
          },
          {
            tag: 'button',
            text: '📖 查看完整日报',
            type: 'primary',
            option: {
              tag: 'url',
              multi_url: {
                url: options.viewUrl,
                ios_url: options.viewUrl,
                android_url: options.viewUrl,
              },
            },
          },
        ],
      },
      card_action: {
        url: options.viewUrl,
        ios_url: options.viewUrl,
        android_url: options.viewUrl,
      },
    };
  }
}
