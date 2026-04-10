// main.js — Velo Client Launcher (QWebChannel bridge)

// ── Bridge init ───────────────────────────────────────────────────────────────
let bridge = null;
let _pendingCalls = [];

new QWebChannel(qt.webChannelTransport, channel => {
    bridge = channel.objects.bridge;
    _pendingCalls.forEach(fn => fn());
    _pendingCalls = [];
    init();
});

// ── State ─────────────────────────────────────────────────────────────────────
let config = {};
let scriptsState = {};

// ── Global toggle click handler ───────────────────────────────────────────────
// Intercept in capture phase so data-on updates before browser default
document.addEventListener('click', e => {
    const label = e.target.closest('.toggle');
    if (!label) return;
    const input = label.querySelector('input[type="checkbox"]');
    if (!input) return;
    input.checked = !input.checked;
    label.setAttribute('data-on', input.checked ? 'true' : 'false');
    input.dispatchEvent(new Event('change', { bubbles: true }));
    e.preventDefault();
}, true);

// ── Overlay management ────────────────────────────────────────────────────────
function openOverlay(name) {
    document.getElementById('overlay-' + name).classList.add('open');
}
function closeOverlay(name) {
    document.getElementById('overlay-' + name).classList.remove('open');
}

document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => closeOverlay(btn.dataset.close));
});
document.querySelectorAll('.overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
        if (e.target === overlay) closeOverlay(overlay.id.replace('overlay-', ''));
    });
});

document.getElementById('btn-settings').addEventListener('click', () => {
    openOverlay('settings');
    loadResources();
});
document.getElementById('btn-scripts').addEventListener('click', () => {
    openOverlay('scripts');
    loadScripts();
});
document.getElementById('btn-logs').addEventListener('click', () => {
    openOverlay('logs');
});

// ── Accordion toggles ─────────────────────────────────────────────────────────
const expandMap = {
    'fps_limit_enabled':   'expand-fps',
    'window_size_enabled': 'expand-winsize',
    'crosshair_enabled':   'expand-crosshair',
    'resource_swapper':    'expand-resources',
    'custom_css_enabled':  'expand-css',
    'chrome_flags_enabled':'expand-flags',
};
const toggleInputMap = {
    'fps_limit_enabled':   's-fps-enabled',
    'window_size_enabled': 's-winsize-enabled',
    'crosshair_enabled':   's-ch-enabled',
    'resource_swapper':    's-res-enabled',
    'custom_css_enabled':  's-css-enabled',
    'chrome_flags_enabled':'s-flags-enabled',
};

Object.entries(expandMap).forEach(([key, expandId]) => {
    const cb = document.getElementById(toggleInputMap[key]);
    if (!cb) return;
    cb.addEventListener('change', () => {
        document.getElementById(expandId).classList.toggle('open', cb.checked);
        if (key === 'crosshair_enabled') drawCrosshairPreview();
    });
});

// ── Load config ───────────────────────────────────────────────────────────────
function loadConfig() {
    bridge.getConfig(result => {
        config = JSON.parse(result);
        applyConfig(config);
    });
}

function applyConfig(cfg) {
    const ch = cfg.crosshair || {};
    const cl = cfg.client    || {};

    setCheck('s-fps-enabled',    cl.fps_limit_enabled);
    setNum  ('s-fps-limit',      cl.fps_limit ?? 144);
    setCheck('s-fullscreen',     cl.fullscreen !== false);
    setCheck('s-winsize-enabled',cl.window_size_enabled);
    setNum  ('s-win-w',          cl.window_width  ?? 1280);
    setNum  ('s-win-h',          cl.window_height ?? 720);
    setCheck('s-ch-enabled',     ch.enabled);
    setCheck('s-res-enabled',    cl.resource_swapper);
    setCheck('s-css-enabled',    cl.custom_css_enabled);
    setText ('s-css',            cl.custom_css || '');
    setCheck('s-flags-enabled',  cl.chrome_flags_enabled);
    setText ('s-flags',          cl.chrome_flags || '');
    setCheck('s-gpu',            cl.enable_gpu !== false);
    setCheck('s-ads',            cl.block_ads !== false);
    setCheck('s-keep-open',      cl.keep_launcher_open !== false);
    setCheck('s-debug',          cl.debug_logs);
    document.getElementById('s-keybind').value = cl.show_menu_keybind || '`';

    setColor('s-ch-color',     's-ch-color-hex',  ch.color         || '#2dd4bf');
    setColor('s-ch-out-color', 's-ch-out-hex',    ch.outline_color || '#000000');
    setRange('s-ch-size',    'lbl-ch-size',    ch.size      ?? 12, v => v);
    setRange('s-ch-thick',   'lbl-ch-thick',   ch.thickness ?? 2,  v => v);
    setRange('s-ch-gap',     'lbl-ch-gap',     ch.gap       ?? 4,  v => v);
    setRange('s-ch-opacity', 'lbl-ch-opacity', Math.round((ch.opacity ?? 1) * 100), v => v + '%');
    setCheck('s-ch-outline', ch.outline !== false);
    document.getElementById('s-ch-style').value = ch.style || 'cross';

    Object.entries(expandMap).forEach(([key, expandId]) => {
        const cb = document.getElementById(toggleInputMap[key]);
        if (cb?.checked) document.getElementById(expandId).classList.add('open');
    });

    drawCrosshairPreview();
}

