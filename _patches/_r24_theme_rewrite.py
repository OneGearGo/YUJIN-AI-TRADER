#!/usr/bin/env python3
# Round-24: rewrite the public page from SOL/crypto theme to MT5 forex + indices theme.
# Scope (per user's spec "整个页面的内容需要重新更换内容"):
#   - 23 demo-token short names (BTC, ETH, SOL, ...)
#   - 23 corresponding display names ("Bitcoin", "Ethereum", ...)
#   - I18N.zh.publicbar / I18N.en.publicbar text (drop 链上 ref, list forex+metal+indices)
#   - I18N.zh.mode_tip / I18N.en.mode_tip text (drop 上链, use 不上账户)
#   - I18N.zh.cfg_mwarn / I18N.en.cfg_mwarn text (cosmetic-aligned to forex)
# Decide log-template 加密 jargon replacement OFF of this round — user wants iterative control.
#
# Per user's earlier rule: NO styling / color changes; ONLY the literal text.
# NO touch to: demobar (user already customized), assets CSS, controls, layout, charts.
# Symbol short names: only swap `sym:'<OLD>'` → `sym:'<NEW>'` (precise, avoids body-text matches).
# -*- coding: utf-8 -*-
import pathlib

files = [
    pathlib.Path('static/index.html'),
    pathlib.Path('docs/index.html'),
]

SYM_MAP = {
    'BTC':'EURUSD','ETH':'GBPJPY','SOL':'USDJPY','PEPE':'XAUUSD',
    'BONK':'US30','WIF':'NAS100','JUP':'SPX500','PYTH':'USDCHF',
    'RNDR':'AUDUSD','GMT':'NZDUSD','AKT':'USDCAD','ANKR':'EURJPY',
    'AUDIO':'EURGBP','AVAX':'GBPCHF','ICP':'AUDNZD','JTO':'XAGUSD',
    'MOBILE':'DE40','ONDO':'UK100','ORCA':'JP225','PRCL':'BTCUSD',
    'RAY':'ETHUSD','SRM':'WTI','TIA':'BRENT',
}

NAME_MAP = {
    "'Bitcoin'":"'Euro vs US Dollar'",
    "'Ethereum'":"'British Pound vs Japanese Yen'",
    "'Solana'":"'US Dollar vs Japanese Yen'",
    "'Pepe'":"'Gold vs US Dollar'",
    "'Bonk'":"'Wall Street 30 (DJIA)'",
    "'dogwifhat'":"'Nasdaq 100'",
    "'Jupiter'":"'S&P 500'",
    "'Pyth Network'":"'US Dollar vs Swiss Franc'",
    "'Render Token'":"'Australian Dollar vs US Dollar'",
    "'STEPN'":"'New Zealand Dollar vs US Dollar'",
    "'Akash Network'":"'US Dollar vs Canadian Dollar'",
    "'Ankr Network'":"'Euro vs Japanese Yen'",
    "'Ankr'":"'Euro vs Japanese Yen'",
    "'Audius'":"'Euro vs British Pound'",
    "'Avalanche'":"'British Pound vs Swiss Franc'",
    "'Internet Computer'":"'Australian Dollar vs NZ Dollar'",
    "'Jito'":"'Silver vs US Dollar'",
    "'MobileCoin'":"'Germany 40 (DAX)'",
    "'Ondo Finance'":"'UK 100 (FTSE)'",
    "'Ondo'":"'UK 100 (FTSE)'",
    "'Orca'":"'Japan 225 (Nikkei)'",
    "'Parcl'":"'Bitcoin vs US Dollar'",
    "'Raydium'":"'Ethereum vs US Dollar'",
    "'Serum'":"'WTI Crude Oil'",
    "'Celestia'":"'Brent Crude Oil'",
}

THEME_REPLACES = [
    # publicbar I18N.zh (around line 398)
    (
        "publicbar:'● <b>实时真实数据 · 只读演示</b> · 数据为链上真实筛选结果，<b>不构成投资建议</b> · 本页只展示、不可下单/改配置；想自己交易请 clone 源码本地运行（自配 API Key）'",
        "publicbar:'● <b>实时模拟行情 · 只读演示</b> · 品种覆盖外汇主要货币对 + 黄金 + 主要指数，<b>不构成投资建议</b> · 本页只展示、不可下单/改配置；想自己交易请 clone 源码本地运行(自配券商账号)'"
    ),
    # publicbar I18N.en (around line 542)
    (
        'publicbar:\'● <b>Live real data · read-only demo</b> · data is real on-chain screener output, <b>not investment advice</b> · for live trading, clone and run locally with your own API key\'',
        'publicbar:\'● <b>Live mock data · read-only demo</b> · covers FX majors + Gold + major indices, <b>not investment advice</b> · for live trading, clone and run locally with your own broker account\''
    ),
    # mode_tip I18N.zh (around line 405)
    (
        "mode_tip:'成交模式　|　模拟盘：买卖只记录、不上链（当前锁定，先感受用）；实盘：经签名密钥真实成交、动用资金'",
        "mode_tip:'成交模式　|　模拟盘：买卖只记录不上账户（当前锁定，先感受用）；实盘：经签名密钥真实成交、动用资金'"
    ),
    # mode_tip I18N.en
    (
        "mode_tip:'Trade mode　|　Shadow: trades recorded only, never on-chain (locked for now, just to feel it); Live: real settlement via signing key, real funds'",
        "mode_tip:'Trade mode　|　Shadow: trades recorded only, no account posting (locked for now, just to feel it); Live: real settlement via signing key, real funds'"
    ),
    # cfg_mwarn I18N.zh
    (
        "cfg_mwarn:'⚠ Both keys are sent only to your local backend (127.0.0.1)—they never leave your machine or touch browser storage. In SHADOW, one-click buy/sell only logs; switch to LIVE for real settlement via the signing key.'",
        "cfg_mwarn:'⚠ Both keys are sent only to your local backend (127.0.0.1)—they never leave your machine or touch browser storage. In SHADOW, one-click Long/Short only logs; switch to LIVE for real settlement via the signing key.'"
    ),
    # cfg_mwarn I18N.en
    (
        'cfg_mwarn:\'⚠ Both keys are sent only to your local backend (127.0.0.1)—they never leave your machine or touch browser storage. In SHADOW, one-click buy/sell only logs; switch to LIVE for real settlement via the signing key.\'',
        'cfg_mwarn:\'⚠ Both keys are sent only to your local backend (127.0.0.1)—they never leave your machine or touch browser storage. In SHADOW, one-click Long/Short only logs; switch to LIVE for real settlement via the signing key.\''
    ),
]

for f in files:
    txt = f.read_text(encoding='utf-8')

    sym_total = 0
    for old, new in SYM_MAP.items():
        before = txt.count(f"sym:'{old}'")
        txt = txt.replace(f"sym:'{old}'", f"sym:'{new}'")
        sym_total += before

    name_total = 0
    for old, new in NAME_MAP.items():
        before = txt.count(old)
        if before:
            txt = txt.replace(old, new)
            name_total += before

    theme_total = 0
    for old, new in THEME_REPLACES:
        before = txt.count(old)
        assert before == 1, f'{f}: theme anchor count={before}, abort — {old[:60]}'
        txt = txt.replace(old, new)
        theme_total += before

    f.write_text(txt, encoding='utf-8')
    print(f'{f}: sym_swaps={sym_total} name_swaps={name_total} theme_swaps={theme_total}')

print('Round-24 theme rewrite complete')
