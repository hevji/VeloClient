"""
krunker/krunker.py — Velo Client Game Runner
All paths resolved relative to project root (one level up).

Requirements:
    pip install playwright screeninfo pywin32
    playwright install chromium
"""
print("Starting Velo Client...")
import json
import os
import sys
import time
import threading

from playwright.sync_api import sync_playwright
from screeninfo import get_monitors
import win32gui, win32con, win32api

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE   = os.path.join(ROOT, "config", "client_config.json")
COOKIES_FILE  = os.path.join(ROOT, "cookies", "cookies.json")
SCRIPTS_DIR   = os.path.join(ROOT, "scripts")
RESOURCES_DIR = os.path.join(ROOT, "resources")
MANIFEST_FILE = os.path.join(RESOURCES_DIR, "manifest.json")
USER_DATA_DIR = os.path.join(ROOT, "browser_profile")

KRUNKER_URL    = "https://krunker.io"
KRUNKER_DOMAIN = "krunker.io"

BLOCKED_DOMAINS = [
    "googlesyndication.com", "doubleclick.net", "google-analytics.com",
    "googletagmanager.com", "googletagservices.com", "adservice.google.com",
    "amazon-adsystem.com", "advertising.com", "adnxs.com", "adsrvr.org",
    "pubmatic.com", "rubiconproject.com", "openx.net", "casalemedia.com",
    "smartadserver.com", "criteo.com", "moatads.com", "outbrain.com",
    "taboola.com", "scorecardresearch.com", "quantserve.com", "chartbeat.com",
    "newrelic.com", "hotjar.com", "mouseflow.com", "fullstory.com",
    "segment.com", "amplitude.com", "mixpanel.com", "connect.facebook.net",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def log(msg):
    print(msg, flush=True)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_cookies(context):
    """Save all cookies from the persistent context to cookies.json."""
    os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
    cookies = context.cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    log(f"Saved {len(cookies)} cookies")

def get_primary_monitor():
    monitors = get_monitors()
    for m in monitors:
        if m.is_primary:
            return m.width, m.height
    return monitors[0].width, monitors[0].height

def load_userscripts(scripts_cfg):
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    scripts = []
    for filename in sorted(os.listdir(SCRIPTS_DIR)):
        if not filename.endswith(".js"):
            continue
        if not scripts_cfg.get(filename, True):
            log(f"Script skipped (disabled): {filename}")
            continue
        with open(os.path.join(SCRIPTS_DIR, filename), encoding="utf-8") as f:
            code = f.read()
        scripts.append((filename, code))
        log(f"Script loaded: {filename}")
    return scripts

def load_resource_swaps():
    if not os.path.exists(MANIFEST_FILE):
        return []
    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)
    swaps = []
    for entry in manifest.get("swaps", []):
        local_path = os.path.join(RESOURCES_DIR, entry.get("file", ""))
        url        = entry.get("url", "")
        if url and os.path.exists(local_path):
            swaps.append((url, local_path))
            log(f"Resource swap: {url} → {entry['file']}")
        elif url:
            log(f"Resource swap skipped (file missing): {entry.get('file')}")
    return swaps

