import pathlib, re

p = pathlib.Path('F:/yujin-mt5/static/index.html')
html = p.read_text('utf-8')

# ── I18N Dictionary ──
I18N_JS = r"""
var I18N = {
  zh: {
    banner: 'DEMO MODE / SHADOW / 模拟数据',
    mt5sim: 'MT5 模拟',
    scanned: '累计扫描', safety: '过避雷门', confluence: '过共振门',
    pending: '待决策', positions: '持仓', escape: '逃生预警',
    pipeline: '筛选流水线', symbols: '品种',
    colSym: '品种', colSafety: '避雷', colConfl: '共振',
    colStruct: '结构', colTiming: '节奏', colCtx: '上下文',
    colRisk: '风控', colSpread: '点差', colPrio: '优先级',
    colDecision: '决策',
    log: '实时决策日志', logLast: '最近 20 条',
    posMon: '持仓云控监', gateFunnel: '闸门漏斗',
    riskSt: '风控状态', concurrent: '并发持仓',
    exposure: '总敢口', dailyLoss: '当日亏损', consec: '连亏',
    close: '立即平仓', ok: 'OK',
    m1title: 'MT5 凭据配置', m1login: '登录号', m1pwd: '密码',
    m1server: '服务器', m1path: 'MT5 路径',
    m2title: '筛选设置', m2spread: '最大点差',
    m2ema: 'EMA 快/慢', m2fvg: 'FVG 回溯', m2atr: 'ATR 倍数',
    m3title: '一键买入', m3lots: '手数',
    m3sl: '止损', m3tp: '止盈', m3thesis: '理由',
    m4title: '确认操作',
    cancel: '取消', connect: '连接', save: '保存',
    confirmShadow: '确认 (SHADOW)', confirm: '确认',
    modeLive: '切换到 LIVE',
    modeWarn: 'LIVE 模式将使用真实资金下单，确认切换？',
    action: 'ACTION', watch: 'WATCH', reject: 'REJECT',
    screen: 'SCREEN', filter: 'FILTER', buy: 'BUY', sell: 'SELL',
  },
  en: {
    banner: 'DEMO MODE / SHADOW / simulated data',
    mt5sim: 'MT5 Sim',
    scanned: 'Scanned', safety: 'Safety', confluence: 'Confluence',
    pending: 'Pending', positions: 'Positions', escape: 'Escape',
    pipeline: 'Screening Pipeline', symbols: 'symbols',
    colSym: 'Symbol', colSafety: 'Safety', colConfl: 'Confl',
    colStruct: 'Struct', colTiming: 'Timing', colCtx: 'Ctx',
    colRisk: 'Risk', colSpread: 'Spread', colPrio: 'Priority',
    colDecision: 'Decision',
    log: 'Decision Log', logLast: 'last 20',
    posMon: 'Position Monitor', gateFunnel: 'Gate Funnel',
    riskSt: 'Risk Status', concurrent: 'Concurrent',
    exposure: 'Exposure', dailyLoss: 'Daily Loss', consec: 'Consec',
    close: 'Close', ok: 'OK',
    m1title: 'MT5 Credentials', m1login: 'Login', m1pwd: 'Password',
    m1server: 'Server', m1path: 'MT5 Path',
    m2title: 'Scan Settings', m2spread: 'Max Spread',
    m2ema: 'EMA Fast/Slow', m2fvg: 'FVG Lookback', m2atr: 'ATR Multiplier',
    m3title: 'Buy Order', m3lots: 'Lots',
    m3sl: 'Stop Loss', m3tp: 'Take Profit', m3thesis: 'Thesis',
    m4title: 'Confirm',
    cancel: 'Cancel', connect: 'Connect', save: 'Save',
    confirmShadow: 'Confirm (SHADOW)', confirm: 'Confirm',
    modeLive: 'Switch to LIVE',
    modeWarn: 'LIVE mode uses real money. Confirm?',
    action: 'ACTION', watch: 'WATCH', reject: 'REJECT',
    screen: 'SCREEN', filter: 'FILTER', buy: 'BUY', sell: 'SELL',
  }
};
var curLang = localStorage.getItem('yjLang') || 'zh';
function t(k){ return I18N[curLang][k] || k; }
function toggleLang(){ curLang = curLang==='zh'?'en':'zh'; localStorage.setItem('yjLang',curLang); applyTranslations(); document.getElementById('langBtn').textContent = curLang==='zh'?'EN':'中'; document.documentElement.lang = curLang==='zh'?'zh-CN':'en'; }
function applyTranslations(){
  document.querySelectorAll('[data-i18n]').forEach(function(el){ el.textContent = t(el.getAttribute('data-i18n')); });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el){ el.placeholder = t(el.getAttribute('data-i18n-placeholder')); });
  renderTable(); renderLog();
}
"""

# Insert I18N right before the existing var SYM= line
html = html.replace('var SYM=[', I18N_JS + '\nvar SYM=[')

print(f'I18N dictionary injected: {len(html)} chars')
p.write_text(html, 'utf-8')

# ── Add data-i18n to HTML elements ──
# Banner
html = html.replace('<div class="dbanner">DEMO MODE / SHADOW / simulated data</div>',
                     '<div class="dbanner" data-i18n="banner">DEMO MODE / SHADOW / simulated data</div>')
# MT5 status
html = html.replace('<div class="sbdg on"><span class="dt"></span><span>MT5 Sim</span></div>',
                     '<div class="sbdg on"><span class="dt"></span><span data-i18n="mt5sim">MT5 Sim</span></div>')
