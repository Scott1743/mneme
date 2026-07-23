"""Offline Web UI for ``mneme serve``.

The application shell is this ``INDEX_HTML`` string — HTML + CSS + vanilla
ES2017 JS, with no CDN or runtime package installation. The pinned G6 browser
renderer is vendored beside this module and served from a strict local asset
path. ``webserver`` injects the per-process session token by replacing
``__MNEME_TOKEN__`` before serving ``GET /``. All data comes from ``/api/*``
fetches carrying the ``X-Mneme-Token`` header; no cookies, no localStorage.

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
  .brand .skill-version{color:var(--muted);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;font-weight:500;white-space:nowrap;}
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
  .page-graph-context{margin-top:18px;padding-top:16px;border-top:1px solid var(--border);}
  .page-graph-groups{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;margin-top:10px;}
  @media (max-width:700px){.page-graph-groups{grid-template-columns:1fr;}}
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
  main.graph-mode{max-width:none;width:100%;padding:0 18px;}
  .graph-card{padding:0;overflow:hidden;}
  .graph-head{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid var(--border);}
  .graph-head h3{margin:0;}
  .graph-head-actions{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
  .graph-status{display:flex;align-items:center;gap:12px;padding:9px 18px;background:var(--warn-bg);color:#854d0e;border-bottom:1px solid #f4d58d;font-size:13px;}
  .graph-status .btn{margin-left:auto;background:transparent;border-color:#d6a84b;color:#854d0e;}
  .graph-status[hidden]{display:none;}
  .graph-toolbar{display:flex;align-items:center;gap:10px;padding:12px 18px;border-bottom:1px solid var(--border);flex-wrap:wrap;background:#fbfcfd;}
  .graph-toolbar input[type=text]{min-width:180px;max-width:260px;}
  .graph-explainer{border-bottom:1px solid var(--border);background:#fbfcfd;}
  .graph-explainer summary{cursor:pointer;padding:8px 18px;color:var(--muted);font-size:12px;font-weight:600;list-style-position:inside;}
  .graph-explainer summary:hover{color:var(--text);}
  .graph-explainer dl{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:18px;padding:4px 18px 14px;}
  .graph-explainer dt{font-size:12px;font-weight:700;margin-bottom:3px;}
  .graph-explainer dd{font-size:12px;color:var(--muted);line-height:1.55;}
  .segment{display:inline-flex;border:1px solid var(--border);border-radius:6px;overflow:hidden;background:#fff;}
  .segment button{border:0;border-right:1px solid var(--border);background:#fff;color:var(--muted);padding:6px 12px;font-size:13px;cursor:pointer;}
  .segment button:last-child{border-right:0;}
  .segment button.active{background:var(--text);color:#fff;}
  .graph-stat-strip{display:flex;gap:18px;align-items:center;padding:8px 18px;border-bottom:1px solid var(--border);font-size:12px;color:var(--muted);min-height:36px;flex-wrap:wrap;}
  .graph-stat-strip strong{color:var(--text);font-weight:650;}
  .graph-workbench{display:grid;grid-template-columns:minmax(0,1fr) 320px;min-height:clamp(520px,calc(100vh - 305px),760px);transition:grid-template-columns .18s ease;}
  .graph-workbench.detail-collapsed{grid-template-columns:minmax(0,1fr) 0;}
  .graph-stage{position:relative;min-width:0;background:#fff;overflow:hidden;}
  #graphCanvas{width:100%;height:100%;min-height:clamp(520px,calc(100vh - 305px),760px);background:#fff;cursor:grab;display:block;touch-action:none;}
  #graphCanvas:active{cursor:grabbing;}
  #graphCanvas:focus-visible{outline:2px solid var(--accent);outline-offset:-3px;}
  .graph-camera-controls{position:absolute;z-index:8;left:14px;top:14px;display:grid;grid-template-columns:repeat(3,32px);gap:5px;padding:5px;background:rgba(255,255,255,.94);border:1px solid var(--border);border-radius:7px;box-shadow:0 5px 18px rgba(15,23,42,.10);}
  .graph-camera-controls button{width:32px;height:32px;border:0;background:transparent;color:var(--text);font-size:18px;line-height:1;cursor:pointer;border-radius:4px;}
  .graph-camera-controls button:hover{background:var(--accent-soft);color:var(--accent);}
  .graph-camera-controls button:focus-visible{outline:2px solid var(--accent);outline-offset:1px;}
  .graph-camera-controls output{grid-column:1/-1;text-align:center;color:var(--muted);font:10px/16px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;border-top:1px solid var(--border);padding-top:3px;}
  .graph-map-hint{position:absolute;left:16px;bottom:14px;z-index:7;background:rgba(255,255,255,.9);border:1px solid var(--border);border-radius:5px;padding:4px 8px;color:var(--muted);font-size:11px;pointer-events:none;}
  .graph-empty{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:32px;background:#fff;}
  .graph-empty[hidden]{display:none;}
  .graph-empty strong{display:block;font-size:16px;margin-bottom:6px;}
  .graph-empty .btn{margin-top:14px;}
  .graph-detail{border-left:1px solid var(--border);padding:16px 18px;overflow:auto;max-height:clamp(520px,calc(100vh - 305px),760px);background:#fbfcfd;min-width:0;}
  .detail-collapsed .graph-detail{visibility:hidden;padding-left:0;padding-right:0;border-left:0;}
  .graph-detail h4{font-size:15px;margin-bottom:4px;overflow-wrap:anywhere;}
  .graph-detail h5{font-size:12px;color:var(--muted);font-weight:650;margin:16px 0 6px;text-transform:uppercase;}
  .graph-detail p{font-size:13px;overflow-wrap:anywhere;}
  .graph-meta{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 10px;}
  .graph-chip{display:inline-flex;align-items:center;border:1px solid var(--border);border-radius:10px;padding:1px 8px;font-size:11px;color:var(--muted);background:#fff;}
  .graph-chip.base{border-color:#aac4e2;color:#285c91;background:#edf5fc;}
  .graph-chip.enriched{border-color:#d9a5aa;color:#8f3d46;background:#fff1f2;}
  .graph-page-list,.graph-relation-list,.graph-node-index{display:grid;gap:6px;}
  .graph-page-link,.graph-relation-link,.graph-node-link{width:100%;border:1px solid var(--border);background:#fff;border-radius:6px;padding:7px 9px;text-align:left;color:var(--text);font-size:12px;cursor:pointer;overflow-wrap:anywhere;}
  .graph-page-link:hover,.graph-relation-link:hover,.graph-node-link:hover{border-color:var(--accent);color:var(--accent);}
  .graph-relation-link span{display:block;color:var(--muted);font-size:11px;margin-top:2px;}
  .graph-evidence{border-left:3px solid #bf6770;padding:7px 9px;background:#fff5f5;color:#6f3037;font-size:12px;margin-top:8px;overflow-wrap:anywhere;}
  .graph-source-rail{border-left:3px solid #97b7d8;padding-left:10px;}
  .graph-source-rail.enriched{border-left-color:#bf6770;}
  .legend{display:flex;gap:16px;flex-wrap:wrap;padding:10px 18px;border-top:1px solid var(--border);font-size:12px;color:var(--muted);}
  .legend .dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;}
  .legend .square{border-radius:2px;}
  .legend .diamond{border-radius:1px;transform:rotate(45deg);}
  #graphCard:fullscreen{width:100vw;height:100vh;border:0;border-radius:0;background:#fff;display:flex;flex-direction:column;}
  #graphCard:fullscreen .graph-workbench{flex:1;min-height:0;}
  #graphCard:fullscreen .graph-stage,#graphCard:fullscreen #graphCanvas{height:100%;min-height:0;}
  #graphCard:fullscreen .graph-detail{max-height:none;}
  #graphCard:fullscreen .graph-workbench{min-height:0;}
  @media (max-width:900px){
    .graph-workbench{grid-template-columns:1fr;}
    .graph-workbench.detail-collapsed{grid-template-columns:1fr;}
    .graph-detail{border-left:0;border-top:1px solid var(--border);max-height:none;}
    .detail-collapsed .graph-detail{display:none;}
    #graphCanvas{height:520px;min-height:520px;}
  }
  @media (max-width:600px){
    header{padding:10px 12px;gap:8px;}
    .brand{flex:1 1 100%;font-size:16px;}
    .bundle-path{flex:1 1 100%;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    nav{flex:1 1 100%;margin-left:0;flex-wrap:nowrap;overflow-x:auto;padding-bottom:2px;}
    nav a{flex:0 0 auto;padding:5px 9px;}
    main{margin:14px auto;padding:0 10px;}
    .graph-toolbar>*{flex:1 1 100%;max-width:none!important;}
    .segment button{flex:1;}
    .graph-explainer dl{grid-template-columns:1fr;gap:10px;}
    .graph-head{align-items:center;flex-wrap:wrap;}
    .graph-head h3{flex:1;white-space:nowrap;}
    .graph-head-actions{width:100%;margin-left:0;}
    .graph-stat-strip{gap:10px;}
    main.graph-mode{padding:0 10px;}
    #graphCanvas{height:420px;min-height:420px;}
    .graph-camera-controls{left:9px;top:9px;}
    .graph-map-hint{display:none;}
  }
</style>
</head>
<body>

<header>
  <div class="brand">Mneme<span> Web UI</span> <span class="skill-version" id="skillVersion" aria-label="Skill 版本">v…</span> <span class="hint" style="font-weight:400">（只读 + 缓存重建）</span></div>
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
        <div class="page-graph-context" id="pageGraphContext"></div>
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
        <p class="hint" style="margin-bottom:12px;">按当前模式重建 L2（如已启用）、FTS5 与 Graph。本按钮只重建缓存，不改 Markdown；L2 失败会明确报错并停止。</p>
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
    <div class="card graph-card" id="graphCard">
      <div class="graph-head">
        <h3>知识图谱</h3>
        <span class="hint" id="graphFreshness"></span>
        <div class="graph-head-actions">
          <button class="btn small" id="graphBackBtn" onclick="graphBack()" disabled title="返回上一个图谱视图">← 返回</button>
          <button class="btn small" id="graphDetailToggle" onclick="toggleGraphDetail()" aria-pressed="true" title="显示或收起图谱详情">收起详情</button>
          <button class="btn small" id="graphFullscreenBtn" onclick="toggleGraphFullscreen()" aria-pressed="false">⛶ 全屏</button>
          <button class="btn small" onclick="resetGraphLayout()">重新布局</button>
        </div>
      </div>
      <div class="graph-status" id="graphStatus" hidden></div>
      <div class="graph-toolbar">
        <div class="segment" id="graphLayerSegment" role="group" aria-label="图谱层">
          <button class="active" data-layer="all" onclick="setGraphLayer('all')">合并</button>
          <button data-layer="base" onclick="setGraphLayer('base')">基础</button>
          <button data-layer="enriched" onclick="setGraphLayer('enriched')">富化</button>
        </div>
        <select id="graphKindFilter" onchange="applyGraphSlice()" aria-label="节点切片">
          <option value="">节点：全部</option>
          <option value="page">节点：页面</option>
          <option value="tag">节点：标签</option>
          <option value="entity">节点：agent 提取实体</option>
        </select>
        <select id="graphViewFilter" onchange="setGraphView(this.value)" aria-label="图谱视图">
          <option value="overview" selected>视图：全图</option>
          <option value="neighborhood">视图：当前邻域</option>
        </select>
        <select id="graphPredicateFilter" onchange="applyGraphSlice()" aria-label="关系切片">
          <option value="">关系：全部</option>
        </select>
        <input type="text" id="graphSearch" placeholder="聚焦节点…" aria-label="聚焦节点" oninput="scheduleGraphSlice()">
      </div>
      <details class="graph-explainer">
        <summary>合并、基础、富化分别是什么？</summary>
        <dl>
          <div><dt>合并</dt><dd>同时显示基础层与富化层，用于查看页面结构和语义关系如何连接。</dd></div>
          <div><dt>基础</dt><dd>从 Markdown 页面、frontmatter tags 和页面链接确定性派生；重建 Graph 即可完整恢复。</dd></div>
          <div><dt>富化</dt><dd>来自用户批准的 agent 实体与关系提取，带置信度、证据和来源页；Markdown 仍是事实依据。</dd></div>
          <div><dt>agent 提取实体</dt><dd>agent 从正文中识别出的概念、技术、组织或人物。只有在 dream 预览中获批并 ingest 后才会出现，不会自动生成。</dd></div>
        </dl>
      </details>
      <div class="graph-stat-strip" id="graphStats"></div>
      <div class="graph-workbench">
        <div class="graph-stage">
          <div id="graphCanvas" tabindex="0" role="application" aria-label="知识图谱地图，可拖动平移并滚轮缩放"></div>
          <div class="graph-camera-controls" role="group" aria-label="图谱镜头控制">
            <button onclick="zoomGraph(1.25)" title="放大" aria-label="放大图谱">+</button>
            <button onclick="zoomGraph(0.8)" title="缩小" aria-label="缩小图谱">−</button>
            <button onclick="fitGraphView()" title="适配全图" aria-label="适配全图">⌂</button>
            <output id="graphZoomLabel" aria-label="当前缩放比例">100%</output>
          </div>
          <div class="graph-map-hint">拖动画布移动镜头 · 滚轮缩放 · 小地图定位全局</div>
          <div class="graph-empty" id="graphEmpty" hidden></div>
        </div>
        <aside class="graph-detail" id="graphDetail" aria-live="polite"></aside>
      </div>
      <div class="legend" id="graphLegend">
        <span><span class="dot square" style="background:#2f6ba8"></span>页面</span>
        <span><span class="dot diamond" style="background:#4f8467"></span>标签</span>
        <span><span class="dot" style="background:#b6535c"></span>agent 提取实体</span>
        <span><span style="display:inline-block;width:18px;border-top:2px solid #aeb7c2;margin:0 5px 3px 0"></span>基础关系</span>
        <span><span style="display:inline-block;width:18px;border-top:2px solid #b6535c;margin:0 5px 3px 0"></span>富化关系</span>
      </div>
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

<script src="/assets/g6-5.1.1.min.js"></script>
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
let graphPendingSelection = null;

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
  document.querySelector('main').classList.toggle('graph-mode',tab==='graph');
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
  document.getElementById('skillVersion').textContent = 'v' + s.version;
  document.title = 'Mneme Web UI · v' + s.version;
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
  const graphCounts = idx.graph.exists && !idx.graph.error
    ? '<span class="hint" style="display:block">基础 '+((idx.graph.entity_count||0)-(idx.graph.llm_entity_count||0))+' · 富化 '+(idx.graph.llm_entity_count||0)+' 实体</span>'
    : '';
  document.getElementById('indexRows').innerHTML =
    row('FTS5 全文索引', idx.fts5.exists ? '<span class="badge OK">✓ 就绪</span>' : '<span class="badge INFO">✗ 未构建</span>') +
    row('Graph 关系图'+graphCounts, !idx.graph.exists ? '<span class="badge INFO">✗ 未构建</span>'
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
  const originalLabel=btn.textContent;
  btn.disabled=true; btn.textContent='重建中…';
  try{
    const r = await api('/api/reindex', {method:'POST'});
    const parts = [];
    if(r.l2) parts.push('L2 '+r.l2.concepts+' 页 / '+r.l2.chunks+' 分块');
    parts.push('FTS5 '+r.fts_pages+' 页');
    parts.push('Graph '+r.graph.entities+' 实体 / '+r.graph.relations+' 关系');
    toast('✓ 索引重建完成：'+parts.join(' · '));
    await refreshStatus();
    if(GRAPH || document.getElementById('tab-graph').classList.contains('active')){
      GRAPH=null;
      await loadGraph();
    }
  }catch(e){ toast('重建失败：'+e.message, true); }
  btn.disabled=false; btn.textContent=originalLabel;
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
    meta.textContent = 'mode='+r.mode+' · 召回 '+results.length+' 个页面';
    document.getElementById('searchResults').innerHTML = results.map(c=>{
      const p = PAGEMAP[c.path];
      const typeBadge = p && p.type ? ' <span class="badge INFO" style="margin-left:6px">'+esc(p.type)+'</span>' : '';
      return '<div class="result-card" onclick="go(\'browse\',\''+encodeURIComponent(c.path)+'\')">'+
        '<div class="r-title">'+highlight(c.title || c.path, q)+typeBadge+'</div>'+
        '<div class="r-path mono">'+esc(c.path)+
          (Number.isFinite(c.distance) ? ' · distance '+c.distance.toFixed(4) : '')+'</div>'+
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
    renderPageGraphContext(data.graph);
  }catch(e){
    toast('打开页面失败：'+e.message, true);
  }
}

function renderPageGraphContext(context){
  const root=document.getElementById('pageGraphContext');
  if(!context||!context.available){
    root.innerHTML='<h3 style="font-size:13px;color:var(--muted)">Graph 上下文</h3><p class="hint">Graph 未构建。</p><button class="btn small" style="margin-top:8px" onclick="doReindex(this)">构建 Graph</button>';
    return;
  }
  const entities=context.entities.slice().sort((a,b)=>(a.layer===b.layer?0:a.layer==='enriched'?-1:1)||a.label.localeCompare(b.label));
  const relations=context.relations.slice().sort((a,b)=>(a.layers.includes('enriched')===b.layers.includes('enriched')?0:a.layers.includes('enriched')?-1:1)||a.predicate.localeCompare(b.predicate));
  const entityHtml=entities.length?entities.map(node=>'<button class="graph-node-link" data-node="'+escAttr(node.id)+'" onclick="openGraphSelection(\'node\',this.dataset.node)">'+esc(node.label)+'<span class="graph-chip '+node.layer+'" style="float:right">'+(node.layer==='enriched'?'富化':sourceLabel(node.source))+'</span></button>').join(''):'<p class="hint">无关联实体</p>';
  const relationHtml=relations.length?relations.map(edge=>'<button class="graph-relation-link" data-edge="'+escAttr(edge.id)+'" onclick="openGraphSelection(\'edge\',this.dataset.edge)">'+esc(edge.subject_label)+' → '+esc(predicateLabel(edge.predicate))+' → '+esc(edge.object_label)+'<span>'+(edge.layers.includes('enriched')?'富化':'基础')+(edge.confidence!==null&&edge.confidence!==undefined?' · '+confidenceLabel(edge.confidence):'')+'</span></button>').join(''):'<p class="hint">无关联关系</p>';
  root.innerHTML='<h3 style="font-size:13px;color:var(--muted)">Graph 上下文 '+(!context.fresh?'<span class="badge WARN">已过期</span>':'')+'</h3><div class="page-graph-groups"><div><h5 style="font-size:12px;margin-bottom:6px">实体与相邻页面</h5><div class="graph-node-index">'+entityHtml+'</div></div><div><h5 style="font-size:12px;margin-bottom:6px">页面来源关系</h5><div class="graph-relation-list">'+relationHtml+'</div></div></div>';
}

function openGraphSelection(kind,id){
  graphPendingSelection={kind,id};
  if(document.getElementById('tab-graph').classList.contains('active')&&GRAPH){
    if(kind==='node') selectGraphNode(id); else selectGraphEdge(id);
    graphPendingSelection=null;
  }else{
    go('graph');
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
    '1. 不要修改 raw-sources/ 下的原始材料；sources/*.md 是 OKF 溯源页；\n'+
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
    '请对 bundle '+bundle+' 执行一次 dream 审计与写入预览：\n\n'+
    '1. 运行 `mneme dream --bundle '+bundle+' --json` 生成只读审计报告；\n'+
    '2. 向我展示 OKF Hard Rules、Mneme Writer Rules 和 Graph 健康状态；\n'+
    '3. 阅读相关页面，同时准备 Markdown 变更预览和 agent Graph 富化 extraction JSON：实体需包含 name / type / description / confidence，关系需包含 subject / predicate / object / evidence / confidence；\n'+
    '4. 如果当前富化实体与关系均为 0，先选最多 5 个有代表性的现有页面做回填试点，不要直接全量处理；\n'+
    '5. 在任何 bundle 或 .mneme 写入前，展示完整合并预览并等我明确批准；\n'+
    '6. 批准后仅落盘已预览的范围；如有 wiki 页面写入，同步更新 index.md 与 log.md；然后重建 Graph + FTS5，再用 `mneme graph ingest` 写入已批准的 extraction JSON；\n'+
    '7. 最后重跑审计，报告新增或复用的富化实体数、富化关系数及所有警告。';
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
  const valid = meta.valid_candidate_count == null ? meta.candidate_count : meta.valid_candidate_count;
  document.getElementById('dreamMeta').innerHTML =
    '<div class="log-item">OKF 概念页：'+(valid||0)+' / '+(meta.candidate_count||0)+' 个有效</div>'+
    (hard.length ? '<div class="log-item">局部错误不影响其他有效页面被读取，但 bundle 尚不合规。</div>' : '')+
    '<div class="log-item">模式：只读审计（'+(meta.writes ? esc(meta.writes) : 'no writes')+'）</div>';
}

/* ==================== 图谱工作台（G6 camera + minimap） ==================== */
const GRAPH_COLOR={page:'#2f6ba8',tag:'#4f8467',entity:'#b6535c',baseEdge:'#aeb7c2',enrichedEdge:'#b6535c'};
const GRAPH_LAYOUT={type:'force-atlas2',preventOverlap:true,nodeSize:24,kr:18,kg:1,mode:'normal'};
let graphRenderer=null;
let graphState=null;
let graphLayer='all';
let graphView='overview';
let graphSelection=null;
let graphFocusId=null;
let graphHistory=[];
let graphSliceTimer=null;
let graphResizeTimer=null;

function shortGraphLabel(node){
  const label=String(node.label||node.name||'');
  if(node.kind!=='page') return label;
  const title=String(node.properties&&node.properties.title||'').trim();
  if(title&&!title.includes('/')&&!title.includes('\\')) return title;
  const path=String(node.page_path||node.name||label).replaceAll('\\','/');
  const filename=(path.split('/').pop()||path).replace(/\.md$/i,'');
  return filename.replace(/^\d+(?:\.\d+)?[_-]*/,'').replaceAll('_',' ')||label;
}

function graphDegrees(){
  const degree={};
  (GRAPH&&GRAPH.edges||[]).forEach(edge=>{
    degree[edge.source_id]=(degree[edge.source_id]||0)+1;
    degree[edge.target_id]=(degree[edge.target_id]||0)+1;
  });
  return degree;
}

function graphLabelNodes(degree){
  const budget=Math.min(64,Math.max(18,Math.round(Math.sqrt((GRAPH&&GRAPH.nodes.length)||0)*1.8)));
  return new Set(Object.entries(degree).sort((left,right)=>right[1]-left[1]).slice(0,budget).map(([id])=>id));
}

function graphNodeDatum(raw,degree,labelNodes){
  const size=16+Math.min(12,Math.sqrt(degree[raw.id]||0)*2.2);
  return {
    id:raw.id,
    type:raw.kind==='page'?'rect':raw.kind==='tag'?'diamond':'circle',
    data:{raw},
    style:{
      size:raw.kind==='page'?[size,size]:size,
      fill:GRAPH_COLOR[raw.kind]||GRAPH_COLOR.entity,
      stroke:'#ffffff',lineWidth:2,
      labelText:labelNodes.has(raw.id)?shortGraphLabel(raw):'',labelPlacement:'bottom',labelOffsetY:4,
      labelFill:'#1f2937',labelFontSize:12,labelMaxWidth:170,labelWordWrap:false,
      cursor:'pointer'
    }
  };
}

function graphEdgeDatum(raw){
  const enriched=raw.layers.includes('enriched');
  const dense=(GRAPH&&GRAPH.edges.length)>1200;
  return {
    id:raw.id,source:raw.source_id,target:raw.target_id,type:'line',data:{raw},
    style:{
      stroke:enriched?GRAPH_COLOR.enrichedEdge:GRAPH_COLOR.baseEdge,
      strokeOpacity:dense?(enriched?.13:.065):(enriched?.62:.36),
      lineWidth:dense?(enriched?1:.7):(enriched?1.6:1),
      cursor:'pointer'
    }
  };
}

function graphMinimapSize(){
  if(window.innerWidth<=600) return [150,96];
  if(window.innerWidth<=900) return [180,116];
  return [220,142];
}

function graphOptions(){
  const degree=graphDegrees();
  const labelNodes=graphLabelNodes(degree);
  const reduced=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  return {
    container:'graphCanvas',
    data:{
      nodes:GRAPH.nodes.map(node=>graphNodeDatum(node,degree,labelNodes)),
      edges:GRAPH.edges.map(graphEdgeDatum)
    },
    layout:GRAPH_LAYOUT,
    animation:!reduced&&GRAPH.nodes.length<=300,
    zoomRange:[.08,5],
    node:{
      state:{
        selected:{halo:true,haloLineWidth:16,haloStroke:'#172033',haloStrokeOpacity:.16,stroke:'#172033',lineWidth:3,labelText:d=>shortGraphLabel(d.data.raw),labelFontWeight:650,labelOpacity:1},
        highlight:{fillOpacity:1,strokeOpacity:1,labelText:d=>shortGraphLabel(d.data.raw),labelOpacity:1,labelFontWeight:600},
        inactive:{fillOpacity:.12,strokeOpacity:.12,labelOpacity:.08}
      }
    },
    edge:{
      state:{
        selected:{lineWidth:3,stroke:'#7f1d2d',strokeOpacity:1,labelText:d=>predicateLabel(d.data.raw.predicate),labelFill:'#6f3037',labelFontSize:11,labelBackground:true,labelBackgroundFill:'#fff'},
        highlight:{strokeOpacity:.9,lineWidth:2},
        inactive:{strokeOpacity:.05,labelOpacity:0}
      }
    },
    behaviors:[
      'drag-canvas','zoom-canvas','drag-element',
      {type:'auto-adapt-label',key:'adaptive-labels',throttle:100,padding:6,sortNode:{type:'degree'}},
      {type:'optimize-viewport-transform',key:'optimize-camera'}
    ],
    plugins:[{
      type:'minimap',key:'minimap',size:graphMinimapSize(),padding:10,position:'right-bottom',delay:80,
      containerStyle:{border:'1px solid #d8dde5',background:'rgba(255,255,255,.96)',borderRadius:'6px',boxShadow:'0 6px 20px rgba(15,23,42,.12)'},
      maskStyle:{border:'1px solid #2563eb',background:'rgba(37,99,235,.10)'}
    }]
  };
}

async function loadGraph(){
  if(GRAPH&&graphRenderer){
    resizeGraphRenderer();
    return;
  }
  try{
    GRAPH=await api('/api/graph');
  }catch(e){
    toast('加载图谱失败：'+e.message,true);
    return;
  }
  if(graphRenderer){ graphRenderer.destroy(); graphRenderer=null; }
  graphState=null;
  graphSelection=null;
  graphFocusId=null;
  graphHistory=[];
  updateGraphHistoryControls();
  const predicate=document.getElementById('graphPredicateFilter');
  const selected=predicate.value;
  const predicates=[...new Set(GRAPH.edges.map(edge=>edge.predicate))].sort();
  predicate.innerHTML='<option value="">关系：全部</option>'+predicates.map(p=>'<option value="'+escAttr(p)+'">关系：'+esc(predicateLabel(p))+'</option>').join('');
  if(predicates.includes(selected)) predicate.value=selected;
  renderGraphStatus();
  if(!GRAPH.available){
    await applyGraphSlice();
    return;
  }
  if(!window.G6||!G6.Graph){
    document.getElementById('graphEmpty').hidden=false;
    document.getElementById('graphEmpty').innerHTML='<div><strong>图谱渲染器未加载</strong><p class="hint">检查本地 G6 静态资源是否完整。</p></div>';
    return;
  }
  try{
    graphRenderer=new G6.Graph(graphOptions());
    bindGraphEvents();
    await graphRenderer.render();
    await spreadGraphWorld();
    await setInitialGraphCamera();
    await applyGraphSlice({fit:false,animate:false});
  }catch(error){
    if(graphRenderer){ graphRenderer.destroy(); graphRenderer=null; }
    document.getElementById('graphEmpty').hidden=false;
    document.getElementById('graphEmpty').innerHTML='<div><strong>图谱渲染失败</strong><p class="hint">'+esc(error.message||error)+'</p></div>';
    toast('图谱渲染失败：'+(error.message||error),true);
    return;
  }
  if(graphPendingSelection){
    const pending=graphPendingSelection;
    graphPendingSelection=null;
    if(pending.kind==='node') selectGraphNode(pending.id); else selectGraphEdge(pending.id);
  }
}

function bindGraphEvents(){
  graphRenderer.on('node:click',event=>selectGraphNode(event.target.id));
  graphRenderer.on('node:dblclick',event=>focusGraphNode(event.target.id));
  graphRenderer.on('edge:click',event=>selectGraphEdge(event.target.id));
  graphRenderer.on('canvas:click',()=>clearGraphSelection());
  graphRenderer.on('aftertransform',updateGraphZoomLabel);
}

function graphWorldScale(){
  const count=(GRAPH&&GRAPH.nodes.length)||0;
  return count<=140?1:Math.min(4.2,Math.max(1.45,Math.sqrt(count/90)));
}

async function spreadGraphWorld(){
  if(!graphRenderer) return;
  const scale=graphWorldScale();
  if(scale===1) return;
  const nodes=graphRenderer.getNodeData();
  const positioned=nodes.filter(node=>Number.isFinite(Number(node.style&&node.style.x))&&Number.isFinite(Number(node.style&&node.style.y)));
  if(!positioned.length) return;
  const bounds=positioned.reduce((acc,node)=>{
    const x=Number(node.style.x),y=Number(node.style.y);
    acc.minX=Math.min(acc.minX,x);acc.maxX=Math.max(acc.maxX,x);
    acc.minY=Math.min(acc.minY,y);acc.maxY=Math.max(acc.maxY,y);
    return acc;
  },{minX:Infinity,maxX:-Infinity,minY:Infinity,maxY:-Infinity});
  const centerX=(bounds.minX+bounds.maxX)/2,centerY=(bounds.minY+bounds.maxY)/2;
  graphRenderer.updateNodeData(positioned.map(node=>({
    id:node.id,
    style:{x:centerX+(Number(node.style.x)-centerX)*scale,y:centerY+(Number(node.style.y)-centerY)*scale}
  })));
  await graphRenderer.draw();
}

function updateGraphZoomLabel(){
  const output=document.getElementById('graphZoomLabel');
  if(!output||!graphRenderer) return;
  try{
    const zoom=graphRenderer.getZoom();
    if(Number.isFinite(zoom)) output.textContent=Math.round(zoom*100)+'%';
  }catch(error){
    // G6 may emit an initial transform before its viewport is ready.
  }
}

async function setInitialGraphCamera(){
  if(!graphRenderer) return;
  if(((GRAPH&&GRAPH.nodes.length)||0)<=140){
    await graphRenderer.fitView({when:'always',direction:'both'},false);
  }else{
    await graphRenderer.zoomTo(1,false);
    await graphRenderer.fitCenter(false);
  }
  updateGraphZoomLabel();
}

function renderGraphStatus(){
  const freshness=document.getElementById('graphFreshness');
  const status=document.getElementById('graphStatus');
  status.hidden=true;
  status.innerHTML='';
  if(!GRAPH || !GRAPH.available){
    freshness.textContent='未构建';
    return;
  }
  freshness.textContent=GRAPH.fresh?'新鲜':'已过期';
  if(!GRAPH.fresh){
    status.hidden=false;
    status.innerHTML='<span>Graph 已过期，当前数据未覆盖 Markdown 的最新变化。</span><button class="btn small" onclick="doReindex(this)">立即重建</button>';
  }
}

function setGraphLayer(layer){
  graphLayer=layer;
  document.querySelectorAll('#graphLayerSegment button').forEach(button=>{
    const active=button.dataset.layer===layer;
    button.classList.toggle('active',active);
    button.setAttribute('aria-pressed',active?'true':'false');
  });
  applyGraphSlice({fit:true});
}

function setGraphView(view){
  if(view==='neighborhood'&&!(graphSelection&&graphSelection.kind==='node')){
    document.getElementById('graphViewFilter').value='overview';
    toast('先选择一个节点，再查看当前邻域');
    return;
  }
  graphView=view||'overview';
  graphFocusId=graphView==='neighborhood'?graphSelection.id:null;
  applyGraphStates();
  if(graphView==='neighborhood') graphRenderer.focusElement(graphFocusId,{duration:320,easing:'ease-out'});
  else fitGraphView();
}

function scheduleGraphSlice(){
  clearTimeout(graphSliceTimer);
  graphSliceTimer=setTimeout(()=>applyGraphSlice({fit:true}),120);
}

function graphVisibleSlice(){
  if(!GRAPH || !GRAPH.available) return {nodes:[],edges:[]};
  const kind=document.getElementById('graphKindFilter').value;
  const predicate=document.getElementById('graphPredicateFilter').value;
  const query=document.getElementById('graphSearch').value.trim().toLocaleLowerCase();
  const nodeMap=Object.fromEntries(GRAPH.nodes.map(node=>[node.id,node]));
  let edges=GRAPH.edges.filter(edge=>(graphLayer==='all'||edge.layers.includes(graphLayer))&&(!predicate||edge.predicate===predicate));
  const incident=new Set();
  edges.forEach(edge=>{ incident.add(edge.source_id); incident.add(edge.target_id); });
  let nodes=GRAPH.nodes.filter(node=>incident.has(node.id)||(graphLayer==='all'&&!predicate)||(graphLayer!=='all'&&node.layer===graphLayer));

  if(kind||query){
    const focus=new Set(nodes.filter(node=>{
      const kindMatch=!kind||node.kind===kind;
      const haystack=(node.label+' '+node.name+' '+node.description+' '+(node.page_path||'')).toLocaleLowerCase();
      return kindMatch&&(!query||haystack.includes(query));
    }).map(node=>node.id));
    if(!focus.size) return {nodes:[],edges:[]};
    edges=edges.filter(edge=>focus.has(edge.source_id)||focus.has(edge.target_id));
    const visible=new Set(focus);
    edges.forEach(edge=>{ visible.add(edge.source_id); visible.add(edge.target_id); });
    nodes=GRAPH.nodes.filter(node=>visible.has(node.id));
  }else if(predicate){
    nodes=GRAPH.nodes.filter(node=>incident.has(node.id));
  }
  const visibleNodes=new Set(nodes.map(node=>node.id));
  edges=edges.filter(edge=>nodeMap[edge.source_id]&&nodeMap[edge.target_id]&&visibleNodes.has(edge.source_id)&&visibleNodes.has(edge.target_id));
  return {nodes,edges};
}

function graphNeighborhood(focusId){
  const nodeIds=new Set([focusId]),edgeIds=new Set();
  const visibleEdges=new Set((graphState&&graphState.edges||[]).map(edge=>edge.id));
  GRAPH.edges.forEach(edge=>{
    if(!visibleEdges.has(edge.id)) return;
    if(edge.source_id===focusId||edge.target_id===focusId){
      edgeIds.add(edge.id);nodeIds.add(edge.source_id);nodeIds.add(edge.target_id);
    }
  });
  return {nodeIds,edgeIds};
}

async function applyGraphSlice(options){
  const opts=options||{};
  const empty=document.getElementById('graphEmpty');
  if(!GRAPH||!GRAPH.available){
    graphState=null;
    const error=GRAPH&&GRAPH.stats&&GRAPH.stats.error;
    const count=GRAPH&&GRAPH.stats?GRAPH.stats.markdown_pages||0:0;
    empty.hidden=false;
    empty.innerHTML='<div><strong>'+(error?'Graph 无法读取':'Graph 尚未构建')+'</strong><p class="hint">'+(error?esc(error):(count+' 个 Markdown 概念页可建立基础层。'))+'</p><button class="btn primary" onclick="doReindex(this)">构建 Graph</button></div>';
    document.getElementById('graphStats').innerHTML='<span><strong>0</strong> 节点</span><span><strong>0</strong> 关系</span>';
    renderGraphDetail();
    return;
  }
  const slice=graphVisibleSlice();
  graphState=slice;
  const nodeIds=new Set(slice.nodes.map(node=>node.id));
  const edgeIds=new Set(slice.edges.map(edge=>edge.id));
  if(graphSelection&&graphSelection.kind==='node'&&!nodeIds.has(graphSelection.id)) graphSelection=null;
  if(graphSelection&&graphSelection.kind==='edge'&&!edgeIds.has(graphSelection.id)) graphSelection=null;
  if(graphFocusId&&!nodeIds.has(graphFocusId)){graphFocusId=null;graphView='overview';document.getElementById('graphViewFilter').value='overview';}
  const visibility={};
  GRAPH.nodes.forEach(node=>{visibility[node.id]=nodeIds.has(node.id)?'visible':'hidden';});
  GRAPH.edges.forEach(edge=>{visibility[edge.id]=edgeIds.has(edge.id)?'visible':'hidden';});
  if(graphRenderer) await graphRenderer.setElementVisibility(visibility,false);
  const stats=GRAPH.stats;
  document.getElementById('graphStats').innerHTML=
    '<span><strong>'+slice.nodes.length+'</strong> / '+stats.nodes+' 节点</span>'+
    '<span><strong>'+slice.edges.length+'</strong> / '+stats.edges+' 关系</span>'+
    '<span>基础 '+stats.base_nodes+' 节点 · '+stats.base_edges+' 关系</span>'+
    '<span>富化 '+stats.enriched_nodes+' 节点 · '+stats.enriched_edges+' 关系</span>';
  if(!slice.nodes.length){
    empty.hidden=false;
    const enrichedEmpty=graphLayer==='enriched'&&stats.enriched_nodes===0&&stats.enriched_edges===0;
    empty.innerHTML='<div><strong>'+(enrichedEmpty?'尚无 agent 提取实体':'当前筛选没有节点')+'</strong><p class="hint">'+(enrichedEmpty?'当前只有由 Markdown 派生的基础层。agent 提取实体与关系需经过 dream 预览批准后 ingest。':'调整节点、关系或关键词筛选。')+'</p></div>';
  }else{
    empty.hidden=true;
    await applyGraphStates();
    if(opts.fit&&graphRenderer){
      const fullSlice=slice.nodes.length===GRAPH.nodes.length&&slice.edges.length===GRAPH.edges.length;
      if(fullSlice) await setInitialGraphCamera();
      else await graphRenderer.fitView({when:'always',direction:'both'},opts.animate===false?false:{duration:260,easing:'ease-out'});
      updateGraphZoomLabel();
    }
  }
  renderGraphDetail();
}

async function applyGraphStates(){
  if(!graphRenderer||!GRAPH) return;
  const states={};
  GRAPH.nodes.forEach(node=>{states[node.id]=[];});
  GRAPH.edges.forEach(edge=>{states[edge.id]=[];});
  if(graphView==='neighborhood'&&graphFocusId){
    const neighborhood=graphNeighborhood(graphFocusId);
    (graphState&&graphState.nodes||[]).forEach(node=>{states[node.id]=neighborhood.nodeIds.has(node.id)?['highlight']:['inactive'];});
    (graphState&&graphState.edges||[]).forEach(edge=>{states[edge.id]=neighborhood.edgeIds.has(edge.id)?['highlight']:['inactive'];});
  }
  if(graphSelection){
    const current=states[graphSelection.id]||[];
    states[graphSelection.id]=[...new Set([...current,'selected'])];
    if(graphSelection.kind==='edge'){
      const edge=GRAPH.edges.find(item=>item.id===graphSelection.id);
      if(edge){
        states[edge.source_id]=[...new Set([...(states[edge.source_id]||[]),'highlight'])];
        states[edge.target_id]=[...new Set([...(states[edge.target_id]||[]),'highlight'])];
      }
    }
  }
  await graphRenderer.setElementState(states,false);
}

async function resetGraphLayout(){
  if(!graphRenderer) return;
  graphSelection=null;graphFocusId=null;graphView='overview';
  document.getElementById('graphViewFilter').value='overview';
  await applyGraphStates();
  try{
    await graphRenderer.layout(GRAPH_LAYOUT);
    await spreadGraphWorld();
    await setInitialGraphCamera();
  }catch(error){ toast('重新布局失败：'+(error.message||error),true); }
}

function graphViewSnapshot(){
  return {view:graphView,focusId:graphFocusId,selection:graphSelection?{kind:graphSelection.kind,id:graphSelection.id}:null};
}

function updateGraphHistoryControls(){
  const button=document.getElementById('graphBackBtn');
  if(button) button.disabled=!graphHistory.length;
}

async function focusGraphNode(id){
  if(!graphRenderer) return;
  if(graphView!=='neighborhood'||graphFocusId!==id) graphHistory.push(graphViewSnapshot());
  graphSelection={kind:'node',id};graphFocusId=id;graphView='neighborhood';
  document.getElementById('graphViewFilter').value='neighborhood';
  await applyGraphStates();
  await graphRenderer.focusElement(id,{duration:320,easing:'ease-out'});
  renderGraphDetail();updateGraphHistoryControls();
}

async function graphBack(){
  if(!graphHistory.length) return;
  const previous=graphHistory.pop();
  graphView=previous.view;graphFocusId=previous.focusId;graphSelection=previous.selection;
  document.getElementById('graphViewFilter').value=graphView;
  await applyGraphStates();
  if(graphFocusId) await graphRenderer.focusElement(graphFocusId,{duration:280,easing:'ease-out'}); else await fitGraphView();
  renderGraphDetail();updateGraphHistoryControls();
}

async function selectGraphNode(id){
  graphSelection={kind:'node',id};
  await applyGraphStates();
  renderGraphDetail();
}

async function selectGraphEdge(id){
  graphSelection={kind:'edge',id};
  await applyGraphStates();
  renderGraphDetail();
}

async function clearGraphSelection(){
  graphSelection=null;
  if(graphView==='neighborhood'){
    graphView='overview';graphFocusId=null;document.getElementById('graphViewFilter').value='overview';
  }
  await applyGraphStates();
  renderGraphDetail();
}

async function zoomGraph(ratio){
  if(!graphRenderer) return;
  await graphRenderer.zoomBy(ratio,{duration:180,easing:'ease-out'});
  updateGraphZoomLabel();
}

async function fitGraphView(){
  if(!graphRenderer||!graphState||!graphState.nodes.length) return Promise.resolve();
  await graphRenderer.fitView({when:'always',direction:'both'},{duration:260,easing:'ease-out'});
  updateGraphZoomLabel();
}

function toggleGraphDetail(){
  const workbench=document.querySelector('.graph-workbench');
  const button=document.getElementById('graphDetailToggle');
  const collapsed=workbench.classList.toggle('detail-collapsed');
  button.textContent=collapsed?'显示详情':'收起详情';
  button.setAttribute('aria-pressed',collapsed?'false':'true');
  clearTimeout(graphResizeTimer);graphResizeTimer=setTimeout(resizeGraphRenderer,210);
}

function resizeGraphRenderer(){
  if(graphRenderer&&document.getElementById('tab-graph').classList.contains('active')){
    graphRenderer.resize();
    updateGraphZoomLabel();
  }
}

function predicateLabel(value){ return String(value||'relates_to').replaceAll('_',' '); }
function confidenceLabel(value){ return value===null||value===undefined?'':Math.round(Number(value)*100)+'%'; }
function sourceLabel(value){ return value==='llm_extracted'?'agent 提取':value==='link'?'Markdown 链接':value==='tag'?'frontmatter tag':value==='page'?'Markdown 页面':(value||'派生'); }
function graphPageButtons(pages){
  const unique=[...new Set((pages||[]).filter(Boolean))];
  return unique.length?'<div class="graph-page-list">'+unique.map(page=>'<button class="graph-page-link" data-page="'+escAttr(page)+'" onclick="openGraphPage(this.dataset.page)">'+esc(page)+'</button>').join('')+'</div>':'<p class="hint">无可追溯页面</p>';
}
function openGraphPage(page){ go('browse',page); }

function renderGraphDetail(){
  const detail=document.getElementById('graphDetail');
  if(!GRAPH||!GRAPH.available){
    detail.innerHTML='<h4>Graph</h4><p class="hint">构建后显示页面、标签以及已批准的 agent 提取实体与关系。</p>';
    return;
  }
  const nodeMap=Object.fromEntries(GRAPH.nodes.map(node=>[node.id,node]));
  if(!graphSelection){
    const nodes=(graphState?graphState.nodes:[]).slice().sort((a,b)=>a.label.localeCompare(b.label)).slice(0,20);
    detail.innerHTML='<h4>当前地图</h4><p class="hint">'+(graphState?graphState.nodes.length:0)+' 个节点 · '+(graphState?graphState.edges.length:0)+' 条关系</p><h5>节点目录</h5><div class="graph-node-index">'+(nodes.length?nodes.map(node=>'<button class="graph-node-link" data-node="'+escAttr(node.id)+'" onclick="selectGraphNode(this.dataset.node)">'+esc(shortGraphLabel(node))+'<span class="graph-chip '+node.layer+'" style="float:right">'+(node.layer==='enriched'?'富化':sourceLabel(node.source))+'</span></button>').join(''):'<p class="hint">当前无节点</p>')+'</div>';
    return;
  }
  if(graphSelection.kind==='node'){
    const node=nodeMap[graphSelection.id];
    if(!node){ graphSelection=null;renderGraphDetail();return; }
    const relations=GRAPH.edges.filter(edge=>edge.source_id===node.id||edge.target_id===node.id).sort((a,b)=>a.predicate.localeCompare(b.predicate));
    const docType=node.kind==='page'&&node.properties?node.properties.type:'';
    const relationHtml=relations.length?relations.map(edge=>{
      const outgoing=edge.source_id===node.id;
      const neighbor=nodeMap[outgoing?edge.target_id:edge.source_id];
      const layer=edge.layers.includes('enriched')?'富化':'基础';
      return '<button class="graph-relation-link" data-edge="'+escAttr(edge.id)+'" onclick="selectGraphEdge(this.dataset.edge)">'+esc(outgoing?'→ '+predicateLabel(edge.predicate):'← '+predicateLabel(edge.predicate))+' · '+esc(neighbor?shortGraphLabel(neighbor):'未知节点')+'<span>'+layer+(edge.confidence!==null&&edge.confidence!==undefined?' · '+confidenceLabel(edge.confidence):'')+'</span></button>';
    }).join(''):'<p class="hint">无直接关系</p>';
    detail.innerHTML='<div class="graph-source-rail '+node.layer+'"><h4>'+esc(shortGraphLabel(node))+'</h4><p class="hint mono">'+esc(node.page_path||node.name)+'</p></div><div class="graph-meta"><span class="graph-chip '+node.layer+'">'+(node.layer==='enriched'?'富化层':'基础层')+'</span><span class="graph-chip">'+esc(node.kind==='page'?(docType||'page'):node.entity_type)+'</span>'+(node.confidence!==null&&node.confidence!==undefined?'<span class="graph-chip">置信度 '+confidenceLabel(node.confidence)+'</span>':'')+'</div>'+(node.description?'<p>'+esc(node.description)+'</p>':'')+'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"><button class="btn small" data-node="'+escAttr(node.id)+'" onclick="focusGraphNode(this.dataset.node)">查看邻域</button>'+(node.page_path?'<button class="btn small" data-page="'+escAttr(node.page_path)+'" onclick="openGraphPage(this.dataset.page)">打开页面</button>':'')+'</div><h5>相关页面</h5>'+graphPageButtons(node.related_pages)+'<h5>直接关系</h5><div class="graph-relation-list">'+relationHtml+'</div>';
    return;
  }
  const edge=GRAPH.edges.find(item=>item.id===graphSelection.id);
  if(!edge){ graphSelection=null;renderGraphDetail();return; }
  const subject=nodeMap[edge.source_id],object=nodeMap[edge.target_id];
  const pages=edge.sources.map(source=>source.page);
  const evidence=[edge.evidence,...edge.sources.map(source=>source.evidence)].filter(Boolean);
  const sourceNames=[...new Set([edge.source,...edge.sources.map(source=>source.source)].filter(Boolean))];
  detail.innerHTML='<div class="graph-source-rail '+(edge.layers.includes('enriched')?'enriched':'')+'"><h4>'+esc(subject?shortGraphLabel(subject):'未知节点')+' → '+esc(predicateLabel(edge.predicate))+' → '+esc(object?shortGraphLabel(object):'未知节点')+'</h4></div><div class="graph-meta">'+edge.layers.map(layer=>'<span class="graph-chip '+layer+'">'+(layer==='enriched'?'富化层':'基础层')+'</span>').join('')+sourceNames.map(source=>'<span class="graph-chip">'+esc(sourceLabel(source))+'</span>').join('')+(edge.confidence!==null&&edge.confidence!==undefined?'<span class="graph-chip">置信度 '+confidenceLabel(edge.confidence)+'</span>':'')+'</div>'+(evidence.length?'<h5>证据</h5>'+[...new Set(evidence)].map(text=>'<div class="graph-evidence">'+esc(text)+'</div>').join(''):'')+'<h5>来源页面</h5>'+graphPageButtons(pages)+'<h5>端点</h5><div class="graph-node-index"><button class="graph-node-link" data-node="'+escAttr(edge.source_id)+'" onclick="selectGraphNode(this.dataset.node)">'+esc(subject?shortGraphLabel(subject):'未知节点')+'</button><button class="graph-node-link" data-node="'+escAttr(edge.target_id)+'" onclick="selectGraphNode(this.dataset.node)">'+esc(object?shortGraphLabel(object):'未知节点')+'</button></div>';
}

document.getElementById('graphCanvas').addEventListener('keydown',event=>{
  if(event.key==='Escape') clearGraphSelection();
});

function updateGraphFullscreenControl(){
  const card=document.getElementById('graphCard');
  const button=document.getElementById('graphFullscreenBtn');
  if(!card||!button) return;
  const active=document.fullscreenElement===card;
  button.textContent=active?'退出全屏':'⛶ 全屏';
  button.setAttribute('aria-pressed',active?'true':'false');
  if(!card.requestFullscreen){
    button.disabled=true;
    button.title='当前浏览器不支持全屏显示';
  }
}

async function toggleGraphFullscreen(){
  const card=document.getElementById('graphCard');
  if(!card||!card.requestFullscreen) return;
  try{
    if(document.fullscreenElement===card) await document.exitFullscreen();
    else await card.requestFullscreen();
  }catch(error){
    toast('无法切换全屏：'+error.message,true);
  }
}

document.addEventListener('fullscreenchange',()=>{
  updateGraphFullscreenControl();
  clearTimeout(graphResizeTimer);
  graphResizeTimer=setTimeout(resizeGraphRenderer,140);
});

window.addEventListener('resize',()=>{
  if(!document.getElementById('tab-graph').classList.contains('active')) return;
  clearTimeout(graphResizeTimer);graphResizeTimer=setTimeout(resizeGraphRenderer,160);
});
window.addEventListener('beforeunload',()=>{if(graphRenderer) graphRenderer.destroy();});

/* ==================== 工具 ==================== */
function esc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function escAttr(s){
  return esc(s).replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/* ==================== 启动 ==================== */
async function boot(){
  updateGraphFullscreenControl();
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
