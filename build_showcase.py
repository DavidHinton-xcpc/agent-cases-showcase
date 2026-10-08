#!/usr/bin/env python3
"""Build a single-file showcase.html for the agent-cases-showcase packet.

- Embeds every HTML page (58) as JSON string values; runtime routes via iframe srcdoc.
- Internal links are rewritten to `scs:` markers; an injected interceptor routes clicks.
- Small text files (.md/.txt/.py/.json) are embedded as text panels (T:).
- Binary / too-large files (.zip/.docx/.jsonl) become placeholder panels (P:).
"""
import re, os, json, posixpath

BASE = "/home/xiachen/sync/packets/20261008T1245_agent-cases-showcase"
SESS = os.path.join(BASE, "session")
OUT = os.path.join(BASE, "showcase.html")

# ---------- collect pages ----------
pages = {}  # key (path rel to session/) -> html text
def addpage(p):
    key = posixpath.relpath(os.path.relpath(p, BASE), "session")
    pages[key] = open(p, encoding="utf-8").read()

for f in sorted(os.listdir(SESS)):
    if f.endswith(".html"):
        addpage(os.path.join(SESS, f))
for sub in ("view", "cases"):
    for f in sorted(os.listdir(os.path.join(SESS, sub))):
        if f.endswith(".html"):
            addpage(os.path.join(SESS, sub, f))
print("pages:", len(pages))

# ---------- collect all local refs across pages ----------
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

href_re = re.compile(r'(<a\b[^>]*?href\s*=\s*")([^"]*)(")')
refs = set()
for key, txt in pages.items():
    for m in href_re.finditer(txt):
        v = m.group(2)
        if re.match(r'^(#|https?:|data:|mailto:|javascript:|scs:)', v):
            continue
        refs.add((key, v))
print("local refs:", len(refs))

# ---------- classify refs ----------
def vpath(key, ref_path):
    """virtual path of ref, rel to BASE"""
    d = posixpath.dirname(key)
    vp = posixpath.normpath(posixpath.join(d, ref_path))
    return posixpath.relpath(os.path.join("session", vp), "session") if False else posixpath.normpath(posixpath.join("session", d, ref_path))

TEXT_EXTS = {".md", ".txt", ".py", ".json"}
MAX_TEXT = 300 * 1024
texts, placeholders, missing = {}, {}, set()

def classify(ref_abs_from_base):
    ext = os.path.splitext(ref_abs_from_base)[1].lower()
    p = os.path.join(BASE, ref_abs_from_base)
    if ext in TEXT_EXTS and os.path.exists(p) and os.path.getsize(p) <= MAX_TEXT:
        texts[ref_abs_from_base] = open(p, encoding="utf-8", errors="replace").read()
        return "T:" + ref_abs_from_base
    if os.path.exists(p):
        placeholders[ref_abs_from_base] = os.path.getsize(p)
    else:
        missing.add(ref_abs_from_base)
        placeholders[ref_abs_from_base] = None
    return "P:" + ref_abs_from_base

def marker_for(key, ref):
    path, frag = (ref.split("#", 1) + [""])[:2]
    ref_abs = vpath(key, path)
    if ref_abs.endswith(".html") and ref_abs[0] != "/":
        p = os.path.join(BASE, ref_abs)
        key2 = posixpath.relpath(os.path.relpath(p, BASE), "session")
        if key2 in pages:
            return "scs:" + key2 + ("#" + frag if frag else "")
    m = classify(ref_abs)
    return "scs:" + m + ("#" + frag if frag else "")

rewritten = 0
leftovers = []
for key in list(pages):
    def sub(m):
        global rewritten
        head, v, tail = m.group(1), m.group(2), m.group(3)
        if re.match(r'^(#|https?:|data:|mailto:|javascript:|scs:)', v):
            return m.group(0)
        rewritten += 1
        return head + marker_for(key, v) + tail
    pages[key] = href_re.sub(sub, pages[key])
    # find any non-<a> local refs we may have missed (should be none)
    for m in re.finditer(r'href\s*=\s*"([^"]*)"', pages[key]):
        v = m.group(1)
        if re.match(r'^(#|https?:|data:|mailto:|javascript:|scs:)', v):
            continue
        if m.start() > 0 and not re.search(r'<a\b', pages[key][max(0, m.start()-400):m.start()] or ""):
            leftovers.append((key, v))