// ── Collect config ────────────────────────────────────────────────────────────
function collectConfig() {
    return {
        crosshair: {
            enabled:       getCheck('s-ch-enabled'),
            style:         document.getElementById('s-ch-style').value,
            color:         document.getElementById('s-ch-color').value,
            size:          getNum('s-ch-size'),
            thickness:     getNum('s-ch-thick'),
            gap:           getNum('s-ch-gap'),
            opacity:       getNum('s-ch-opacity') / 100,
            outline:       getCheck('s-ch-outline'),
            outline_color: document.getElementById('s-ch-out-color').value,
        },
        client: {
            fps_limit_enabled:    getCheck('s-fps-enabled'),
            fps_limit:            getNum('s-fps-limit'),
            fullscreen:           getCheck('s-fullscreen'),
            window_size_enabled:  getCheck('s-winsize-enabled'),
            window_width:         getNum('s-win-w'),
            window_height:        getNum('s-win-h'),
            keep_launcher_open:   getCheck('s-keep-open'),
            debug_logs:           getCheck('s-debug'),
            block_ads:            getCheck('s-ads'),
            enable_gpu:           getCheck('s-gpu'),
            show_menu_keybind:    document.getElementById('s-keybind').value || '`',
            resource_swapper:     getCheck('s-res-enabled'),
            custom_css_enabled:   getCheck('s-css-enabled'),
            custom_css:           document.getElementById('s-css').value,
            chrome_flags_enabled: getCheck('s-flags-enabled'),
            chrome_flags:         document.getElementById('s-flags').value,
        },
        scripts: scriptsState,
    };
}

// ── DOM helpers ───────────────────────────────────────────────────────────────
function setCheck(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    el.checked = !!val;
    const label = el.closest('.toggle');
    if (label) label.setAttribute('data-on', el.checked ? 'true' : 'false');
}
function getCheck(id)     { return document.getElementById(id)?.checked ?? false; }
function setNum(id, val)  { const el = document.getElementById(id); if (el) el.value = val; }
function getNum(id)       { return parseInt(document.getElementById(id)?.value || '0'); }
function setText(id, val) { const el = document.getElementById(id); if (el) el.value = val; }
function setColor(colorId, hexId, val) {
    const ci = document.getElementById(colorId);
    const hi = document.getElementById(hexId);
    if (ci) ci.value = val;
    if (hi) hi.value = val;
}
function setRange(sliderId, labelId, val, fmt) {
    const sl = document.getElementById(sliderId);
    const lb = document.getElementById(labelId);
    if (sl) sl.value = val;
    if (lb) lb.textContent = fmt(val);
}

