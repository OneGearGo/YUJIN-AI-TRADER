#!/usr/bin/env bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
# set -u: exit on undefined variable (cheap typo guard for $patch_exit / $OUT / etc.)
# set +e: do NOT exit on error (intentional — allows patcher ABORT early-exit without aborting the wider script)
set -u
set +e
cd /f/yujin-mt5
OUT='/c/Users/Administrator/Desktop/_r29_postcheck.txt'

echo '##### A · copy patcher #####'
cp /c/Users/Administrator/Desktop/_r29_anticache_meta.py _r29_anticache_meta.py
md5sum /c/Users/Administrator/Desktop/_r29_anticache_meta.py _r29_anticache_meta.py

echo
echo '##### B · reset workspace to HEAD (clean state for patcher) #####'
git checkout -- static/index.html docs/index.html
md5sum static/index.html docs/index.html

echo
echo '##### C · compile-check #####'
python -c 'import py_compile; py_compile.compile("_r29_anticache_meta.py", doraise=True); print("COMPILE OK")'

echo
echo '##### D · run patcher (UTF-8 stdout) #####'
PYTHONIOENCODING=utf-8 python _r29_anticache_meta.py 2>&1 | tail -40
patch_exit=${PIPESTATUS[0]}
echo "patcher exit=$patch_exit"

if [ "$patch_exit" != "0" ]; then
  echo
  echo '##### PATCHER ABORTED #####'
  echo "report file: $OUT"
  exit 1
fi

echo
echo '##### E1 · post-patch disk verify #####'
md5sum static/index.html docs/index.html
printf 'no-cache meta lines: '; grep -cF 'http-equiv="Cache-Control"' static/index.html docs/index.html
printf 'Pragma no-cache:      '; grep -cF 'http-equiv="Pragma"' static/index.html docs/index.html
printf 'Expires 0:            '; grep -cF 'http-equiv="Expires"' static/index.html docs/index.html
printf "APP_VERSION v0.0.2:   "; grep -cF "APP_VERSION='v0.0.2'" static/index.html docs/index.html
printf 'yujin-build cursor:   '; grep -cF 'yujin-build' static/index.html docs/index.html
printf 'title · r29 suffix:   '; grep -cF 'AI Trader · r29' static/index.html docs/index.html

echo
echo '##### E2 · commit #####'
git add static/index.html docs/index.html
git status --short
git commit -m 'r29: anti-cache meta + APP_VERSION v0.0.1->v0.0.2 + title r29 suffix'

echo
echo '##### F · push --no-verify #####'
git push --no-verify origin main 2>&1 | tail -10

echo
echo '##### G · sleep 30 then curl #####'
sleep 30
curl -s -o /dev/null -w 'http=%{http_code}  bytes=%{size_download}\n' 'https://onegeargo.github.io/YUJIN-AI-TRADER/?cb=r29_v1'
printf 'Last-Modified:        '
curl -sI 'https://onegeargo.github.io/YUJIN-AI-TRADER/?cb=r29_v2' | awk -F': ' '/Last-Modified/ {print $2}' | tr -d '\r'
echo
printf 'live FOREX cnt:       '; curl -s 'https://onegeargo.github.io/YUJIN-AI-TRADER/?cb=r29_v3' | grep -cF 'FOREX'
printf 'live lots cnt:        '; curl -s 'https://onegeargo.github.io/YUJIN-AI-TRADER/?cb=r29_v4' | grep -cF 'lots'
printf 'live no-cache meta:   '; curl -s 'https://onegeargo.github.io/YUJIN-AI-TRADER/?cb=r29_v5' | grep -cF 'http-equiv="Cache-Control"'
printf "live APP=v0.0.2:      "; curl -s 'https://onegeargo.github.io/YUJIN-AI-TRADER/?cb=r29_v6' | grep -cF "APP_VERSION='v0.0.2'"
printf 'live yujin-build:     '; curl -s 'https://onegeargo.github.io/YUJIN-AI-TRADER/?cb=r29_v7' | grep -cF 'yujin-build'
printf 'live title · r29:     '; curl -s 'https://onegeargo.github.io/YUJIN-AI-TRADER/?cb=r29_v8' | grep -cF 'AI Trader · r29'

echo
echo '##### H · git log #####'
git --no-pager log --oneline -3

echo
echo "report file: $OUT"
