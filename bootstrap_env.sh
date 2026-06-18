#!/usr/bin/env bash
# bootstrap_env.sh — F:\\yujin-mt5\\ 凭据 守门员 v2
#
# 流程 (凭 据 不  ·  ·  · 不  echo value):
#   1. 读 KEY.txt (本地 · 仅 本机 读)
#   2. parse KEY=value → .env.tmp · 原子 改名
#   3. 验证 4 个 必须 KEY (MT5_LOGIN/PASSWORD/SERVER/PATH) 都在  ·  缺 1 hard-fail
#   4. chmod 600 .env   // 仅 本地 用户 读写
#   5. cleanup 旧 .env.bak.<ts> ·  保 留 最 近 5 个
#
# 凭据 不 echo · 不 写 log ·  仅  打印  KEY count & bucket size
set -euo pipefail

YELLOW='\033[1;33m'; RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'
KEY_FILE="${1:-KEY.txt}"
ENV_FILE=".env"
TMP_FILE=".env.tmp"
REQUIRED=(MT5_LOGIN MT5_PASSWORD MT5_SERVER MT5_PATH)

# --- preflight ---
echo -e "${YELLOW}:: preflight${NC}"
[[ -f "$KEY_FILE" ]] || { echo -e "${RED}FAIL: $KEY_FILE 不存在${NC}" >&2; exit 1; }
[[ ! -w "$ENV_FILE" ]] && [[ ! -e "$ENV_FILE" ]] && : || true
KEY_SIZE=$(wc -c < "$KEY_FILE")
[[ "$KEY_SIZE" -lt 10 ]] && { echo -e "${RED}FAIL: $KEY_FILE 太小 ($KEY_SIZE bytes)${NC}" >&2; exit 2; }
echo "  KEY_FILE: $KEY_FILE  ($KEY_SIZE bytes)"

# --- backup existing .env ---
if [[ -f "$ENV_FILE" ]]; then
  BAK=".env.bak.$(date +%s)"
  cp "$ENV_FILE" "$BAK"
  echo "  backup: $BAK"
fi

# --- atomic write ---
echo -e "${YELLOW}:: parse + write${NC}"
: > "$TMP_FILE"
COUNT=0
# 走 KEY=value 格式 ( · 1 行 1 条)
while IFS='=' read -r k v; do
  [[ -z "$k" || "$k" =~ ^# ]] && continue
  if [[ "$k" =~ ^[A-Z_][A-Z0-9_]*$ ]]; then
    # 不 echo "$v" · 仅写文件
    printf '%s=%s\n' "$k" "$v" >> "$TMP_FILE"
    COUNT=$((COUNT + 1))
  fi
done < "$KEY_FILE"

#  3 行格式 fallback (login/password/server 各 1 行)
if [[ "$COUNT" -eq 0 ]]; then
  echo "  走 3 行格式 fallback ..."
  i=1
  while IFS= read -r raw; do
    [[ -z "$raw" ]] && continue
    case "$i" in
      1) printf 'MT5_LOGIN=%s\n'    "$raw" >> "$TMP_FILE" ;;
      2) printf 'MT5_PASSWORD=%s\n' "$raw" >> "$TMP_FILE" ;;
      3) printf 'MT5_SERVER=%s\n'   "$raw" >> "$TMP_FILE" ;;
    esac
    i=$((i + 1))
  done < "$KEY_FILE"
  COUNT=3
fi

# --- required KEY 验证 ---
echo -e "${YELLOW}:: required KEY 验证${NC}"
MISSING=()
for k in "${REQUIRED[@]}"; do
  grep -q "^${k}=" "$TMP_FILE" || MISSING+=("$k")
done
if [[ "${#MISSING[@]}" -gt 0 ]]; then
  echo -e "${RED}FAIL: 缺 KEY: ${MISSING[*]}${NC}" >&2
  rm -f "$TMP_FILE"
  exit 3
fi

mv "$TMP_FILE" "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo -e "${GREEN}OK: .env 写入 ($COUNT lines · chmod 600)${NC}"
for k in "${REQUIRED[@]}"; do
  SIZE=$(grep "^${k}=" "$ENV_FILE" | cut -d'=' -f2- | wc -c)
  echo "    $k -> <${SIZE} bytes>"
done

# --- cleanup 旧 backups · 保 留 最近 5 个 ---
echo -e "${YELLOW}:: cleanup old backups${NC}"
COUNT_BAK=$(ls -1t .env.bak.* 2>/dev/null | wc -l)
if [[ "$COUNT_BAK" -gt 5 ]]; then
  ls -1t .env.bak.* | tail -n +6 | xargs -r rm -f
  echo "  删 $(($COUNT_BAK - 5)) 旧 backup · 留 5"
fi
