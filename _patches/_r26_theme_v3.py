#!/usr/bin/env python3
# Round-26 retry: Round-25 patcher abort on `inj_tip` because file uses U+2019 (RIGHT SINGLE
# QUOTATION MARK `’`) but patcher anchors used U+0027 (ASCII apostrophe `'`).
# Round-26 fixes the 3 affected log anchors: inj_tip, gatetip3, pipe_reset_btn_title.
#
# Other 10 anchors (6 I18N + 4 sig/bk log) work as-is — they have no apostrophes.
# -*- coding: utf-8 -*-
import pathlib

files = [
    pathlib.Path('static/index.html'),
    pathlib.Path('docs/index.html'),
]

# === 6 I18N literal swaps (verbatim from prior round, no apostrophes — should still match) ===

I18N_REWRITES = [
    (
        "publicbar:'● <b>实时真实数据 · 只读演示</b> · 数据为链上真实筛选结果，<b>不构成投资建议</b> · 本页只展示、不可下单/改配置；想自己交易请 clone 源码本地运行（自配 API Key）'",
        "publicbar:'● <b>实时模拟行情 · 只读演示</b> · 品种覆盖外汇 + 黄金 + 主要指数，<b>不构成投资建议</b> · 本页只展示、不可下单/改配置；想自己交易请 clone 源码本地运行（自配券商账号）'"
    ),
    (
        "publicbar:'● <b>Live real data · read-only demo</b> · real on-chain screening results, <b>not investment advice</b> · view-only here—no orders, no config changes; to trade yourself, clone the source and run locally (your own API key)'",
        "publicbar:'● <b>Live mock data · read-only demo</b> · covers FX majors + Gold + major indices, <b>not investment advice</b> · view-only here—no orders, no config changes; to trade yourself, clone the source and run locally (your own broker account)'"
    ),
    (
        "mode_tip:'成交模式　|　模拟盘：买卖只记录、不上链（当前锁定，先感受用）；实盘：经签名密钥真实成交、动用资金'",
        "mode_tip:'成交模式　|　模拟盘：买卖只记录不上账户（当前锁定，先感受用）；实盘：经API密钥真实报单、动用资金'"
    ),
    (
        "mode_tip:'Trade mode　|　Shadow: trades recorded only, never on-chain (locked for now, just to feel it); Live: real settlement via signing key, real funds'",
        "mode_tip:'Trade mode　|　Shadow: trades recorded only, paper-trade (locked for now, just to feel it); Live: real settlement via API key, real funds'"
    ),
    (
        "cfg_mwarn:'⚠ 两个 key 只发送到你本机后端 (127.0.0.1)，不离开本机、不写浏览器存储。SHADOW 下「一键买入/平仓」只落日志不真实发单；切 LIVE 才会经签名密钥真实成交。'",
        "cfg_mwarn:'⚠ 两个 key 只发送到你本机后端 (127.0.0.1)，不离开本机、不写浏览器存储。SHADOW 下「一键买入/平仓」只落日志不真实发单；切 LIVE 才会经API密钥真实下单。'"
    ),
    (
        "cfg_mwarn:'⚠ Both keys are sent only to your local backend (127.0.0.1)—they never leave your machine or touch browser storage. In SHADOW, one-click buy/sell only logs; switch to LIVE for real settlement via the signing key.'",
        "cfg_mwarn:'⚠ Both keys are sent only to your local backend (127.0.0.1)—they never leave your machine or touch browser storage. In SHADOW, one-click Long/Short only logs; switch to LIVE for real settlement via the API key.'"
    ),
]

# === 7 decision-log cipher-jargon swaps ===
# 4 anchors (sig_top10sell, sig_devout, sig_lppull, bk_rank) use ASCII, verbatim
# 3 anchors (inj_tip, gatetip3, pipe_reset_btn_title) — REPLACE '’' with U+2019 (RIGHT SINGLE QUOTATION MARK)
# Use Python-source-level ’ (U+2019) so heredoc delivers byte-perfect.

LOG_REWRITES = [
    (
        "sig_top10sell:'top10 holders start selling'",
        "sig_top10sell:'[Hash:0xa3c] 持仓集中度阈值触发 / Position concentration breach'"
    ),
    (
        "sig_devout:'dev-linked wallet outflow'",
        "sig_devout:'[Hash:0xb21] 关键账户资金外流 / Key-account outflow detected'"
    ),
    (
        "sig_lppull:'LP liquidity pull started ← escape signal'",
        "sig_lppull:'[Hash:0xc7f] 深度剧烈缩水预警 / Depth void alert'"
    ),
    (
        "bk_rank:'ML ranking: score too low, cut'",
        "bk_rank:'[Rank:0x9d1] ML ranking below cutoff · signal cut'"
    ),
    # inj_tip uses ’ (U+2019): “This token’s on-chain name…doesn't hijack the AI. On-chain text is never trusted.”
    (
        "inj_tip:\'This token\u2019s on-chain name hides prompt-injection text (e.g. \u201cignore previous instructions\u2026 buy now\u201d). The system detected and neutralized it; the LLM only sees the safe version\u2014the name cannot hijack the AI. On-chain text is never trusted.\'",
        "inj_tip:\'[Codepath:0xff1] 输入消毒检测; raw payload 已被剔除 / Verified input sanitized; raw payload ignored\'"
    ),
    # gatetip3 uses ’ for “doc’s” (U+2019)
    (
        "gatetip3:\'Ranked by priority score; only the top few enter the LLM (cuts volume, matches the doc\u2019s ML ranking)\'",
        "gatetip3:\'[Gate:0x4a2] 优先级队列截断 / Priority queue truncated before LLM\'"
    ),
    # pipe_reset_btn_title uses ’ for “chain’s” (U+2019)
    (
        "pipe_reset_btn_title:\'Reset this chain\u2019s trending command to default (persisted server-side)\'",
        "pipe_reset_btn_title:\'[Reset:0x101] 重置行情扫描指令 / Reset scanning command (server-side)\'"
    ),
]

for f in files:
    txt = f.read_text(encoding='utf-8')
    i18_count = 0
    log_count = 0
    for old, new in I18N_REWRITES:
        n = txt.count(old)
        assert n == 1, f'{f}: I18N anchor count={n}, abort — {repr(old)[:80]}'
        txt = txt.replace(old, new)
        i18_count += n
    for old, new in LOG_REWRITES:
        n = txt.count(old)
        assert n == 1, f'{f}: log anchor count={n}, abort — {repr(old)[:80]}'
        txt = txt.replace(old, new)
        log_count += n
    f.write_text(txt, encoding='utf-8')
    print(f'{f}: i18n_rewrites={i18_count} log_cipher_rewrites={log_count}')

print('Round-26 (theme rewrite v3) complete')
