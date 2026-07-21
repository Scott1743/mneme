"""Single-file Web UI for ``mneme serve`` (P1).

The entire frontend is this one ``INDEX_HTML`` string — HTML + CSS +
vanilla ES2017 JS, zero CDN, zero npm. ``webserver`` injects the
per-process session token by replacing ``__MNEME_TOKEN__`` before
serving ``GET /``. All data comes from ``/api/*`` fetches carrying the
``X-Mneme-Token`` header; no cookies, no localStorage.

Design: ``docs/design/webserver-prototype.md`` §6; layout and styling
follow the approved interactive prototype ``webserver-mock.html``.
"""

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mneme Web UI</title>
<style>
  :root{
    --bg:#f5f6f8; --card:#ffffff; --border:#e3e6ea; --text:#1f2329; --muted:#6b7280;
    --accent:#2563eb; --accent-soft:#eaf1fe;
    --err:#dc2626; --err-bg:#fee2e2;
    --warn:#b45309; --warn-bg:#fef3c7;
    --ok:#16a34a; --ok-bg:#dcfce7;
    --info:#475569; --info-bg:#e2e8f0;
    --radius:8px;
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
       background:var(--bg);color:var(--text);font-size:14px;line-height:1.6;}
  code,pre,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
  header{background:var(--card);border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;}
  .brand{font-size:18px;font-weight:700;}
  .brand span{color:var(--accent);}
  .bundle-path{color:var(--muted);font-size:13px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:2px 10px;}
  nav{display:flex;gap:4px;flex-wrap:wrap;margin-left:auto;}
  nav a{padding:6px 14px;border-radius:6px;color:var(--muted);text-decoration:none;font-weight:500;cursor:pointer;}
  nav a:hover{background:var(--bg);color:var(--text);}
  nav a.active{background:var(--accent-soft);color:var(--accent);}
  main{max-width:1100px;margin:24px auto;padding:0 20px;}
  .tab{display:none;}
  .tab.active{display:block;}
  .card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;margin-bottom:18px;}
  .card h3{font-size:15px;margin-bottom:12px;display:flex;align-items:center;gap:8px;}
  .grid-3{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;}
  .grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px;}
  .badge{display:inline-block;padding:1px 9px;border-radius:10px;font-size:12px;font-weight:600;}
  .badge.ERROR{background:var(--err-bg);color:var(--err);}
  .badge.WARN{background:var(--warn-bg);color:var(--warn);}
  .badge.OK{background:var(--ok-bg);color:var(--ok);}
  .badge.INFO{background:var(--info-bg);color:var(--info);}
  .btn{border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:6px;padding:6px 14px;cursor:pointer;font-size:13px;}
  .btn:hover{border-color:var(--accent);color:var(--accent);}
  .btn.primary{background:var(--accent);color:#fff;border-color:var(--accent);}
  .btn.primary:hover{background:#1d4ed8;}
  .btn:disabled{opacity:.6;cursor:default;}
  .hint{color:var(--muted);font-size:13px;}
  mark{background:#fde68a;padding:0 2px;border-radius:2px;}
  a.link{color:var(--accent);text-decoration:none;cursor:pointer;}
  a.link:hover{text-decoration:underline;}
  .health-big{font-size:22px;font-weight:700;display:flex;align-items:center;gap:10px;}
  .check-icon{width:34px;height:34px;border-radius:50%;background:var(--ok-bg);color:var(--ok);display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;}
  .check-icon.bad{background:var(--err-bg);color:var(--err);}
  .stat-row{display:flex;gap:24px;flex-wrap:wrap;}
  .stat-num{font-size:24px;font-weight:700;color:var(--accent);}
  .stat-label{color:var(--muted);font-size:13px;}
  .idx-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px dashed var(--border);}
  .idx-row:last-child{border-bottom:none;}
  .log-item{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;padding:5px 0;border-bottom:1px dashed var(--border);}
  .log-item:last-child{border-bottom:none;}
  .toast{display:none;background:var(--ok-bg);color:var(--ok);border:1px solid var(--ok);border-radius:6px;padding:8px 14px;margin-bottom:14px;font-size:13px;}
  .toast.err{background:var(--err-bg);color:var(--err);border-color:var(--err);}
  .search-bar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px;}
  input[type=text],select{border:1px solid var(--border);border-radius:6px;padding:7px 12px;font-size:14px;background:#fff;color:var(--text);}
  input[type=text]{flex:1;min-width:220px;}
  .result-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 18px;margin-bottom:12px;cursor:pointer;}
  .result-card:hover{border-color:var(--accent);}
  .result-card .r-title{font-weight:600;font-size:15px;}
  .result-card .r-path{color:var(--muted);font-size:12px;margin:2px 0 6px;}
  .result-card .r-snippet{color:var(--text);font-size:13px;}
  .browse-wrap{display:grid;grid-template-columns:260px 1fr;gap:18px;}
  @media (max-width:800px){.browse-wrap{grid-template-columns:1fr;}}
  .tree-group{margin-bottom:12px;}
  .tree-group .tg-title{font-weight:600;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;}
  .tree-item{padding:3px 8px;border-radius:5px;cursor:pointer;font-size:13px;display:flex;gap:6px;align-items:center;}
  .tree-item:hover{background:var(--bg);}
  .tree-item.active{background:var(--accent-soft);color:var(--accent);}
  .tree-item.orphan{color:#9ca3af;}
  .tag-mini{font-size:10px;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:0 6px;color:var(--muted);}
  .md-toolbar{display:flex;gap:10px;align-items:center;margin-bottom:12px;}
  .md-body h1{font-size:22px;margin:14px 0 8px;}
  .md-body h2{font-size:18px;margin:12px 0 6px;}
  .md-body h3{font-size:15px;margin:10px 0 5px;}
  .md-body p{margin:8px 0;}
  .md-body ul{margin:8px 0 8px 22px;}
  .md-body pre{background:#f1f3f5;border:1px solid var(--border);border-radius:6px;padding:10px 12px;margin:10px 0;overflow-x:auto;font-size:13px;}
  .md-body code{background:#f1f3f5;border-radius:4px;padding:1px 5px;font-size:12.5px;}
  .md-body pre code{background:none;padding:0;}
  .md-body blockquote{border-left:3px solid var(--border);padding-left:12px;color:var(--muted);margin:8px 0;}
  .md-src{white-space:pre-wrap;background:#f8f9fa;border:1px solid var(--border);border-radius:6px;padding:14px;font-size:13px;}
  .links-cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
  @media (max-width:700px){.links-cols{grid-template-columns:1fr;}}
  .link-list li{margin:4px 0;list-style:none;}
  .rule-strip{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:16px;}
  .rule-chip{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:6px 12px;font-size:13px;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:top;}
  th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px;}
  .banner{background:var(--warn-bg);border:1px solid #f59e0b;color:#92400e;border-radius:var(--radius);padding:12px 18px;margin-bottom:18px;font-weight:600;}
  .rule-item{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px dashed var(--border);font-size:13.5px;}
  .rule-item:last-child{border-bottom:none;}
  .ri-icon{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;}
  .ri-pass{background:var(--ok-bg);color:var(--ok);}
  .ri-fail{background:var(--err-bg);color:var(--err);}
  .ri-warn{background:var(--warn-bg);color:var(--warn);}
  .modal-mask{display:none;position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:50;align-items:center;justify-content:center;padding:24px;}
  .modal-mask.open{display:flex;}
  .modal{background:var(--card);border-radius:var(--radius);border:1px solid var(--border);max-width:720px;width:100%;max-height:84vh;display:flex;flex-direction:column;box-shadow:0 12px 40px rgba(15,23,42,.25);}
  .modal-head{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid var(--border);font-weight:600;}
  .modal-body{padding:16px 18px;overflow:auto;}
  .modal-body pre{background:#f8f9fa;border:1px solid var(--border);border-radius:6px;padding:12px 14px;font-size:12.5px;white-space:pre-wrap;word-break:break-word;}
  .modal-foot{display:flex;gap:10px;justify-content:flex-end;padding:12px 18px;border-top:1px solid var(--border);}
  .btn.small{padding:2px 9px;font-size:12px;}
  .p2-badge{position:absolute;top:-8px;right:-8px;background:#7c3aed;color:#fff;font-size:10px;font-weight:700;border-radius:8px;padding:0 6px;line-height:16px;pointer-events:none;}
  .btn-wrap{position:relative;display:inline-block;}
  #graphCanvas{width:100%;height:480px;border:1px solid var(--border);border-radius:var(--radius);background:#fff;cursor:pointer;display:block;}
  .legend{display:flex;gap:18px;flex-wrap:wrap;margin-top:12px;font-size:13px;color:var(--muted);}
  .legend .dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;}
</style>
</head>
<body>

<header>
  <div class="brand">Mneme<span> Web UI</span> <span class="hint" style="font-weight:400">（P1 · 只读 + reindex）</span></div>
  <div class="bundle-path mono" id="bundlePath" title="bundle 路径">bundle: …</div>
  <nav id="nav">
    <a data-tab="overview">总览</a>
    <a data-tab="search">搜索</a>
    <a data-tab="browse">浏览</a>
    <a data-tab="lint">体检</a>
    <a data-tab="dream">Dream</a>
    <a data-tab="graph">图谱</a>
  </nav>
</header>

<main>
  <div class="toast" id="toast"></div>

  <!-- ========== 空 bundle 引导页 ========== -->
  <section class="tab" id="tab-empty">
    <div class="card">
      <h3>尚未找到可用的 wiki bundle</h3>
      <p class="hint" style="margin-bottom:12px;">
        当前没有解析到已初始化的 OKF bundle（缺少 <code>index.md</code>）。
        请先初始化一个 bundle，再用 <code>--bundle</code> 参数重启本面板：
      </p>
      <pre class="md-src mono">python3 ~/.claude/skills/mneme/scripts/mneme.py init ~/wiki
python3 ~/.claude/skills/mneme/scripts/mneme.py serve --bundle ~/wiki --open</pre>
      <p class="hint" style="margin-top:12px;">
        bundle 解析优先级：<code>--bundle</code> &gt; <code>$MNEME_BUNDLE</code> &gt;
        <code>~/.config/mneme/config.toml</code> &gt; cwd 祖先 <code>index.md</code> &gt; <code>./wiki</code>。
      </p>
    </div>
  </section>

  <!-- ========== 总览 ========== -->
  <section class="tab" id="tab-overview">
    <div class="grid-2">
      <div class="card">
        <h3>健康度</h3>
        <div class="health-big"><span class="check-icon" id="healthIcon">✓</span> <span class="badge ERROR" id="errBadge">0 ERROR</span> <span class="badge WARN" id="warnBadge">0 WARN</span></div>
        <p class="hint" style="margin:10px 0 14px;" id="healthHint">加载中…</p>
        <button class="btn primary" id="btnRelint" onclick="relint(this)">重新体检</button>
        <button class="btn" onclick="go('lint')">查看诊断 →</button>
      </div>
      <div class="card">
        <h3>页面统计</h3>
        <div class="stat-row" id="pageStats"></div>
        <p class="hint" style="margin-top:12px;" id="pageStatsHint"></p>
      </div>
      <div class="card">
        <h3>索引状态</h3>
        <div id="indexRows"></div>
        <div style="margin-top:12px;">
          <button class="btn" id="btnReindex1" onclick="doReindex(this)">重建索引</button>
        </div>
      </div>
      <div class="card">
        <h3>最近动态 <span class="hint" style="font-weight:400">（log.md 尾部）</span></h3>
        <div id="recentLog"></div>
      </div>
    </div>
  </section>

  <!-- ========== 搜索 ========== -->
  <section class="tab" id="tab-search">
    <div class="card">
      <h3>搜索 wiki</h3>
      <div class="search-bar">
        <input type="text" id="searchInput" placeholder="输入关键词，如：OKF、dream、索引…">
        <select id="searchMode">
          <option value="auto">mode: auto</option>
          <option value="fts">mode: fts</option>
          <option value="hybrid">mode: hybrid</option>
          <option value="graph">mode: graph</option>
          <option value="l2">mode: l2</option>
        </select>
        <select id="searchType"><option value="">type: 全部</option></select>
        <button class="btn primary" onclick="doSearch()">搜索</button>
      </div>
      <div class="hint" id="searchMeta">输入关键词后回车，或点击「搜索」。结果为候选导航，答案以完整页面为准。</div>
    </div>
    <div id="searchResults"></div>
  </section>

  <!-- ========== 浏览 ========== -->
  <section class="tab" id="tab-browse">
    <div class="browse-wrap">
      <div class="card">
        <h3>目录</h3>
        <div class="search-bar" style="margin-bottom:10px;">
          <select id="browseTypeFilter" style="flex:1" onchange="renderTree()"><option value="">type: 全部</option></select>
        </div>
        <div class="search-bar" style="margin-bottom:12px;">
          <select id="browseTagFilter" style="flex:1" onchange="renderTree()"><option value="">tag: 全部</option></select>
        </div>
        <div id="tree"></div>
      </div>
      <div class="card">
        <div class="md-toolbar">
          <strong id="pageTitle" style="font-size:16px;"></strong>
          <span class="hint mono" id="pagePath"></span>
          <span style="margin-left:auto"></span>
          <button class="btn" id="btnViewRender" onclick="setView('render')">渲染</button>
          <button class="btn" id="btnViewSrc" onclick="setView('src')">源</button>
        </div>
        <div id="pageBody"><p class="hint">从左侧目录选择一个页面。</p></div>
        <div class="links-cols" style="margin-top:18px;">
          <div><h3 style="font-size:13px;color:var(--muted)">出链</h3><ul class="link-list" id="outLinks"></ul></div>
          <div><h3 style="font-size:13px;color:var(--muted)">入链</h3><ul class="link-list" id="inLinks"></ul></div>
        </div>
      </div>
    </div>
  </section>

  <!-- ========== 体检 ========== -->
  <section class="tab" id="tab-lint">
    <div class="card">
      <h3>诊断 <span class="hint" style="font-weight:400">（mneme lint）</span>
        <span style="margin-left:auto"></span>
        <button class="btn" onclick="openLintPrompt(null)">复制全部诊断</button>
      </h3>
      <div class="rule-strip" id="ruleStrip"></div>
      <table>
        <thead><tr><th style="width:80px">severity</th><th style="width:170px">rule</th><th style="width:220px">路径</th><th>detail</th><th style="width:100px">操作</th></tr></thead>
        <tbody id="lintBody"></tbody>
      </table>
    </div>
    <div class="grid-2">
      <div class="card">
        <h3>孤儿页（无任何入链）</h3>
        <ul class="link-list" id="orphanList"></ul>
      </div>
      <div class="card">
        <h3>索引维护</h3>
        <p class="hint" style="margin-bottom:12px;">FTS5 与 Graph 均为 disposable accelerator，可随时删除重建。本按钮只重建缓存，不改 Markdown。</p>
        <button class="btn" id="btnReindex2" onclick="doReindex(this)">重建索引</button>
      </div>
    </div>
  </section>

  <!-- ========== Dream ========== -->
  <section class="tab" id="tab-dream">
    <div class="banner">⚠ 本面板不执行写盘；写入请在 agent 会话中完成 dream 审批流。</div>
    <div class="card" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
      <button class="btn" id="btnReaudit" onclick="reaudit(this)">重新审计</button>
      <button class="btn primary" onclick="openDreamModal()">发起 dream</button>
      <span class="btn-wrap" title="需先在预览中确认变更（P2 功能）">
        <button class="btn" disabled>确认写入</button>
        <span class="p2-badge">P2</span>
      </span>
      <span class="hint">写侧操作均需审批；当前为只读审计视图。</span>
    </div>
    <div class="grid-2">
      <div class="card">
        <h3>OKF Hard Rules <span class="hint" style="font-weight:400">（协议级 MUST）</span></h3>
        <div id="okfRules"></div>
      </div>
      <div class="card">
        <h3>Mneme Writer Rules <span class="hint" style="font-weight:400">（写作纪律）</span></h3>
        <div id="writerRules"></div>
      </div>
      <div class="card">
        <h3>Graph 健康摘要</h3>
        <div class="stat-row" id="dreamGraphStats"></div>
        <p class="hint" style="margin-top:10px;" id="dreamGraphHint"></p>
      </div>
      <div class="card">
        <h3>审计元信息</h3>
        <div id="dreamMeta"></div>
      </div>
    </div>
  </section>

  <!-- ========== 图谱 ========== -->
  <section class="tab" id="tab-graph">
    <div class="card">
      <h3>知识图谱 <span class="hint" style="font-weight:400">（Markdown 互链力导向布局，点击节点跳转浏览）</span></h3>
      <canvas id="graphCanvas"></canvas>
      <div class="legend" id="graphLegend"></div>
    </div>
  </section>
</main>

<!-- ========== 通用模态框（复制提示词 / 发起 dream） ========== -->
<div class="modal-mask" id="modalMask" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-head"><span id="modalTitle">提示词</span></div>
    <div class="modal-body" id="modalBody"></div>
    <div class="modal-foot">
      <button class="btn" onclick="closeModal()">关闭</button>
      <button class="btn primary" id="modalCopyBtn">复制到剪贴板</button>
    </div>
  </div>
</div>

<script>
/* ==================== API 基础 ==================== */
const TOKEN = "__MNEME_TOKEN__";
async function api(path, opts){
  const r = await fetch(path, Object.assign({headers:{'X-Mneme-Token': TOKEN}}, opts||{}));
  let data = null;
  try{ data = await r.json(); }catch(e){ data = {error:'服务返回了非 JSON 内容', code:'internal'}; }
  if(!r.ok){
    const err = new Error((data && data.error) || ('HTTP '+r.status));
    err.status = r.status; err.code = data && data.code;
    throw err;
  }
  return data;
}

/* ==================== 全局状态 ==================== */
let STATUS = null;        // /api/status
let PAGES = [];           // /api/pages
let PAGEMAP = {};         // path -> page summary
let LINT = null;          // /api/lint
let DREAM = null;         // /api/dream
let GRAPH = null;         // /api/graph

/* ==================== 路由 ==================== */
const TABS = ['overview','search','browse','lint','dream','graph'];
function go(tab, arg){
  location.hash = '#/' + tab + (arg ? '/' + encodeURIComponent(arg) : '');
}
function applyRoute(){
  if(!STATUS || !STATUS.initialized){
    document.querySelectorAll('.tab').forEach(el=>el.classList.remove('active'));
    document.getElementById('tab-empty').classList.add('active');
    document.querySelectorAll('#nav a').forEach(a=>a.classList.remove('active'));
    return;
  }
  const parts = location.hash.replace(/^#\//,'').split('/');
  let tab = parts[0] || 'overview';
  if(!TABS.includes(tab)) tab = 'overview';
  const arg = parts[1] ? decodeURIComponent(parts[1]) : null;
  document.querySelectorAll('.tab').forEach(el=>el.classList.remove('active'));
  document.getElementById('tab-'+tab).classList.add('active');
  document.querySelectorAll('#nav a').forEach(a=>a.classList.toggle('active', a.dataset.tab===tab));
  if(tab==='browse'){ if(arg) openPage(arg); }
  if(tab==='lint'){ loadLint(); }
  if(tab==='dream'){ loadDream(); }
  if(tab==='graph'){ loadGraph(); }
}
document.querySelectorAll('#nav a').forEach(a=>{
  a.addEventListener('click', ()=>go(a.dataset.tab));
});
window.addEventListener('hashchange', applyRoute);

/* ==================== Toast ==================== */
let toastTimer=null;
function toast(msg, isErr){
  const t=document.getElementById('toast');
  t.textContent=msg; t.style.display='block';
  t.classList.toggle('err', !!isErr);
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>t.style.display='none', 3200);
}

/* ==================== 总览 ==================== */
function renderOverview(){
  const s = STATUS;
  document.getElementById('bundlePath').textContent = 'bundle: ' + (s.bundle || '(未解析)');
  const errs = s.lint.errors, warns = s.lint.warnings;
  document.getElementById('errBadge').textContent = errs + ' ERROR';
  document.getElementById('warnBadge').textContent = warns + ' WARN';
  document.getElementById('healthIcon').textContent = errs ? '✗' : '✓';
  document.getElementById('healthIcon').classList.toggle('bad', errs > 0);
  document.getElementById('healthHint').textContent =
    'mneme v' + s.version + ' · 页面 ' + s.pages.total + ' 个 · 规则诊断实时计算（不存储）';

  const byType = s.pages.by_type || {};
  const order = Object.keys(byType).sort((a,b)=>byType[b]-byType[a]).slice(0,3);
  document.getElementById('pageStats').innerHTML =
    '<div><div class="stat-num">'+s.pages.total+'</div><div class="stat-label">总页面</div></div>'+
    order.map(t=>'<div><div class="stat-num">'+byType[t]+'</div><div class="stat-label">'+esc(t)+'</div></div>').join('');
  document.getElementById('pageStatsHint').textContent = '孤儿页 ' + s.pages.orphans + ' 个';

  const idx = s.indexes;
  const row = (name, badge)=>'<div class="idx-row"><span>'+name+'</span>'+badge+'</div>';
  document.getElementById('indexRows').innerHTML =
    row('FTS5 全文索引', idx.fts5.exists ? '<span class="badge OK">✓ 就绪</span>' : '<span class="badge INFO">✗ 未构建</span>') +
    row('Graph 关系图', !idx.graph.exists ? '<span class="badge INFO">✗ 未构建</span>'
        : idx.graph.fresh ? '<span class="badge OK">✓ 新鲜</span>' : '<span class="badge WARN">⚠ 已过期</span>') +
    row('L2 语义索引', idx.l2.exists ? '<span class="badge OK">✓ 已启用</span>' : '<span class="badge INFO">✗ 未启用</span>');

  document.getElementById('recentLog').innerHTML = s.recent_log.length
    ? s.recent_log.map(l=>'<div class="log-item">'+esc(l)+'</div>').join('')
    : '<div class="hint">log.md 暂无条目</div>';
}

async function refreshStatus(){
  STATUS = await api('/api/status');
  renderOverview();
}

async function relint(btn){
  btn.disabled=true; btn.textContent='体检中…';
  try{
    LINT = await api('/api/lint');
    await refreshStatus();
    renderLint();
    toast('✓ 体检完成：' + LINT.errors + ' ERROR · ' + LINT.warnings + ' WARN');
  }catch(e){ toast('体检失败：'+e.message, true); }
  btn.disabled=false; btn.textContent='重新体检';
}

async function doReindex(btn){
  btn.disabled=true; btn.textContent='重建中…';
  try{
    const r = await api('/api/reindex', {method:'POST'});
    const g = r.graph ? (' · Graph '+r.graph.entities+' 实体 / '+r.graph.relations+' 关系') : ' · Graph 未构建（未重建）';
    toast('✓ 索引重建完成：FTS5 '+r.fts_pages+' 页'+g);
    await refreshStatus();
  }catch(e){ toast('重建失败：'+e.message, true); }
  btn.disabled=false; btn.textContent='重建索引';
}

/* ==================== 搜索 ==================== */
function highlight(text, q){
  let out = esc(text);
  if(q){
    const safe = q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    out = out.replace(new RegExp('('+safe+')','gi'), '<mark>$1</mark>');
  }
  return out;
}
async function doSearch(){
  const q = document.getElementById('searchInput').value.trim();
  const type = document.getElementById('searchType').value;
  const mode = document.getElementById('searchMode').value;
  if(!q){ toast('请输入关键词', true); return; }
  const meta = document.getElementById('searchMeta');
  meta.textContent = '搜索中…';
  try{
    const r = await api('/api/search?q='+encodeURIComponent(q)+'&k=20&mode='+encodeURIComponent(mode));
    let results = r.candidates;
    if(type) results = results.filter(c=>{ const p=PAGEMAP[c.path]; return p && p.type===type; });
    meta.textContent = 'mode='+r.mode+' · 命中 '+results.length+' 条';
    document.getElementById('searchResults').innerHTML = results.map(c=>{
      const p = PAGEMAP[c.path];
      const typeBadge = p && p.type ? ' <span class="badge INFO" style="margin-left:6px">'+esc(p.type)+'</span>' : '';
      return '<div class="result-card" onclick="go(\'browse\',\''+encodeURIComponent(c.path)+'\')">'+
        '<div class="r-title">'+highlight(c.title || c.path, q)+typeBadge+'</div>'+
        '<div class="r-path mono">'+esc(c.path)+'</div>'+
        '<div class="r-snippet">'+highlight(c.snippet, q)+'</div>'+
      '</div>';
    }).join('') || '<div class="card hint">无结果。</div>';
  }catch(e){
    meta.textContent = '搜索失败：'+e.message;
    toast('搜索失败：'+e.message, true);
  }
}
document.getElementById('searchInput').addEventListener('keydown', e=>{ if(e.key==='Enter') doSearch(); });

/* ==================== 浏览 ==================== */
let currentPage = null;
let currentPageData = null;
let viewMode = 'render';

function fillSelect(id, values, label){
  const sel = document.getElementById(id);
  sel.innerHTML = '<option value="">'+label+': 全部</option>' +
    values.map(v=>'<option value="'+esc(v)+'">'+esc(v)+'</option>').join('');
}

function renderTree(){
  const tf = document.getElementById('browseTypeFilter').value;
  const gf = document.getElementById('browseTagFilter').value;
  const pass = p=>{
    if(tf && p.type!==tf) return false;
    if(gf && !p.tags.includes(gf)) return false;
    return true;
  };
  const groups = {};
  PAGES.forEach(p=>{
    if(!pass(p)) return;
    const seg = p.orphan ? '(orphans)' : (p.path.split('/')[1] || '(root)') + '/';
    (groups[seg] = groups[seg] || []).push(p);
  });
  const names = Object.keys(groups).sort((a,b)=>{
    if(a==='(orphans)') return 1;
    if(b==='(orphans)') return -1;
    return a<b?-1:1;
  });
  document.getElementById('tree').innerHTML = names.map(name=>{
    const items = groups[name];
    const isOrphan = name==='(orphans)';
    return '<div class="tree-group"><div class="tg-title">'+esc(name)+'</div>'+
      items.map(p=>'<div class="tree-item'+(isOrphan?' orphan':'')+(p.path===currentPage?' active':'')+
        '" onclick="go(\'browse\',\''+encodeURIComponent(p.path)+'\')">'+
        esc(p.title || p.path)+' <span class="tag-mini">'+esc(p.type||'?')+'</span></div>').join('')+
      '</div>';
  }).join('') || '<div class="hint">无匹配页面</div>';
}

/* ---- 极简 Markdown 渲染器（近似渲染；权威是 Markdown 源） ---- */
function renderMarkdown(md){
  const lines = md.split('\n');
  let html='', inCode=false, inList=false;
  const inline = s => esc(s)
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\((\/[^)]+)\)/g,'<a class="link" data-mdlink="$2">$1</a>');
  for(const raw of lines){
    const line = raw;
    if(line.trim().startsWith('```')){
      if(inCode){ html+='</code></pre>'; inCode=false; }
      else { html+='<pre><code>'; inCode=true; }
      continue;
    }
    if(inCode){ html+=esc(line)+'\n'; continue; }
    const t=line.trim();
    if(!t){ if(inList){html+='</ul>';inList=false;} continue; }
    if(t.startsWith('### ')){ html+='<h3>'+inline(t.slice(4))+'</h3>'; continue; }
    if(t.startsWith('## ')){ html+='<h2>'+inline(t.slice(3))+'</h2>'; continue; }
    if(t.startsWith('# ')){ html+='<h1>'+inline(t.slice(2))+'</h1>'; continue; }
    if(t.startsWith('&gt; ')||t.startsWith('> ')){ html+='<blockquote>'+inline(t.replace(/^&gt; |^> /,''))+'</blockquote>'; continue; }
    if(t.startsWith('- ')){
      if(!inList){ html+='<ul>'; inList=true; }
      html+='<li>'+inline(t.slice(2))+'</li>'; continue;
    }
    html+='<p>'+inline(t)+'</p>';
  }
  if(inList) html+='</ul>';
  if(inCode) html+='</code></pre>';
  return html;
}

async function openPage(path){
  try{
    const data = await api('/api/page?path='+encodeURIComponent(path));
    currentPage = data.path;
    currentPageData = data;
    document.getElementById('pageTitle').textContent = data.frontmatter.title || data.path;
    document.getElementById('pagePath').textContent = data.path;
    renderTree();
    setView(viewMode);
    const li = p=>'<li><a class="link mono" onclick="go(\'browse\',\''+encodeURIComponent(p)+'\')">'+esc(p)+'</a>'+(PAGEMAP[p]?'':' <span class="badge WARN">断链</span>')+'</li>';
    document.getElementById('outLinks').innerHTML = data.outlinks.length? data.outlinks.map(li).join('') : '<li class="hint">无</li>';
    document.getElementById('inLinks').innerHTML = data.inlinks.length? data.inlinks.map(li).join('') : '<li class="hint">无（孤儿页）</li>';
  }catch(e){
    toast('打开页面失败：'+e.message, true);
  }
}

function setView(mode){
  viewMode=mode;
  const body=document.getElementById('pageBody');
  if(!currentPageData){ body.innerHTML='<p class="hint">从左侧目录选择一个页面。</p>'; return; }
  document.getElementById('btnViewRender').classList.toggle('primary', mode==='render');
  document.getElementById('btnViewSrc').classList.toggle('primary', mode==='src');
  if(mode==='render'){
    body.className='md-body';
    body.innerHTML=renderMarkdown(currentPageData.body);
    body.querySelectorAll('[data-mdlink]').forEach(a=>{
      a.addEventListener('click', ()=>go('browse', a.dataset.mdlink));
    });
  }else{
    body.className='';
    body.innerHTML='<div class="md-src mono">'+esc(currentPageData.raw)+'</div>';
  }
}

/* ==================== 体检 ==================== */
async function loadLint(){
  if(LINT){ renderLint(); return; }
  try{
    LINT = await api('/api/lint');
    renderLint();
  }catch(e){ toast('加载诊断失败：'+e.message, true); }
}

function diagPathLink(path){
  if(path && path.endsWith('.md')){
    const rel = path.startsWith('/') ? path : '/'+path;
    return '<a class="link mono" onclick="go(\'browse\',\''+encodeURIComponent(rel)+'\')">'+esc(path)+'</a>';
  }
  return '<span class="mono">'+esc(path)+'</span>';
}

function renderLint(){
  if(!LINT) return;
  const diags = LINT.diagnostics;
  const counts={};
  diags.forEach(d=>{ counts[d.code]=(counts[d.code]||0)+1; });
  document.getElementById('ruleStrip').innerHTML =
    '<span class="rule-chip"><span class="badge ERROR">ERROR '+LINT.errors+'</span></span>'+
    '<span class="rule-chip"><span class="badge WARN">WARN '+LINT.warnings+'</span></span>'+
    Object.keys(counts).sort().map(r=>'<span class="rule-chip mono">'+esc(r)+' ×'+counts[r]+'</span>').join('');
  document.getElementById('lintBody').innerHTML = diags.map((d,i)=>
    '<tr><td><span class="badge '+d.severity+'">'+d.severity+'</span></td>'+
    '<td class="mono">'+esc(d.code)+'</td>'+
    '<td>'+diagPathLink(d.path)+'</td>'+
    '<td>'+esc(d.detail)+'</td>'+
    '<td><button class="btn small" onclick="openLintPrompt('+i+')">复制提示词</button></td></tr>').join('')
    || '<tr><td colspan="5" class="hint">无诊断 —— 很健康。</td></tr>';
  document.getElementById('orphanList').innerHTML = LINT.orphan_paths.length
    ? LINT.orphan_paths.map(p=>'<li><a class="link mono" onclick="go(\'browse\',\''+encodeURIComponent(p)+'\')">'+esc(p)+'</a> <span class="hint">—— 无入链，建议归档或补充互链</span></li>').join('')
    : '<li class="hint">无孤儿页</li>';
}

/* ==================== 模态框 / 提示词组装 ==================== */
let modalText='';
function openModal(title, text, noteHtml){
  modalText=text;
  document.getElementById('modalTitle').textContent=title;
  document.getElementById('modalBody').innerHTML =
    (noteHtml? '<div style="margin-bottom:12px;">'+noteHtml+'</div>' : '') +
    '<pre id="modalPre">'+esc(text)+'</pre>';
  document.getElementById('modalMask').classList.add('open');
}
function closeModal(){
  document.getElementById('modalMask').classList.remove('open');
}
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeModal(); });
document.getElementById('modalCopyBtn').addEventListener('click', ()=>{
  const done=()=>{ toast('✓ 已复制到剪贴板'); };
  const fallback=()=>{
    const pre=document.getElementById('modalPre');
    if(pre){
      const r=document.createRange(); r.selectNodeContents(pre);
      const sel=window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
    }
    try{
      const ta=document.createElement('textarea');
      ta.value=modalText; document.body.appendChild(ta);
      ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
      done(); return;
    }catch(e){}
    toast('自动复制不可用，文本已全选，请手动 Cmd/Ctrl+C 复制');
  };
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(modalText).then(done).catch(fallback);
  }else fallback();
});

function buildLintPrompt(diags){
  const lines = diags.map(d=>'- ['+d.severity+'] '+d.path+' — 规则 '+d.code+'：'+d.detail).join('\n');
  return '请修复 mneme wiki 的 lint 诊断。\n\n'+
    'Bundle 路径：'+(STATUS.bundle || '(未知)')+'\n'+
    '诊断（'+diags.length+' 条）：\n'+lines+'\n\n'+
    '规则出处：诊断 code 即规则 ID；OKF 协议级规则见 OKF SPEC v0.1'+
    '（§4 frontmatter / §6 index.md / §7 log.md / §9 容错消费契约），'+
    'MNEME- 前缀规则见 mneme 写作纪律（AGENTS.md / SKILL.md）。\n\n'+
    '约束：\n'+
    '1. 不要修改 sources/ 下的 raw sources；\n'+
    '2. 写入前先展示变更预览，等我确认后再落盘；\n'+
    '3. 如有页面改动，同步更新 index.md 与 log.md；\n'+
    '4. 修复后重跑 `mneme lint` 验证。';
}
function openLintPrompt(i){
  if(!LINT){ toast('诊断尚未加载', true); return; }
  const diags = (i===null||i===undefined) ? LINT.diagnostics : [LINT.diagnostics[i]];
  if(!diags.length){ toast('当前没有诊断可复制'); return; }
  const title = (i===null||i===undefined) ? '修复提示词 · 全部诊断（'+diags.length+' 条）' : '修复提示词 · 单条诊断';
  openModal(title, buildLintPrompt(diags));
}

function openDreamModal(){
  const bundle = (STATUS && STATUS.bundle) || '<bundle>';
  const text =
    '请对 bundle '+bundle+' 执行一次 dream：\n\n'+
    '1. 运行 `mneme dream --bundle '+bundle+'` 生成只读审计报告；\n'+
    '2. 向我展示报告（OKF Hard Rules + Mneme Writer Rules）；\n'+
    '3. 待我明确点头后，再用 Write / Edit 落盘概念页；\n'+
    '4. 同步更新 index.md 与 log.md，并重建 Graph + FTS5 索引。';
  openModal('发起 dream', text,
    '在宿主 agent 集成环境中，此按钮将唤起 agent 执行 dream 工作流并回这里等待你确认；'+
    '当前独立 server 模式下，请复制下面的 dream 指令文本粘贴给你的 agent：');
}
async function reaudit(btn){
  btn.disabled=true; btn.textContent='审计中…';
  try{
    DREAM = await api('/api/dream');
    renderDream();
    toast('✓ 审计完成');
  }catch(e){ toast('审计失败：'+e.message, true); }
  btn.disabled=false; btn.textContent='重新审计';
}

/* ==================== Dream ==================== */
async function loadDream(){
  if(DREAM){ renderDream(); return; }
  try{
    DREAM = await api('/api/dream');
    renderDream();
  }catch(e){ toast('加载 dream 审计失败：'+e.message, true); }
}

function renderDream(){
  if(!DREAM) return;
  const icon = ok => ok===true ? '<span class="ri-icon ri-pass">✓</span>'
                 : ok===false ? '<span class="ri-icon ri-fail">✗</span>'
                 : '<span class="ri-icon ri-warn">–</span>';
  const hard = DREAM.okf_hard_rules || [];
  const writer = DREAM.mneme_writer_rules || [];
  const err = DREAM._meta && DREAM._meta.error;
  document.getElementById('okfRules').innerHTML = err
    ? '<div class="rule-item">'+icon(null)+'<span>'+esc(err)+'</span></div>'
    : (hard.length
      ? hard.map(r=>'<div class="rule-item">'+icon(false)+'<span><span class="mono">'+esc(r.path)+'</span> — '+esc(r.rule)+'</span></div>').join('')
      : '<div class="rule-item">'+icon(true)+'<span>每个非保留 .md 均含 YAML frontmatter</span></div>');
  document.getElementById('writerRules').innerHTML = err
    ? '<div class="rule-item">'+icon(null)+'<span>'+esc(err)+'</span></div>'
    : (writer.length
      ? writer.map(r=>'<div class="rule-item">'+icon(false)+'<span><span class="mono">'+esc(r.path)+'</span> — '+esc(r.rule)+'</span></div>').join('')
      : '<div class="rule-item">'+icon(true)+'<span>所有概念页至少 1 个 tag</span></div>');
  const g = DREAM.graph;
  if(g && !g.error){
    document.getElementById('dreamGraphStats').innerHTML =
      '<div><div class="stat-num">'+g.entity_count+'</div><div class="stat-label">实体</div></div>'+
      '<div><div class="stat-num">'+g.relation_count+'</div><div class="stat-label">关系</div></div>'+
      '<div><div class="stat-num">'+g.connected_component_count+'</div><div class="stat-label">连通分量</div></div>';
    document.getElementById('dreamGraphHint').textContent = 'graph.db 派生缓存；可重建，不是事实来源。';
  }else{
    document.getElementById('dreamGraphStats').innerHTML = '<div class="hint">graph.db 未构建'+(g&&g.error?'（'+esc(g.error)+'）':'')+'</div>';
    document.getElementById('dreamGraphHint').textContent = '运行「重建索引」或 `mneme reindex --graph` 后可见。';
  }
  const meta = DREAM._meta || {};
  document.getElementById('dreamMeta').innerHTML =
    '<div class="log-item">候选概念页：'+(meta.candidate_count||0)+' 个</div>'+
    '<div class="log-item">模式：只读审计（'+(meta.writes ? esc(meta.writes) : 'no writes')+'）</div>';
}

/* ==================== 图谱（Canvas 力导向） ==================== */
const TYPE_COLOR = {Concept:'#3b82f6', Reference:'#22c55e', Topic:'#f97316', Source:'#a855f7', Summary:'#eab308'};
let graphState=null;
async function loadGraph(){
  try{
    GRAPH = await api('/api/graph');
  }catch(e){ toast('加载图谱失败：'+e.message, true); return; }
  graphState=null;
  const types = [...new Set(GRAPH.nodes.map(n=>n.type))];
  document.getElementById('graphLegend').innerHTML =
    types.map(t=>'<span><span class="dot" style="background:'+(TYPE_COLOR[t]||'#94a3b8')+'"></span>'+esc(t)+'</span>').join('') +
    '<span id="graphStats"></span>';
  requestAnimationFrame(drawGraph);
}
function initGraph(w,h){
  const nodes = GRAPH.nodes.map((n,i)=>({
    id:n.id, label:n.label, type:n.type,
    x: w/2 + Math.cos(i/Math.max(1,GRAPH.nodes.length)*Math.PI*2)*Math.min(w,h)*0.32 + (Math.random()-0.5)*30,
    y: h/2 + Math.sin(i/Math.max(1,GRAPH.nodes.length)*Math.PI*2)*Math.min(w,h)*0.32 + (Math.random()-0.5)*30,
    vx:0, vy:0
  }));
  const idx={}; nodes.forEach((n,i)=>idx[n.id]=i);
  const edges = GRAPH.edges.filter(([a,b])=>idx[a]!==undefined && idx[b]!==undefined).map(([a,b])=>[idx[a],idx[b]]);
  return {nodes, edges};
}
function tickGraph(st,w,h){
  const {nodes,edges}=st;
  const REP=2600, SPRING=0.012, REST=130, CENTER=0.006, DAMP=0.82;
  for(let i=0;i<nodes.length;i++){
    for(let j=i+1;j<nodes.length;j++){
      let dx=nodes[i].x-nodes[j].x, dy=nodes[i].y-nodes[j].y;
      let d2=dx*dx+dy*dy||1;
      const f=REP/d2;
      const d=Math.sqrt(d2);
      dx/=d; dy/=d;
      nodes[i].vx+=dx*f; nodes[i].vy+=dy*f;
      nodes[j].vx-=dx*f; nodes[j].vy-=dy*f;
    }
  }
  edges.forEach(([a,b])=>{
    let dx=nodes[b].x-nodes[a].x, dy=nodes[b].y-nodes[a].y;
    const d=Math.sqrt(dx*dx+dy*dy)||1;
    const f=(d-REST)*SPRING;
    dx/=d; dy/=d;
    nodes[a].vx+=dx*f*d*0.1; nodes[a].vy+=dy*f*d*0.1;
    nodes[b].vx-=dx*f*d*0.1; nodes[b].vy-=dy*f*d*0.1;
  });
  nodes.forEach(n=>{
    n.vx+=(w/2-n.x)*CENTER; n.vy+=(h/2-n.y)*CENTER;
    n.vx*=DAMP; n.vy*=DAMP;
    n.x=Math.max(40,Math.min(w-40,n.x+n.vx));
    n.y=Math.max(30,Math.min(h-30,n.y+n.vy));
  });
}
function drawGraphFrame(ctx,st,w,h){
  ctx.clearRect(0,0,w,h);
  ctx.strokeStyle='#d7dce2'; ctx.lineWidth=1.2;
  st.edges.forEach(([a,b])=>{
    ctx.beginPath(); ctx.moveTo(st.nodes[a].x,st.nodes[a].y);
    ctx.lineTo(st.nodes[b].x,st.nodes[b].y); ctx.stroke();
  });
  st.nodes.forEach(n=>{
    const c=TYPE_COLOR[n.type]||'#94a3b8';
    ctx.beginPath(); ctx.arc(n.x,n.y,10,0,Math.PI*2);
    ctx.fillStyle=c; ctx.fill();
    ctx.lineWidth=2; ctx.strokeStyle='#fff'; ctx.stroke();
    ctx.font='12px -apple-system, "PingFang SC", sans-serif';
    ctx.fillStyle='#1f2329'; ctx.textAlign='center';
    ctx.fillText(n.label, n.x, n.y+26);
  });
}
function drawGraph(){
  const cv=document.getElementById('graphCanvas');
  if(!GRAPH || !GRAPH.nodes.length){
    const ctx0=cv.getContext('2d'); ctx0.clearRect(0,0,cv.width,cv.height);
    document.getElementById('graphStats').textContent = '· 无页面可绘制';
    return;
  }
  const w=cv.clientWidth||800, h=480;
  const dpr=window.devicePixelRatio||1;
  cv.width=w*dpr; cv.height=h*dpr;
  const ctx=cv.getContext('2d'); ctx.scale(dpr,dpr);
  if(!graphState) graphState=initGraph(w,h);
  for(let i=0;i<220;i++) tickGraph(graphState,w,h);
  let frame=0;
  function anim(){
    if(!document.getElementById('tab-graph').classList.contains('active')) return;
    tickGraph(graphState,w,h);
    drawGraphFrame(ctx,graphState,w,h);
    if(++frame<60) requestAnimationFrame(anim);
  }
  drawGraphFrame(ctx,graphState,w,h);
  requestAnimationFrame(anim);
  document.getElementById('graphStats').textContent =
    '· 节点 '+graphState.nodes.length+' · 边 '+graphState.edges.length;
  cv.onclick = e=>{
    const r=cv.getBoundingClientRect();
    const mx=e.clientX-r.left, my=e.clientY-r.top;
    for(const n of graphState.nodes){
      const dx=n.x-mx, dy=n.y-my;
      if(dx*dx+dy*dy<18*18){ go('browse', n.id); return; }
    }
  };
}

/* ==================== 工具 ==================== */
function esc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ==================== 启动 ==================== */
async function boot(){
  try{
    STATUS = await api('/api/status');
  }catch(e){
    document.getElementById('bundlePath').textContent = 'bundle: (连接失败)';
    toast('无法连接 /api/status：'+e.message, true);
    return;
  }
  renderOverview();
  if(STATUS.initialized){
    try{
      const pr = await api('/api/pages');
      PAGES = pr.pages;
      PAGES.forEach(p=>{ PAGEMAP[p.path]=p; });
      fillSelect('searchType', [...new Set(PAGES.map(p=>p.type).filter(Boolean))].sort(), 'type');
      fillSelect('browseTypeFilter', [...new Set(PAGES.map(p=>p.type).filter(Boolean))].sort(), 'type');
      fillSelect('browseTagFilter', [...new Set(PAGES.flatMap(p=>p.tags))].sort(), 'tag');
      renderTree();
    }catch(e){ toast('加载页面清单失败：'+e.message, true); }
  }
  applyRoute();
}
boot();
</script>
</body>
</html>
"""
