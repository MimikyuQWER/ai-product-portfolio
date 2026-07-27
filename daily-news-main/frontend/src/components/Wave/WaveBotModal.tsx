import { useState } from 'react';

interface WaveBotModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const BOT_NAME = 'ai_daily';

export default function WaveBotModal({ isOpen, onClose }: WaveBotModalProps) {
  const [tab, setTab] = useState<'personal' | 'group'>('personal');
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(BOT_NAME);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-white dark:bg-surface-dark rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-slate-200 dark:border-border-dark">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-500 to-purple-500 px-6 py-5 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl">🤖</span>
              <div>
                <h2 className="text-lg font-bold">订阅 AI 日报推送</h2>
                <p className="text-sm text-white/80">每天自动收到精选 AI 资讯</p>
              </div>
            </div>
            <button onClick={onClose} className="text-white/80 hover:text-white transition-colors">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-100 dark:border-border-dark">
          <button
            onClick={() => setTab('personal')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              tab === 'personal'
                ? 'text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-500'
                : 'text-slate-500 dark:text-text-secondary hover:text-slate-700'
            }`}
          >
            <span className="material-symbols-outlined text-[18px] align-middle mr-1">person</span>
            订阅到个人
          </button>
          <button
            onClick={() => setTab('group')}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              tab === 'group'
                ? 'text-purple-600 dark:text-purple-400 border-b-2 border-purple-500'
                : 'text-slate-500 dark:text-text-secondary hover:text-slate-700'
            }`}
          >
            <span className="material-symbols-outlined text-[18px] align-middle mr-1">groups</span>
            订阅到群聊
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5">
          {tab === 'personal' ? (
            <div className="space-y-4">
              <p className="text-sm text-slate-600 dark:text-text-secondary">
                在 Wave 中搜索并打开机器人，进入对话即可自动订阅，之后每天会私聊推送日报给你。
              </p>
              <div className="flex items-center gap-3 p-4 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800/30">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center">
                  <span className="material-symbols-outlined text-indigo-600 dark:text-indigo-400">smart_toy</span>
                </div>
                <div className="flex-1">
                  <p className="text-xs text-slate-400 dark:text-text-secondary">机器人名称</p>
                  <p className="text-base font-bold text-slate-900 dark:text-white font-mono">{BOT_NAME}</p>
                </div>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 px-2 py-1 rounded"
                >
                  <span className="material-symbols-outlined text-[16px]">{copied ? 'check' : 'content_copy'}</span>
                  {copied ? '已复制' : '复制'}
                </button>
              </div>
              <ol className="space-y-2 text-sm text-slate-600 dark:text-text-secondary">
                <li className="flex gap-2"><span className="font-bold text-indigo-500">1.</span> 打开 Wave，搜索机器人 <code className="px-1 rounded bg-slate-100 dark:bg-surface-darker">{BOT_NAME}</code></li>
                <li className="flex gap-2"><span className="font-bold text-indigo-500">2.</span> 点击进入与机器人的对话</li>
                <li className="flex gap-2"><span className="font-bold text-indigo-500">3.</span> 订阅完成，每天自动收到日报推送</li>
              </ol>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-slate-600 dark:text-text-secondary">
                把机器人拉进任意 Wave 群聊，群内成员每天都能收到日报推送。
              </p>
              <div className="flex items-center gap-3 p-4 rounded-xl bg-purple-50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-800/30">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center">
                  <span className="material-symbols-outlined text-purple-600 dark:text-purple-400">smart_toy</span>
                </div>
                <div className="flex-1">
                  <p className="text-xs text-slate-400 dark:text-text-secondary">机器人名称</p>
                  <p className="text-base font-bold text-slate-900 dark:text-white font-mono">{BOT_NAME}</p>
                </div>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 text-xs font-medium text-purple-600 dark:text-purple-400 hover:text-purple-700 px-2 py-1 rounded"
                >
                  <span className="material-symbols-outlined text-[16px]">{copied ? 'check' : 'content_copy'}</span>
                  {copied ? '已复制' : '复制'}
                </button>
              </div>
              <ol className="space-y-2 text-sm text-slate-600 dark:text-text-secondary">
                <li className="flex gap-2"><span className="font-bold text-purple-500">1.</span> 打开目标 Wave 群聊</li>
                <li className="flex gap-2"><span className="font-bold text-purple-500">2.</span> 群设置 → 添加成员/机器人，搜索 <code className="px-1 rounded bg-slate-100 dark:bg-surface-darker">{BOT_NAME}</code></li>
                <li className="flex gap-2"><span className="font-bold text-purple-500">3.</span> 添加后该群每天自动收到日报推送</li>
              </ol>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50 dark:bg-surface-darker border-t border-slate-100 dark:border-border-dark">
          <p className="text-[11px] text-slate-400 dark:text-text-secondary text-center">
            每日早间自动推送 · 精选 AI 资讯中文摘要 · 支持随时退订
          </p>
        </div>
      </div>
    </div>
  );
}