// ── Color sync ────────────────────────────────────────────────────────────────
function bindColorSync(colorId, hexId) {
    const ci = document.getElementById(colorId);
    const hi = document.getElementById(hexId);
    if (!ci || !hi) return;
    ci.addEventListener('input', () => { hi.value = ci.value; drawCrosshairPreview(); });
    hi.addEventListener('input', () => {
        if (/^#[0-9a-fA-F]{6}$/.test(hi.value)) { ci.value = hi.value; drawCrosshairPreview(); }
    });
}
bindColorSync('s-ch-color',     's-ch-color-hex');
bindColorSync('s-ch-out-color', 's-ch-out-hex');

[
    ['s-ch-size',    'lbl-ch-size',    v => v],
    ['s-ch-thick',   'lbl-ch-thick',   v => v],
    ['s-ch-gap',     'lbl-ch-gap',     v => v],
    ['s-ch-opacity', 'lbl-ch-opacity', v => v + '%'],
].forEach(([sid, lid, fmt]) => {
    const sl = document.getElementById(sid);
    const lb = document.getElementById(lid);
    if (sl && lb) sl.addEventListener('input', () => { lb.textContent = fmt(sl.value); drawCrosshairPreview(); });
});
['s-ch-style', 's-ch-outline'].forEach(id =>
    document.getElementById(id)?.addEventListener('change', drawCrosshairPreview)
);

// ── Crosshair preview ─────────────────────────────────────────────────────────
function drawCrosshairPreview() {
    const canvas = document.getElementById('ch-preview');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, 100, 100);
    ctx.fillStyle = '#0a0b0d';
    ctx.fillRect(0, 0, 100, 100);
    if (!getCheck('s-ch-enabled')) return;

    const cx=50, cy=50;
    const col = document.getElementById('s-ch-color').value;
    const out = document.getElementById('s-ch-out-color').value;
    const sz  = parseInt(document.getElementById('s-ch-size').value);
    const th  = parseInt(document.getElementById('s-ch-thick').value);
    const gap = parseInt(document.getElementById('s-ch-gap').value);
    const op  = parseInt(document.getElementById('s-ch-opacity').value) / 100;
    const st  = document.getElementById('s-ch-style').value;
    const doO = getCheck('s-ch-outline');

    ctx.globalAlpha = op;
    function ln(x1,y1,x2,y2) {
        if (doO) { ctx.strokeStyle=out; ctx.lineWidth=th+2; ctx.lineCap='round'; ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke(); }
        ctx.strokeStyle=col; ctx.lineWidth=th; ctx.lineCap='round'; ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
    }
    if (st==='cross'||st==='cross+dot') { ln(cx-sz-gap,cy,cx-gap,cy); ln(cx+gap,cy,cx+sz+gap,cy); ln(cx,cy-sz-gap,cx,cy-gap); ln(cx,cy+gap,cx,cy+sz+gap); }
    if (st==='dot'||st==='cross+dot')   { const r=th+2; if(doO){ctx.fillStyle=out;ctx.beginPath();ctx.arc(cx,cy,r+1,0,Math.PI*2);ctx.fill();} ctx.fillStyle=col;ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fill(); }
    if (st==='circle')                  { if(doO){ctx.strokeStyle=out;ctx.lineWidth=th+2;ctx.beginPath();ctx.arc(cx,cy,sz,0,Math.PI*2);ctx.stroke();} ctx.strokeStyle=col;ctx.lineWidth=th;ctx.beginPath();ctx.arc(cx,cy,sz,0,Math.PI*2);ctx.stroke(); }
}

// ── Save settings ─────────────────────────────────────────────────────────────
document.getElementById('btn-save-settings').addEventListener('click', () => {
    const cfg = collectConfig();
    bridge.saveConfig(JSON.stringify(cfg));
    config = cfg;
    closeOverlay('settings');
    toast('Settings saved');
});

// ── Scripts ───────────────────────────────────────────────────────────────────
function loadScripts() {
    bridge.getScripts(result => {
        const scripts = JSON.parse(result);
        const list = document.getElementById('scripts-list');
        scripts.forEach(s => { scriptsState[s.name] = s.enabled; });
        if (!scripts.length) {
            list.innerHTML = '<div class="scripts-empty">No .js files found in scripts/ folder.</div>';
            return;
        }
        list.innerHTML = scripts.map(s => `
            <div class="script-item">
                <span class="script-name">${s.name}</span>
                <label class="toggle sm">
                    <input type="checkbox" ${s.enabled ? 'checked' : ''}
                        onchange="scriptsState['${s.name}'] = this.checked">
                    <div class="toggle-track"></div>
                </label>
            </div>
        `).join('');
    });
}

document.getElementById('btn-save-scripts').addEventListener('click', () => {
    const cfg = collectConfig();
    cfg.scripts = scriptsState;
    bridge.saveConfig(JSON.stringify(cfg));
    config.scripts = scriptsState;
    closeOverlay('scripts');
    toast('Scripts saved');
});

function openScriptsFolder()   { bridge.openScriptsFolder(); }

// ── Resources ─────────────────────────────────────────────────────────────────
function loadResources() {
    bridge.getResources(result => {
        const data  = JSON.parse(result);
        const list  = document.getElementById('res-list');
        const swaps = data.swaps || [];
        if (!swaps.length) {
            list.innerHTML = '<div class="res-empty">No swaps in resources/manifest.json yet.</div>';
            return;
        }
        list.innerHTML = swaps.map(s => `<div class="res-item">${s.file} → ${s.url}</div>`).join('');
    });
}