def force_fullscreen(title_fragment="krunker", retries=20, delay=0.5):
    for _ in range(retries):
        found = []
        def cb(hwnd, res):
            if win32gui.IsWindowVisible(hwnd):
                if title_fragment.lower() in win32gui.GetWindowText(hwnd).lower():
                    res.append(hwnd)
        win32gui.EnumWindows(cb, found)
        if found:
            hwnd = found[0]
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)
            win32api.keybd_event(win32con.VK_F11, 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(win32con.VK_F11, 0, win32con.KEYEVENTF_KEYUP, 0)
            log("Fullscreen activated")
            return True
        time.sleep(delay)
    log("Warning: could not find window to fullscreen")
    return False
# ── Overlay JS ────────────────────────────────────────────────────────────────
def build_client_js(config):
    ch       = config.get("crosshair", {})
    cl       = config.get("client", {})
    keybind  = cl.get("show_menu_keybind", "`").replace("'", "\\'")
    ch_json  = json.dumps(ch)
    fps_cap  = cl.get("fps_limit", 144) if cl.get("fps_limit_enabled") else 0
    css_code = cl.get("custom_css", "").replace("`", "\\`") if cl.get("custom_css_enabled") else ""

    return f"""
(function() {{
    if (window.__veloLoaded) return;
    window.__veloLoaded = true;
    window.__veloClose  = false;

    window.__veloSettings = {{
        fps:        {str(cl.get('fps_counter', True)).lower()},
        ping:       {str(cl.get('ping_display', True)).lower()},
        autoRejoin: {str(cl.get('auto_rejoin', True)).lower()},
        crosshair:  {str(ch.get('enabled', False)).lower()},
        menuOpen:   false,
    }};

    if (`{css_code}`) {{
        const s = document.createElement('style');
        s.textContent = `{css_code}`;
        document.head.appendChild(s);
    }}

    // ── Styles ────────────────────────────────────────────────────────────
    const style = document.createElement('style');
    style.textContent = `
        #velo-close {{
            position:fixed!important;top:14px!important;right:14px!important;
            z-index:2147483647!important;padding:7px 16px!important;
            font-family:'Inter',sans-serif!important;font-size:12px!important;
            font-weight:600!important;letter-spacing:1px!important;
            text-transform:uppercase!important;color:#0f172a!important;
            background:#2dd4bf!important;border:none!important;
            border-radius:6px!important;cursor:pointer!important;
            outline:none!important;user-select:none!important;
            opacity:0.15!important;transition:opacity .15s!important;
        }}
        #velo-close:hover{{opacity:1!important;}}
        #velo-hud{{
            position:fixed!important;top:10px!important;left:10px!important;
            z-index:2147483646!important;display:flex!important;
            flex-direction:column!important;gap:3px!important;pointer-events:none!important;
        }}
        .velo-hud-item{{
            background:rgba(0,0,0,0.55)!important;color:#fff!important;
            font-size:12px!important;font-weight:600!important;
            padding:2px 8px!important;border-radius:4px!important;font-family:monospace!important;
        }}
        #velo-menu{{
            position:fixed!important;top:50%!important;left:50%!important;
            transform:translate(-50%,-50%)!important;
            z-index:2147483647!important;width:300px!important;
            background:#16181c!important;border:1px solid rgba(45,212,191,0.25)!important;
            border-radius:10px!important;overflow:hidden!important;
            box-shadow:0 8px 32px rgba(0,0,0,0.8)!important;
        }}
        #velo-menu-header{{
            background:#2dd4bf!important;padding:11px 16px!important;
            display:flex!important;justify-content:space-between!important;align-items:center!important;
        }}
        #velo-menu-title{{
            color:#0f172a!important;font-size:13px!important;font-weight:700!important;
            letter-spacing:1.5px!important;font-family:'Inter',sans-serif!important;
        }}
        #velo-menu-x{{
            color:#0f172a!important;background:none!important;border:none!important;
            font-size:16px!important;cursor:pointer!important;padding:0!important;
        }}
        #velo-menu-body{{padding:12px!important;display:flex!important;flex-direction:column!important;gap:6px!important;}}
        .velo-row{{
            display:flex!important;justify-content:space-between!important;align-items:center!important;
            padding:7px 10px!important;background:#1e2028!important;
            border-radius:6px!important;border:1px solid rgba(255,255,255,0.06)!important;
        }}
        .velo-label{{color:#cbd5e1!important;font-size:12px!important;font-family:'Inter',sans-serif!important;}}
        .velo-sw{{position:relative!important;width:36px!important;height:20px!important;cursor:pointer!important;}}
        .velo-sw input{{opacity:0!important;width:0!important;height:0!important;}}
        .velo-track{{
            position:absolute!important;inset:0!important;
            background:rgba(255,255,255,0.1)!important;border-radius:10px!important;transition:.18s!important;
        }}
        .velo-track::before{{
            content:''!important;position:absolute!important;
            width:14px!important;height:14px!important;left:3px!important;top:3px!important;
            background:rgba(255,255,255,0.4)!important;border-radius:50%!important;transition:.18s!important;
        }}
        .velo-sw input:checked+.velo-track{{background:#2dd4bf!important;}}
        .velo-sw input:checked+.velo-track::before{{transform:translateX(16px)!important;background:#fff!important;}}
        #velo-hint{{text-align:center!important;color:#475569!important;font-size:10px!important;
            padding:8px!important;font-family:monospace!important;}}
        #velo-ch{{
            position:fixed!important;top:50%!important;left:50%!important;
            transform:translate(-50%,-50%)!important;
            z-index:2147483645!important;pointer-events:none!important;
        }}
    `;
    document.head.appendChild(style);

    // ── FPS cap ───────────────────────────────────────────────────────────
    const fpsCap = {fps_cap};
    if (fpsCap > 0) {{
        const _raf = window.requestAnimationFrame.bind(window);
        const interval = 1000 / fpsCap;
        let last = 0;
        window.requestAnimationFrame = function(cb) {{
            return _raf(function(ts) {{
                if (ts - last >= interval) {{ last = ts; cb(ts); }}
                else window.requestAnimationFrame(cb);
            }});
        }};
    }}

    // ── Close button ──────────────────────────────────────────────────────
    const closeBtn = document.createElement('button');
    closeBtn.id = 'velo-close'; closeBtn.textContent = 'CLOSE';
    closeBtn.onclick = () => window.__veloClose = true;
    document.body.appendChild(closeBtn);

    // ── HUD ───────────────────────────────────────────────────────────────
    const hud = document.createElement('div'); hud.id = 'velo-hud';
    const fpsEl  = document.createElement('div'); fpsEl.className = 'velo-hud-item';
    const pingEl = document.createElement('div'); pingEl.className = 'velo-hud-item';
    hud.appendChild(fpsEl); hud.appendChild(pingEl);
    document.body.appendChild(hud);

    let frames=0, lastT=performance.now();
    function countFps(){{
        frames++;
        const now=performance.now();
        if(now-lastT>=500){{
            const fps=Math.round(frames*1000/(now-lastT));
            frames=0; lastT=now;
            fpsEl.style.display=window.__veloSettings.fps?'':'none';
            fpsEl.textContent=fps+' FPS';
            fpsEl.style.color=fps>=60?'#2dd4bf':fps>=30?'#eab308':'#ef4444';
        }}
        requestAnimationFrame(countFps);
    }}
    requestAnimationFrame(countFps);

    setInterval(()=>{{
        pingEl.style.display=window.__veloSettings.ping?'':'none';
        const p=window.ping!==undefined?window.ping:null;
        pingEl.textContent=p!==null?p+' ms':'-- ms';
        pingEl.style.color=p===null?'#94a3b8':p<50?'#2dd4bf':p<100?'#eab308':'#ef4444';
    }},800);

    // ── Crosshair ─────────────────────────────────────────────────────────
    const canvas=document.createElement('canvas');
    canvas.id='velo-ch'; canvas.width=120; canvas.height=120;
    document.body.appendChild(canvas);

    function drawCH(){{
        const cfg={ch_json};
        canvas.style.display=(window.__veloSettings.crosshair&&cfg.enabled)?'':'none';
        if(!window.__veloSettings.crosshair||!cfg.enabled) return;
        const ctx=canvas.getContext('2d');
        ctx.clearRect(0,0,120,120);
        const cx=60,cy=60,col=cfg.color||'#2dd4bf',out=cfg.outline_color||'#000',
              sz=cfg.size||12,th=cfg.thickness||2,gap=cfg.gap||4,
              op=cfg.opacity!==undefined?cfg.opacity:1,st=cfg.style||'cross',doO=cfg.outline!==false;
        ctx.globalAlpha=op;
        function ln(x1,y1,x2,y2){{
            if(doO){{ctx.strokeStyle=out;ctx.lineWidth=th+2;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}}
            ctx.strokeStyle=col;ctx.lineWidth=th;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
        }}
        if(st==='cross'||st==='cross+dot'){{ln(cx-sz-gap,cy,cx-gap,cy);ln(cx+gap,cy,cx+sz+gap,cy);ln(cx,cy-sz-gap,cx,cy-gap);ln(cx,cy+gap,cx,cy+sz+gap);}}
        if(st==='dot'||st==='cross+dot'){{const r=th+2;if(doO){{ctx.fillStyle=out;ctx.beginPath();ctx.arc(cx,cy,r+1,0,Math.PI*2);ctx.fill();}}ctx.fillStyle=col;ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fill();}}
        if(st==='circle'){{if(doO){{ctx.strokeStyle=out;ctx.lineWidth=th+2;ctx.beginPath();ctx.arc(cx,cy,sz,0,Math.PI*2);ctx.stroke();}}ctx.strokeStyle=col;ctx.lineWidth=th;ctx.beginPath();ctx.arc(cx,cy,sz,0,Math.PI*2);ctx.stroke();}}
    }}
    drawCH();

    // ── Auto-rejoin ───────────────────────────────────────────────────────
    setInterval(()=>{{
        if(!window.__veloSettings.autoRejoin) return;
        const end=document.querySelector('.endBoard,.endBoardWrapper,[class*="endBoard"]');
        if(end){{const btn=document.querySelector('[class*="playBtn"],[class*="playButton"]');if(btn)btn.click();}}
    }},3000);

    // ── In-game menu ──────────────────────────────────────────────────────
    function mkSw(checked,onChange){{
        const lbl=document.createElement('label');lbl.className='velo-sw';
        const inp=document.createElement('input');inp.type='checkbox';inp.checked=checked;
        inp.onchange=()=>onChange(inp.checked);
        const tr=document.createElement('div');tr.className='velo-track';
        lbl.appendChild(inp);lbl.appendChild(tr);return lbl;
    }}
    function mkRow(text,checked,onChange){{
        const row=document.createElement('div');row.className='velo-row';
        const lbl=document.createElement('span');lbl.className='velo-label';lbl.textContent=text;
        row.appendChild(lbl);row.appendChild(mkSw(checked,onChange));return row;
    }}

    const menu=document.createElement('div');menu.id='velo-menu';menu.style.display='none';
    const mh=document.createElement('div');mh.id='velo-menu-header';
    const mt=document.createElement('span');mt.id='velo-menu-title';mt.textContent='VELO CLIENT';
    const mx=document.createElement('button');mx.id='velo-menu-x';mx.textContent='✕';
    mx.onclick=()=>{{menu.style.display='none';window.__veloSettings.menuOpen=false;}};
    mh.appendChild(mt);mh.appendChild(mx);
    const mb=document.createElement('div');mb.id='velo-menu-body';
    mb.appendChild(mkRow('FPS Counter',    window.__veloSettings.fps,        v=>{{window.__veloSettings.fps=v;}}));
    mb.appendChild(mkRow('Ping Display',   window.__veloSettings.ping,       v=>{{window.__veloSettings.ping=v;}}));
    mb.appendChild(mkRow('Custom Crosshair',window.__veloSettings.crosshair, v=>{{window.__veloSettings.crosshair=v;drawCH();}}));
    mb.appendChild(mkRow('Auto-Rejoin',    window.__veloSettings.autoRejoin, v=>{{window.__veloSettings.autoRejoin=v;}}));
    const hint=document.createElement('div');hint.id='velo-hint';
    hint.textContent="Press '{keybind}' to toggle";
    menu.appendChild(mh);menu.appendChild(mb);menu.appendChild(hint);
    document.body.appendChild(menu);

    document.addEventListener('keydown',e=>{{
        if(e.key==='{keybind}'){{
            window.__veloSettings.menuOpen=!window.__veloSettings.menuOpen;
            menu.style.display=window.__veloSettings.menuOpen?'block':'none';
        }}
    }});
}})();
"""

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    config = load_config()
    cl     = config.get("client", {})
    debug  = cl.get("debug_logs", False)

    if cl.get("window_size_enabled") and not cl.get("fullscreen"):
        width  = cl.get("window_width",  1280)
        height = cl.get("window_height", 720)
    else:
        width, height = get_primary_monitor()

    log(f"Window: {width}x{height}")

    client_js   = build_client_js(config)
    userscripts = load_userscripts(config.get("scripts", {}))
    swaps       = load_resource_swaps() if cl.get("resource_swapper") else []

    args = [
        f"--app={KRUNKER_URL}",
        f"--window-size={width},{height}",
        "--window-position=0,0",
        "--disable-infobars",
        "--no-first-run",
    ]

    if cl.get("enable_gpu", True):
        args += [
            "--enable-gpu",
            "--ignore-gpu-blocklist",
            "--enable-gpu-rasterization",
        ]

    if cl.get("chrome_flags_enabled") and cl.get("chrome_flags"):
        for flag in cl["chrome_flags"].splitlines():
            flag = flag.strip()
            if flag.startswith("--"):
                args.append(flag)
                if debug: log(f"Chrome flag: {flag}")

    with sync_playwright() as p:
        # Use persistent profile so browser remembers login, settings etc.
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=args,
            viewport={"width": width, "height": height},
            screen={"width": width, "height": height},
        )

        # Only intercept requests if a feature actually needs it
        block_ads = cl.get("block_ads", True)
        do_swap   = bool(swaps)

        if block_ads or do_swap:
            swap_map = {url.lower(): path for url, path in swaps} if do_swap else {}

            def handle_route(route, request):
                try:
                    url = request.url.lower()
                    if do_swap:
                        local = swap_map.get(url)
                        if local:
                            if debug: log(f"Swapped: {request.url}")
                            route.fulfill(path=local)
                            return
                    if block_ads and any(d in url for d in BLOCKED_DOMAINS):
                        route.abort()
                        return
                    route.continue_()
                except Exception:
                    try: route.continue_()
                    except Exception: pass

            context.route("**/*", handle_route)
            if block_ads: log("Ad blocker active")
            if do_swap:   log(f"Resource swapper active ({len(swaps)} swaps)")

        # Override page title to "Velo Client - {krunker title}"
        context.add_init_script("""
(function() {
    const _desc = Object.getOwnPropertyDescriptor(Document.prototype, 'title');
    Object.defineProperty(document, 'title', {
        get() { return _desc.get.call(this); },
        set(val) {
            _desc.set.call(this, val ? 'Velo Client - ' + val : 'Velo Client');
        }
    });
    // Also fix whatever title is already set at document_start
    if (document.title) document.title = document.title;
})();
        """)

        # Register client overlay + userscripts
        context.add_init_script(client_js)
        for name, code in userscripts:
            context.add_init_script(f"(function(){{\n// {name}\n{code}\n}})();")
            log(f"Userscript registered: {name}")

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(KRUNKER_URL, wait_until="domcontentloaded", timeout=30000)
        log("Game loaded")

        if cl.get("fullscreen", True):
            threading.Thread(target=force_fullscreen, daemon=True).start()

        log(f"Ready — press '{cl.get('show_menu_keybind', '`')}' for overlay menu")

        # Wait for page close (user closes the window)
        stop = threading.Event()
        page.on("close", lambda _: stop.set())
        context.on("close", lambda _: stop.set())

        try:
            stop.wait()
        finally:
            save_cookies(context)
            try:
                context.close()
            except Exception:
                pass
            log("Session ended")
if __name__ == "__main__":
    main()