print("rewritten:", rewritten, "text embeds:", len(texts), "placeholders:", len(placeholders), "missing files:", sorted(missing))
print("leftover local hrefs (non-<a>):", leftovers[:10])

# ---------- interceptor + goBack override appended to every page ----------
INTERCEPT = """<script data-scs="1">
(function(){
  function onC(ev){
    var n = ev.target, a = null;
    while (n && n !== document) {
      if (n.tagName === 'A' && n.hasAttribute('href')) { a = n; break; }
      n = n.parentElement;
    }
    if (!a) return;
    var h = a.getAttribute('href');
    if (!h || h.indexOf('scs:') !== 0) return;
    ev.preventDefault(); ev.stopPropagation();
    var i = h.indexOf('#');
    var key  = (i >= 0 ? h.slice(4, i) : h.slice(4));
    var frag = (i >= 0 ? h.slice(i) : '');
    try { if (window.parent && window.parent.SCS_NAV) window.parent.SCS_NAV(key, frag); } catch (e) {}
  }
  document.addEventListener('click', onC, true);
})();
function goBack(){
  try { if (window.parent && window.parent !== window && window.parent.SCS_BACK) { window.parent.SCS_BACK(); return; } } catch (e) {}
  if (document.referrer) { history.back(); } else { location.href = "index.html"; }
}
</script>
"""
for key in list(pages):
    t = pages[key]
    i = t.rfind("</body>")
    pages[key] = (t[:i] + INTERCEPT + t[i:] if i > 0 else t + INTERCEPT)

# ---------- sizes meta ----------
META = {}
for p in placeholders: META[p] = placeholders[p]
for p in texts: META[p] = os.path.getsize(os.path.join(BASE, p))

# ---------- shell ----------
def title_of(key):
    m = re.search(r"<title>([^<]*)</title>", pages[key], re.S)
    return m.group(1).strip() if m else key

def doc_label(key):
    base = key.split("/")[-1]
    b = re.sub(r"\.html$", "", base)
    return b.replace("__", " / ")

case_opts = ['<option value="">案例 ▾</option>',
             '<option value="cases/index.html">案例总览</option>']
for i in range(1, 8):
    k = f"cases/case{i}.html"
    case_opts.append(f'<option value="{k}">案例 {i} · {esc(title_of(k))[:48]}</option>')

sess_opts = ['<option value="">会话 ▾</option>',
             '<option value="sessions.html">全部会话</option>']
tops = [k for k in sorted(pages) if k.endswith(".html") and "/" not in k and k not in ("index.html", "sessions.html")]
for k in tops:
    sess_opts.append(f'<option value="{k}">{esc(title_of(k)[:44] or k)}</option>')

doc_opts = ['<option value="">文档 ▾</option>']
views = [k for k in sorted(pages) if k.startswith("view/")]
for k in views:
    doc_opts.append(f'<option value="{esc(k)}">{esc(doc_label(k))}</option>')

all_opts = ['<option value="">全部页面 ▾</option>']
for i in range(1, 8):
    k = f"cases/case{i}.html"
    all_opts.append(f'<option value="{k}">案例 {i} · {esc(title_of(k)[:40])}</option>')
all_opts.append('<option value="index.html">案例总览</option>')
all_opts.append('<option value="sessions.html">全部会话</option>')
for k in sorted(k for k in pages if k.endswith(".html") and "/" not in k and k not in ("index.html", "sessions.html")):
    all_opts.append(f'<option value="{esc(k)}">{esc(title_of(k)[:44] or k)}</option>')
for k in views:
    all_opts.append(f'<option value="{esc(k)}">文档 · {esc(doc_label(k))}</option>')

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

PAGES_JSON = json.dumps(pages, ensure_ascii=False).replace("</", "<\\/")
TEXTS_JSON = json.dumps(texts, ensure_ascii=False).replace("</", "<\\/")
META_JSON  = json.dumps(META, ensure_ascii=False)