function openResourcesFolder() { bridge.openResourcesFolder(); }

// ── Cookies ───────────────────────────────────────────────────────────────────
function loadCookieInfo() {
    bridge.getCookiesInfo(result => {
        const data = JSON.parse(result);
        document.getElementById('cookie-count').textContent = data.count;
        const statusEl = document.getElementById('cookie-status');
        statusEl.textContent = data.exists ? 'Session saved' : 'No session';
        statusEl.className   = 'stat-value ' + (data.exists ? 'cookies-ok' : 'cookies-none');
    });
}

function clearCookies() {
    if (!confirm('Clear all saved cookies? You will need to log in again.')) return;
    bridge.clearCookies();
    loadCookieInfo();
    toast('Cookies cleared');
}

function exportCookies() { bridge.exportCookies(); }

// ── Logs ──────────────────────────────────────────────────────────────────────
const logOutput = document.getElementById('log-output');

function appendLog(line) {
    const span = document.createElement('span');
    span.className = 'log-line';
    if      (line.startsWith('[LAUNCHER]')) span.classList.add('log-launcher');
    else if (line.startsWith('[KRUNKER]'))  span.classList.add('log-krunker');
    else                                    span.classList.add('log-other');
    span.textContent = line;
    logOutput.appendChild(span);
    logOutput.scrollTop = logOutput.scrollHeight;
}

function clearLogs() {
    logOutput.innerHTML = '';
    const cmLog = document.getElementById('cm-log');
    if (cmLog) cmLog.innerHTML = '';
}

// ── Console mode (triggered by Python when game starts/stops) ─────────────────
function enterConsoleMode() {
    document.getElementById('app').style.display = 'none';
    document.querySelectorAll('.overlay').forEach(o => o.classList.remove('open'));

    let panel = document.getElementById('console-mode');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'console-mode';
        panel.innerHTML = `
            <div id="cm-header">
                <div id="cm-title">
                    <span class="velo-tb-name">VELO</span>
                    <span class="velo-tb-client">CLIENT</span>
                    <span id="cm-status">— Game running</span>
                </div>
                <button class="ghost-btn sm" onclick="clearLogs()">Clear</button>
            </div>
            <div id="cm-log"></div>
        `;
        document.body.appendChild(panel);
    }
    panel.style.display = 'flex';

    // Wrap appendLog to also write into cm-log
    const cmLog = document.getElementById('cm-log');
    window._origAppendLog = window.appendLog;
    window.appendLog = line => {
        window._origAppendLog(line);
        const span = document.createElement('span');
        span.className = 'log-line ' + (
            line.startsWith('[LAUNCHER]') ? 'log-launcher' :
            line.startsWith('[KRUNKER]')  ? 'log-krunker'  : 'log-other'
        );
        span.textContent = line;
        cmLog.appendChild(span);
        cmLog.scrollTop = cmLog.scrollHeight;
    };
}

function exitConsoleMode() {
    const panel = document.getElementById('console-mode');
    if (panel) panel.style.display = 'none';
    document.getElementById('app').style.display = '';
    if (window._origAppendLog) {
        window.appendLog = window._origAppendLog;
        window._origAppendLog = null;
    }
}

// ── Launch ────────────────────────────────────────────────────────────────────
document.getElementById('btn-play').addEventListener('click', () => {
    const cfg = collectConfig();
    bridge.launch(JSON.stringify(cfg));
    toast('Launching Krunker...');
});

// ── Titlebar drag ─────────────────────────────────────────────────────────────
function initTitlebarDrag() {
    const bar = document.getElementById('velo-titlebar');
    if (!bar) { setTimeout(initTitlebarDrag, 100); return; }

    let dragging = false, ox = 0, oy = 0;
    bar.addEventListener('mousedown', e => {
        if (e.target.closest('.velo-tb-btn')) return;
        dragging = true; ox = e.screenX; oy = e.screenY;
        e.preventDefault();
    });
    window.addEventListener('mousemove', e => {
        if (!dragging) return;
        bridge.moveWindow(e.screenX - ox, e.screenY - oy);
        ox = e.screenX; oy = e.screenY;
    });
    window.addEventListener('mouseup', () => { dragging = false; });
    bar.addEventListener('dblclick', e => {
        if (e.target.closest('.velo-tb-btn')) return;
        bridge.maximize();
    });
}
setTimeout(initTitlebarDrag, 300);

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2400);
}

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
    loadConfig();
    loadCookieInfo();
}