# KPI labels
for k,v in [('scanned','Scanned'),('safety','Safety'),('confluence','Confluence'),
            ('pending','Pending'),('positions','Positions'),('escape','Escape')]:
    html = html.replace(f'<span class="kl">{v}</span>',
                         f'<span class="kl" data-i18n="{k}">{v}</span>')
# Pipeline header
html = html.replace('<h3>Screening Pipeline</h3>', '<h3 data-i18n="pipeline">Screening Pipeline</h3>')
# Table headers
for k,v in [('colSym','Symbol'),('colSafety','Safety'),('colConfl','Confl'),('colStruct','Struct'),
            ('colTiming','Timing'),('colCtx','Ctx'),('colRisk','Risk'),('colSpread','Spread'),
            ('colPrio','Priority'),('colDecision','Decision')]:
    html = html.replace(f'<th>{v}</th>', f'<th data-i18n="{k}">{v}</th>')
# Log header
html = html.replace('<h3>Decision Log</h3>', '<h3 data-i18n="log">Decision Log</h3>')
# Position Monitor
html = html.replace('<h3>Position Monitor</h3>', '<h3 data-i18n="posMon">Position Monitor</h3>')
# Gate Funnel
html = html.replace('<h3>Gate Funnel</h3>', '<h3 data-i18n="gateFunnel">Gate Funnel</h3>')
# Risk Status
html = html.replace('<h3>Risk Status</h3>', '<h3 data-i18n="riskSt">Risk Status</h3>')
for k,v in [('concurrent','Concurrent'),('exposure','Exposure'),('dailyLoss','Daily Loss'),('consec','Consec')]:
    html = html.replace(f'<div class="rl">{v}</div>', f'<div class="rl" data-i18n="{k}">{v}</div>')
# Modal titles and labels
mappings = [
    ('m1title','MT5 Credentials'),('m1login','Login'),('m1pwd','Password'),
    ('m1server','Server'),('m1path','MT5 Path'),
    ('m2title','Scan Settings'),('m2spread','Max Spread'),('m2ema','EMA Fast/Slow'),
    ('m2fvg','FVG Lookback'),('m2atr','ATR Multiplier'),
    ('m3title','Buy Order'),('m3lots','Lots'),('m3sl','Stop Loss'),('m3tp','Take Profit'),('m3thesis','Thesis'),
    ('cancel','Cancel'),('connect','Connect'),('save','Save'),
    ('confirmShadow','Confirm (SHADOW)'),('confirm','Confirm'),
]
for k,v in mappings:
    html = html.replace(f'"{v}"', f'"{v}"')  # no-op placeholder, actual replacement below

# Modal h3 titles
html = html.replace('<h3>MT5 Credentials</h3>', '<h3 data-i18n="m1title">MT5 Credentials</h3>')
html = html.replace('<h3>Scan Settings</h3>', '<h3 data-i18n="m2title">Scan Settings</h3>')
html = html.replace('<h3>Buy Order</h3>', '<h3 data-i18n="m3title">Buy Order</h3>')

# Modal labels
for k,v in [('m1login','Login'),('m1pwd','Password'),('m1server','Server'),('m1path','MT5 Path'),
            ('m2spread','Max Spread'),('m2ema','EMA Fast/Slow'),('m2fvg','FVG Lookback'),('m2atr','ATR Multiplier'),
            ('m3lots','Lots'),('m3sl','Stop Loss'),('m3tp','Take Profit'),('m3thesis','Thesis')]:
    html = html.replace(f'<label>{v}</label>', f'<label data-i18n="{k}">{v}</label>')

# Button text in modals
html = html.replace('>Cancel</button>', ' data-i18n="cancel">Cancel</button>')
html = html.replace('>Connect</button>', ' data-i18n="connect">Connect</button>')
html = html.replace('>Save</button>', ' data-i18n="save">Save</button>')
html = html.replace('>Confirm (SHADOW)</button>', ' data-i18n="confirmShadow">Confirm (SHADOW)</button>')
html = html.replace('>Confirm</button>', ' data-i18n="confirm">Confirm</button>')

# Position close button
html = html.replace('>Close</button>', ' data-i18n="close">Close</button>')

print(f'HTML data-i18n attributes added: {len(html)} chars')
p.write_text(html, 'utf-8')

# ── Add language toggle button to topbar (before gearBtn) ──
lang_btn = '<button class="gbtn" id="langBtn" onclick="toggleLang()" style="font-size:12px;">EN</button>'
html = html.replace('<button class="gbtn" id="gearBtn"', lang_btn + '\n  <button class="gbtn" id="gearBtn"')

# ── Update JS: replace hardcoded strings in renderTable with t() calls ──
# Replace ACTION/WATCH/REJECT labels
html = html.replace("'ACTION':d.st==='watch'?'WATCH':'REJECT'",
                    "t('action'):d.st==='watch'?t('watch'):t('reject')")
# Replace hardcoded log action labels
html = html.replace("'SCREEN',fi:'FILTER',by:'BUY',se:'SELL'}",
                    "t('screen'),fi:t('filter'),by:t('buy'),se:t('sell')}")
# Replace CL category labels with t()-compatible short names (keep as-is, they are technical)
# Replace mode switch text
html = html.replace("document.getElementById('scnt').textContent='23 symbols / '+cm",
                    "document.getElementById('scnt').textContent='23 '+t('symbols')+' / '+cm")

# ── Call applyTranslations() at the end (replace init calls) ──
html = html.replace('renderTable();renderPos();renderFunnel();renderLog();',
                    'applyTranslations();renderPos();renderFunnel();')

print(f'Part 3 applied: {len(html)} chars')
p.write_text(html, 'utf-8')

print('All transformations complete!')
