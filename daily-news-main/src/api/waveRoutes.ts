import { FastifyInstance } from 'fastify';
import { WavePublisher } from '../plugins/builtin/publishers/wave/WavePublisher.js';
import { LogService } from '../services/LogService.js';

/**
 * Wave 事件回调路由
 * 用于接收 Wave 开放平台推送的事件
 */
export function registerWaveRoutes(fastify: FastifyInstance, wavePublisher: WavePublisher) {

  /**
   * Wave 事件回调地址
   * 在 Wave 开放平台配置此 URL：https://your-domain/api/wave/callback
   */
  fastify.post('/api/wave/callback', async (request, reply) => {
    const rawBody = (request as any).rawBody || JSON.stringify(request.body);
    const body = request.body as any;

    // 打印完整的请求信息用于调试
    LogService.info(`Wave callback received - Headers: ${JSON.stringify(request.headers)}`);
    LogService.info(`Wave callback received - Body: ${rawBody.substring(0, 500)}`);

    const waveService = wavePublisher.getService();

    // 1. Challenge 校验（支持多种格式）
    // 格式1: body.challenge（顶层）
    if (body.challenge) {
      LogService.info(`Wave challenge (top-level) received: ${body.challenge}`);
      return reply.send({ challenge: body.challenge });
    }
    // 格式2: body.event.challenge（标准事件格式）
    if (body.event?.challenge) {
      LogService.info(`Wave challenge (event) received: ${body.event.challenge}`);
      return reply.send({ challenge: body.event.challenge });
    }

    // 2. 如果 body 包含 encrypt，需要解密
    if (body.encrypt) {
      if (!waveService) {
        LogService.error('Wave callback: encrypted event received but AES key not configured');
        return reply.status(500).send({ error: 'Wave service not configured, cannot decrypt' });
      }

      // 获取签名信息（兼容 hoyowave-open-* 和 open-* 两种前缀）
      const timestamp = (request.headers['hoyowave-open-timestamp'] || request.headers['open-timestamp']) as string;
      const nonce = (request.headers['hoyowave-open-nonce'] || request.headers['open-nonce']) as string;
      const signature = (request.headers['hoyowave-open-signature'] || request.headers['open-signature']) as string;

      // 验证签名（如果有签名头）
      if (timestamp && nonce && signature) {
        const valid = waveService.verifySignature(timestamp, nonce, rawBody, signature);
        if (!valid) {
          const computed = waveService.computeSignature(timestamp, nonce, rawBody);
          LogService.error(`Wave signature mismatch. received=${signature} computed=${computed} ts=${timestamp} nonce=${nonce} bodyLen=${rawBody.length}`);
          // 验签失败不阻断 challenge（部分网关可能改写 body），继续尝试解密
          LogService.warn('Signature verification failed, proceeding to decrypt anyway for challenge');
        }
      }

      // 解密事件
      let eventData: any;
      try {
        const decrypted = waveService.decrypt(body.encrypt);
        eventData = JSON.parse(decrypted);
        LogService.info(`Wave decrypted event: ${JSON.stringify(eventData).substring(0, 200)}`);
      } catch (err: any) {
        LogService.error(`Wave decrypt failed: ${err.message}`);
        return reply.status(400).send({ error: 'Decrypt failed' });
      }

      // 解密后的 challenge 校验（顶层或 event 内）
      if (eventData.challenge) {
        LogService.info(`Wave challenge (encrypted, top) received: ${eventData.challenge}`);
        return reply.send({ challenge: eventData.challenge });
      }
      if (eventData.event?.challenge) {
        LogService.info(`Wave challenge (encrypted, event) received: ${eventData.event.challenge}`);
        return reply.send({ challenge: eventData.event.challenge });
      }

      // 正常事件：先返回 200，再异步处理
      reply.status(200).send('');
      try {
        await wavePublisher.handleEvent(eventData);
      } catch (err: any) {
        LogService.error(`Wave event handling error: ${err.message}`);
      }
      return;
    }

    // 3. 非加密的普通事件
    if (!waveService) {
      LogService.error('Wave callback received but service not configured');
      return reply.status(500).send({ error: 'Wave service not configured' });
    }

    // 直接处理事件
    reply.status(200).send('');
    try {
      await wavePublisher.handleEvent(body);
    } catch (err: any) {
      LogService.error(`Wave event handling error: ${err.message}`);
    }
  });

  // ==================== 管理 API ====================

  /**
   * 获取订阅者列表
   */
  fastify.get('/api/wave/subscribers', async (request, reply) => {
    const subscribers = await wavePublisher.getSubscribers();
    return reply.send({ subscribers });
  });

  /**
   * 手动推送日报到 Wave
   */
  fastify.post('/api/wave/push', async (request, reply) => {
    const { title, date, summary, highlights } = request.body as any;

    if (!title || !date || !summary) {
      return reply.status(400).send({ error: 'Missing required fields: title, date, summary' });
    }

    try {
      const result = await wavePublisher.publishDaily({
        title,
        date,
        summary,
        highlights: highlights || [],
      });
      return reply.send(result);
    } catch (err: any) {
      return reply.status(500).send({ error: err.message });
    }
  });

  /**
   * 获取 Wave 机器人信息（前端展示用）
   */
  fastify.get('/api/wave/bot-info', async (request, reply) => {
    const subscribers = await wavePublisher.getSubscribers();
    return reply.send({
      configured: !!wavePublisher.getService(),
      subscriberCount: subscribers.length,
      userCount: subscribers.filter(s => s.type === 'user').length,
      groupCount: subscribers.filter(s => s.type === 'group').length,
    });
  });

  LogService.info('Wave callback routes registered');
}
