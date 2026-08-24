import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot, Check, ChevronDown, Clipboard, Download, FileDown, History,
  LoaderCircle, Menu, Pencil, Redo2, RotateCcw, Sparkles, Undo2, X,
} from 'lucide-react';

const ContentRenderer = lazy(() => import('./components/ContentRenderer'));

type IndexData = { dates: string[]; archives: string[] };
type ConfigStatus = { configured: boolean; provider: string; model: string; baseUrl: string };
type TocItem = { id: string; title: string };
type Toast = { id: number; message: string; tone?: 'info' | 'success' | 'warning' };

const DRAFT_PREFIX = 'ai-daily-demo:draft:';
const HISTORY_LIMIT = 5;
const BASE_URL = import.meta.env.BASE_URL;
const IS_STATIC_HOSTING = BASE_URL !== '/';
const assetUrl = (path: string) => `${BASE_URL}${path.replace(/^\/+/, '')}`;
const DATA_BASE_URL = IS_STATIC_HOSTING ? `${BASE_URL}../daily-news-main/demo/public/` : BASE_URL;
const dataUrl = (path: string) => `${DATA_BASE_URL}${path.replace(/^\/+/, '')}`;

const formatDate = (date: string, withYear = true) => {
  const value = new Date(`${date}T12:00:00`);
  return new Intl.DateTimeFormat('zh-CN', withYear
    ? { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' }
    : { month: '2-digit', day: '2-digit' }).format(value);
};

const slug = (value: string) => value.toLowerCase().trim().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');

function extractToc(markdown: string): TocItem[] {
  return markdown.split('\n').filter((line) => /^##\s+/.test(line)).map((line) => {
    const title = line.replace(/^##\s+/, '').replace(/[*_`]/g, '').trim();
    return { title, id: slug(title) };
  });
}

function downloadBlob(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function App() {
  const [index, setIndex] = useState<IndexData>({ dates: [], archives: [] });
  const [date, setDate] = useState('');
  const [snapshot, setSnapshot] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<'read' | 'edit'>('read');
  const [past, setPast] = useState<string[]>([]);
  const [future, setFuture] = useState<string[]>([]);
  const [config, setConfig] = useState<ConfigStatus | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0, title: '' });
  const [toasts, setToasts] = useState<Toast[]>([]);
  const previewRef = useRef<HTMLElement>(null);
  const editTimer = useRef<number | null>(null);
  const editBase = useRef<string | null>(null);

  const toc = useMemo(() => extractToc(content), [content]);
  const dirty = Boolean(snapshot && content !== snapshot);

  const toast = (message: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now();
    setToasts((items) => [...items, { id, message, tone }]);
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 3200);
  };

  useEffect(() => {
    const configRequest = IS_STATIC_HOSTING
      ? Promise.resolve<ConfigStatus>({ configured: false, provider: '', model: '', baseUrl: '' })
      : fetch(assetUrl('api/config/status')).then((response) => response.json());

    Promise.all([
      fetch(dataUrl('daily-index.json')).then((response) => response.json()),
      configRequest,
    ]).then(([data, status]) => {
      setIndex(data);
      setDate(data.dates[0]);
      setConfig(status);
    }).catch(() => toast('初始化失败，请确认本地服务已启动', 'warning'));
  }, []);

  useEffect(() => {
    if (!date) return;
    setLoading(true);
    fetch(dataUrl(`daily/${date}.md`), { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error('not found');
        return response.text();
      })
      .then((markdown) => {
        setSnapshot(markdown);
        setContent(localStorage.getItem(`${DRAFT_PREFIX}${date}`) || markdown);
        setPast([]);
        setFuture([]);
        setMode('read');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      })
      .catch(() => toast('这一天的快照未能加载', 'warning'))
      .finally(() => setLoading(false));
  }, [date]);

  useEffect(() => {
    if (!date || !snapshot) return;
    if (content === snapshot) localStorage.removeItem(`${DRAFT_PREFIX}${date}`);
    else localStorage.setItem(`${DRAFT_PREFIX}${date}`, content);
  }, [content, date, snapshot]);

  const applyEdit = (next: string) => {
    if (next === content) return;
    if (editTimer.current) window.clearTimeout(editTimer.current);
    editTimer.current = null;
    editBase.current = null;
    setPast((items) => [...items.slice(-(HISTORY_LIMIT - 1)), content]);
    setFuture([]);
    setContent(next);
  };

  const onEditorChange = (next: string) => {
    if (editBase.current === null) editBase.current = content;
    setContent(next);
    if (editTimer.current) window.clearTimeout(editTimer.current);
    editTimer.current = window.setTimeout(() => {
      const base = editBase.current;
      if (base !== null && base !== next) setPast((items) => [...items.slice(-(HISTORY_LIMIT - 1)), base]);
      setFuture([]);
      editBase.current = null;
      editTimer.current = null;
    }, 500);
  };

  const undo = () => {
    const previous = past.at(-1);
    if (previous === undefined) return;
    setPast((items) => items.slice(0, -1));
    setFuture((items) => [content, ...items].slice(0, HISTORY_LIMIT));
    setContent(previous);
  };

  const redo = () => {
    const next = future[0];
    if (next === undefined) return;
    setFuture((items) => items.slice(1));
    setPast((items) => [...items.slice(-(HISTORY_LIMIT - 1)), content]);
    setContent(next);
  };

  const restore = () => {
    if (!dirty || !window.confirm('恢复原始快照？当前本地草稿将被清除。')) return;
    applyEdit(snapshot);
    localStorage.removeItem(`${DRAFT_PREFIX}${date}`);
    toast('已恢复原始快照', 'success');
  };

  const copyMarkdown = async () => {
    await navigator.clipboard.writeText(content);
    toast('Markdown 已复制', 'success');
  };

  const exportHtml = () => {
    const article = previewRef.current?.innerHTML || '<p>请切换到阅读模式后重试。</p>';
    const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AI 资讯日报 · ${date}</title><style>body{margin:0;background:#f4f4f1;color:#191918;font:17px/1.8 Inter,"Noto Sans SC",sans-serif}.page{max-width:820px;margin:40px auto;padding:48px 64px;background:#fff}h1,h2,h3{font-family:Georgia,"Noto Serif SC",serif;line-height:1.25}h2{margin-top:2.5em;border-top:1px solid #ddd;padding-top:1.2em}img{display:block;max-width:100%;height:auto;margin:24px auto;border-radius:8px}a{color:#27496d}blockquote{border-left:3px solid #bbb;margin-left:0;padding-left:20px;color:#555}@media(max-width:700px){.page{margin:0;padding:28px 20px}}</style></head><body><main class="page">${article}</main></body></html>`;
    downloadBlob(`ai-daily-${date}.html`, html, 'text/html;charset=utf-8');
    setExportOpen(false);
    toast('独立 HTML 已导出', 'success');
  };

  const runPolish = async () => {
    if (!config?.configured) {
      setSetupOpen(true);
      return;
    }
    setPolishing(true);
    setProgress({ current: 0, total: 0, title: '正在准备章节' });
    try {
      const response = await fetch(assetUrl('api/ai/polish'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date, markdown: content }),
      });
      if (!response.ok || !response.body) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || 'AI 服务暂时不可用');
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let failures: string[] = [];
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.type === 'start') setProgress({ current: 0, total: event.total, title: '开始润色' });
          if (event.type === 'progress' || event.type === 'warning') setProgress({ current: event.current, total: event.total, title: event.title });
          if (event.type === 'complete') {
            applyEdit(event.markdown);
            failures = event.failures || [];
          }
          if (event.type === 'error') throw new Error(event.message);
        }
        if (done) break;
      }
      toast(failures.length ? `润色完成，${failures.length} 个章节保留原文` : 'AI 润色完成，结果已保存为本地草稿', failures.length ? 'warning' : 'success');
    } catch (error) {
      toast(error instanceof Error ? error.message : 'AI 润色失败', 'warning');
    } finally {
      setPolishing(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="打开日期导航"><Menu size={20} /></button>
        <a className="brand" href="#top" aria-label="AI 资讯日报首页"><span className="brand-mark">AI</span><span>资讯日报</span></a>
        <div className="snapshot-chip"><span />数据快照演示</div>
        <button className="ghost-button" onClick={() => setSetupOpen(true)}><Bot size={17} /><span className={config?.configured ? 'status-dot ready' : 'status-dot'} />AI {config?.configured ? '已配置' : '可选'}</button>
      </header>

      <aside className={`date-rail ${mobileNav ? 'open' : ''}`} aria-label="快照日期">
        <div className="rail-head"><span>快照日期</span><button onClick={() => setMobileNav(false)} aria-label="关闭导航"><X size={19} /></button></div>
        <div className="date-list">
          {index.dates.map((item, i) => (
            <button key={item} className={item === date ? 'active' : ''} onClick={() => { setDate(item); setMobileNav(false); }}>
              <span className="date-short">{formatDate(item, false)}</span>
              <span className="date-meta">{i === 0 ? '最新快照' : item.slice(0, 4)}</span>
            </button>
          ))}
        </div>
        <div className="archive-note"><History size={15} />另含 {index.archives.length} 份归档副本</div>
      </aside>
      {mobileNav && <button className="scrim" onClick={() => setMobileNav(false)} aria-label="关闭导航遮罩" />}

      <main className="workspace" id="top">
        <section className="hero">
          <p className="eyebrow">AI INDUSTRY BRIEF · FIXED SNAPSHOT</p>
          <h1>AI 资讯日报</h1>
          <p>聚合当天值得关注的人工智能新闻、产品与研究进展。</p>
          <div className="hero-date">{date ? formatDate(date) : '正在读取快照…'}</div>
        </section>

        <div className="mobile-date-select">
          <label htmlFor="date-select">选择快照</label>
          <div><select id="date-select" value={date} onChange={(event) => setDate(event.target.value)}>{index.dates.map((item) => <option key={item}>{item}</option>)}</select><ChevronDown size={17} /></div>
        </div>

        <section className="document-card">
          <div className="toolbar">
            <div className="mode-switch" role="group" aria-label="阅读模式">
              <button className={mode === 'read' ? 'active' : ''} onClick={() => setMode('read')}>阅读</button>
              <button className={mode === 'edit' ? 'active' : ''} onClick={() => setMode('edit')}><Pencil size={14} />编辑</button>
            </div>
            <div className="toolbar-actions">
              {mode === 'edit' && <><button onClick={undo} disabled={!past.length} title="撤销"><Undo2 size={17} /></button><button onClick={redo} disabled={!future.length} title="重做"><Redo2 size={17} /></button></>}
              <button onClick={restore} disabled={!dirty} title="恢复原始快照"><RotateCcw size={17} /></button>
              <button className="text-action" onClick={runPolish} disabled={polishing}><Sparkles size={17} />{polishing ? '润色中' : 'AI 润色'}</button>
              <button className="primary-action" onClick={() => setExportOpen(true)}><Download size={17} />本地导出</button>
            </div>
          </div>
          {polishing && <div className="progress-bar" aria-live="polite"><LoaderCircle className="spin" size={16} /><span>{progress.total ? `${progress.current}/${progress.total}` : '…'}</span><strong>{progress.title}</strong><i style={{ width: `${progress.total ? (progress.current / progress.total) * 100 : 8}%` }} /></div>}
          {dirty && <div className="draft-banner"><span>本地草稿</span>改动仅保存在当前浏览器，不会修改原始快照。</div>}
          {loading ? <div className="loading-state"><LoaderCircle className="spin" /><p>正在装订今天的日报…</p></div> : <>
            <article className="markdown-body" ref={previewRef} hidden={mode !== 'read'}><Suspense fallback={<div className="loading-state"><LoaderCircle className="spin" /></div>}><ContentRenderer markdown={content} assetBase={DATA_BASE_URL} /></Suspense></article>
            {mode === 'edit' && <div className="editor-wrap"><div className="editor-note">Markdown 编辑器 · 自动保存至浏览器 · 最多 5 步撤销</div><textarea value={content} onChange={(event) => onEditorChange(event.target.value)} spellCheck="false" aria-label="Markdown 编辑器" /></div>}
          </>}
        </section>
      </main>

      <aside className="toc-rail" aria-label="本页目录">
        <p>本期目录</p>
        <nav>{toc.slice(0, 12).map((item, i) => <a href={`#${item.id}`} key={`${item.id}-${i}`}><span>{String(i + 1).padStart(2, '0')}</span>{item.title}</a>)}</nav>
      </aside>

      {exportOpen && <div className="modal-layer" role="presentation" onMouseDown={() => setExportOpen(false)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="export-title" onMouseDown={(event) => event.stopPropagation()}><button className="modal-close" onClick={() => setExportOpen(false)} aria-label="关闭"><X size={19} /></button><p className="eyebrow">LOCAL EXPORT</p><h2 id="export-title">带走这份日报</h2><p>所有操作都在本机完成，不会发布到任何平台。</p><div className="export-grid"><button onClick={copyMarkdown}><Clipboard /><span><strong>复制正文</strong><small>复制当前 Markdown</small></span></button><button onClick={() => { downloadBlob(`ai-daily-${date}.md`, content, 'text/markdown;charset=utf-8'); setExportOpen(false); toast('Markdown 已下载', 'success'); }}><FileDown /><span><strong>下载 Markdown</strong><small>适合继续编辑</small></span></button><button onClick={exportHtml}><Download /><span><strong>导出独立 HTML</strong><small>双击即可离线阅读</small></span></button></div></section></div>}

      {setupOpen && <div className="modal-layer" role="presentation" onMouseDown={() => setSetupOpen(false)}><section className="modal setup-modal" role="dialog" aria-modal="true" aria-labelledby="setup-title" onMouseDown={(event) => event.stopPropagation()}><button className="modal-close" onClick={() => setSetupOpen(false)} aria-label="关闭"><X size={19} /></button><div className="bot-orb"><Bot /></div><h2 id="setup-title">{config?.configured ? 'AI 润色已就绪' : '可选的 AI 润色'}</h2><p>{config?.configured ? `当前模型：${config.model}` : '快照浏览、编辑和导出无需密钥。若想体验整篇润色，请在项目根目录配置本地 .env。'}</p>{!config?.configured && <><pre><code>复制 .env.example 为 .env{`\n`}填写 AI_API_KEY{`\n`}重新运行 npm run demo</code></pre><p className="privacy-note">密钥只由本地 Node 服务读取，不会进入网页、构建产物或日志。</p></>}<button className="wide-button" onClick={() => setSetupOpen(false)}><Check size={17} />知道了</button></section></div>}

      <div className="toast-stack" aria-live="polite">{toasts.map((item) => <div key={item.id} className={`toast ${item.tone || ''}`}>{item.tone === 'success' && <Check size={16} />}{item.message}</div>)}</div>
    </div>
  );
}

export default App;