SHELL = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>案例展示 · 单文件版 · Agent 辅助英语听说周作业</title>
<style>
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; }
body { display: flex; flex-direction: column; font-family: "Segoe UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif; }
#bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 7px 12px;
  background: #1d2433; color: #e8ecf4; font-size: 13px; min-height: 42px; }
#bar .brand { font-weight: 700; letter-spacing: .04em; margin-right: 4px; white-space: nowrap; }
#bar .brand small { font-weight: 400; opacity: .55; margin-left: 6px; }
#bar button { border: 1px solid #3b465e; background: #2a3348; color: #e8ecf4; border-radius: 8px;
  padding: 4px 11px; font-size: 12.5px; cursor: pointer; }
#bar button:hover { background: #354158; }
#bar select { background: #2a3348; color: #e8ecf4; border: 1px solid #3b465e; border-radius: 8px;
  padding: 4px 8px; font-size: 12.5px; max-width: 320px; }
#crumb { margin-left: auto; font-size: 11.5px; color: #8d99b3; max-width: 42vw; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; direction: rtl; text-align: left; }
#vf { flex: 1; width: 100%; border: 0; background: #fff; }
#selAll { display: none; }
@media (max-width: 700px) {
  #bar { flex-wrap: nowrap; gap: 6px; padding: 5px 10px; }
  #bar .brand { font-size: 12.5px; }
  #bar .brand small { display: none; }
  #bar button { font-size: 12px; padding: 3px 9px; white-space: nowrap; }
  .selTriple select { display: none; }
  #selAll { display: block; flex: 1 1 auto; min-width: 0; width: auto; font-size: 13px;
    padding: 5px 8px; text-overflow: ellipsis; }
  #crumb { display: none; }
}
</style></head>
<body>
<header id="bar">
  <span class="brand">W01 案例展示<small>单文件 · 离线可开</small></span>
  <button onclick="SCS_NAV('index.html')">总览</button>
  <span class="selTriple">
  <select id="selCase" onchange="if(this.value)SCS_NAV(this.value)">__CASE_OPTS__</select>
  <select id="selSess" onchange="if(this.value)SCS_NAV(this.value)">__SESS_OPTS__</select>
  <select id="selDoc" onchange="if(this.value)SCS_NAV(this.value)">__DOC_OPTS__</select>
  </span>
  <select id="selAll" onchange="if(this.value)SCS_NAV(this.value)">__ALL_OPTS__</select>
  <span id="crumb"></span>
