# _patches/ · ad-hoc round patchers (r8-r29)

`/patches/_r##_name.py` and `_r##_ship.sh` are the byte-exact patch scripts that
produced each round's commit. They live here so the diffs are reproducible from
git alone — no more workspace-root drift between ad-hoc script and shipped state.

## Round index (recent, in CHANGELOG of /README.md for prose)
- r29: `_r29_anticache_meta.py` + `_r29_ship.sh` (anti-cache meta, cursor meta, version bump)
- r28: `_r28_chain_to_forex.py` (CHAIN SOL → FOREX, 23 anchors)
- r27: `_r27_livelog_cipher.py` + `_r27_bytecheck.py` + `_r27_diag.py` + `_r27_verify.py`
- r26: `_r26_theme_v3.py` (Live cipher decision-log static I18N)
- r25: `_r25_theme_v2.py`
- r24: `_r24_theme_rewrite.py` (SOL/crypto → MT5 forex+indices)
- r23: `_r23_step2_replacetag.py`
- r22: `_r22_killphrase.py`
- r21: `_r21_killtagline.py`
- r20: `_r20_tagappend.py`
- r19: `_r19_fullmatch.py`
- r18: `_r18_phrasereplace.py`
- r17: `_r17_restyle.py`
- r15: `_r15_demobar_linkreplace.py`
- r11: `_r11_demobar_v3.py`
- r10: `_r10_demobar_v2.py`, `_r10_demobar_restore.py`
- r8:  `_r8_patch.py`

Note: scripts in this directory are tracked but **are not part of the runtime**.
The deploy-pages workflow ignores `_patches/` (deploy root is `docs/`).