</header>
<iframe id="vf" title="showcase"></iframe>
<script>
var PAGES = __PAGES__;
var TEXTS = __TEXTS__;
var META  = __META__;
var HOME = "index.html", cur = "", stack = [];
var vf = document.getElementById("vf");
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function textPanel(k){
  var p = k.slice(2), m = META[p] || 0;
  return '<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>'+esc(p)+'</title>'
   + '<style>body{margin:0;font:12.5px/1.75 ui-monospace,"Cascadia Code",Consolas,"Microsoft YaHei",monospace;color:#242a33;background:#fafbfc}'
   + 'header{position:sticky;top:0;z-index:9;background:#fff;border-bottom:1px solid #e2e6ec;padding:9px 16px;'
   + 'font:13px system-ui;display:flex;gap:10px;align-items:center}header .sp{color:#5b6472;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'
   + 'button{border:1px solid #c9d1dc;background:#f4f6f9;border-radius:8px;padding:3px 10px;cursor:pointer;font-size:12.5px}'
   + 'pre{white-space:pre-wrap;word-break:break-word;padding:16px 20px;max-width:1080px;margin:0 auto}</style>'
   + '</head><body><header><button onclick="parent.SCS_BACK()">&larr; 返回</button>'
   + '<span class="sp">'+esc(p)+' · '+(m/1024).toFixed(1)+' KB · 已嵌入文本</span></header>'
   + '<pre>'+esc(TEXTS[p])+'</pre></body></html>';
}
function phPanel(k){
  var p = k.slice(2), m = META[p];
  return '<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>原始文件</title>'
   + '<style>body{font:14px/1.8 "Segoe UI","PingFang SC",system-ui;background:#f4f6f9;color:#242a33;margin:0}'
   + '.wrap{max-width:640px;margin:60px auto;background:#fff;border:1px solid #dde3ec;border-radius:14px;padding:26px 30px}'
   + 'code{background:#eef1f6;border-radius:6px;padding:1px 6px;font-size:12.5px;word-break:break-all}'
   + 'button{margin-top:18px;border:1px solid #c9d1dc;background:#fff;border-radius:8px;padding:6px 16px;cursor:pointer}</style>'
   + '</head><body><div class="wrap"><h2 style="margin-top:0">原始文件（未嵌入）</h2>'
   + '<p>单文件模式下此链接指向原始文件，'+(m!=null&&m>=204800?'体积较大':'为二进制或原始数据')+'，未嵌入本页面。</p>'
   + '<p>文件：<code>20261008T1245_agent-cases-showcase/'+esc(p)+'</code>'
   +(m!=null?'（'+(m/1024/1024).toFixed(1)+' MB）':'（原始包中不存在）')+'</p>'
   + '<button onclick="parent.SCS_BACK()">&larr; 返回</button></div></body></html>';
}
function srcdocFor(k){
  if (PAGES[k]) return PAGES[k];
  if (k.charAt(0) === "T" && TEXTS[k.slice(2)]) return textPanel(k);
  if (k.charAt(0) === "P") return phPanel(k);
  return '<!doctype html><html><head><meta charset="utf-8"></head><body style="font:14px system-ui;padding:40px"><h2>未找到页面：'+esc(k)+'</h2></body></html>';
}
function setSel(k){
  ["selCase","selSess","selDoc","selAll"].forEach(function(id){
    var el = document.getElementById(id);
    if ([].some.call(el.options, function(o){ return o.value === k; })) el.value = k;
    else el.selectedIndex = 0;
  });
}
function crumbLabel(k){
  if (k.charAt(0) === "T") return "文本 · " + k.slice(2);
  if (k.charAt(0) === "P") return "（未嵌入）" + k.slice(2);
  return k;
}
function load(k, frag, fromHash){
  cur = k;
  vf.srcdoc = srcdocFor(k);
  stack.push(k);
  if (!fromHash) { try { location.hash = "!/" + encodeURIComponent(k); } catch (e) {} }
  document.getElementById("crumb").textContent = crumbLabel(k);
  setSel(k);
  if (frag) setTimeout(function(){ try { vf.contentWindow.location.hash = frag; } catch (e) {} }, 120);
}
window.SCS_NAV = function(k, frag){ load(k, frag, false); };
window.SCS_BACK = function(){
  if (stack.length > 2) { stack.pop(); load(stack[stack.length - 1], "", false); }
  else { stack = [HOME]; load(HOME, "", false); }
};
window.addEventListener("hashchange", function(){
  var h = location.hash.replace(/^#/, ""), k = "";
  if (h.slice(0, 2) === "!/") {
    try { k = decodeURIComponent(h.slice(2)); } catch (e) {}
  }
  if (!k) k = HOME;
  var ok = PAGES[k] || (k.charAt(0) === "T" && TEXTS[k.slice(2)]) || (k.charAt(0) === "P");
  if (!ok) k = HOME;
  if (k !== cur) { stack = [HOME, k]; load(k, "", true); }
});
(function(){
  var h = location.hash.replace(/^#/, ""), k = "";
  if (h.slice(0, 2) === "!/") { try { k = decodeURIComponent(h.slice(2)); } catch (e) {} }
  var ok = k && (PAGES[k] || (k.charAt(0) === "T" && TEXTS[k.slice(2)]) || (k.charAt(0) === "P"));
  stack = [HOME];
  load(ok ? k : HOME, "", true);
})();
</script>
</body></html>
"""
SHELL = SHELL.replace("__CASE_OPTS__", "\n".join(case_opts))
SHELL = SHELL.replace("__SESS_OPTS__", "\n".join(sess_opts))
SHELL = SHELL.replace("__DOC_OPTS__", "\n".join(doc_opts))
SHELL = SHELL.replace("__ALL_OPTS__", "\n".join(all_opts))
SHELL = SHELL.replace("__PAGES__", PAGES_JSON)
SHELL = SHELL.replace("__TEXTS__", TEXTS_JSON)
SHELL = SHELL.replace("__META__", META_JSON)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(SHELL)
print("written", OUT, os.path.getsize(OUT) // 1024 // 1024, "MB",
      os.path.getsize(OUT) // 1024, "KB")
