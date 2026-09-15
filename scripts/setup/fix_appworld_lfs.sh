#!/bin/bash
# U1b — fix AppWorld Git LFS pointer stubs, then re-run appworld install/verify and the G2 gate.
# Idempotent: skips any bundle already present, non-pointer, and size-verified.
# Run inside a PBS job only. Never on the login node.
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HOME=/scratch/n12194778/hf
export APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld
PY=/scratch/n12194778/sidekick/env/bin/python
COMMIT=42b5bcf3cd334fee33f0c37c02070a9f5807add5
SRC=/scratch/n12194778/sidekick/env/lib/python3.12/site-packages/appworld/.source
REPO=/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
POINTER_LINE='version https://git-lfs.github.com/spec/v1'

is_pointer() {  # $1 = file ; returns 0 if it's an LFS pointer
  [ -f "$1" ] && [ "$(head -c 200 "$1" | head -n1)" = "$POINTER_LINE" ]
}

fix_one() {  # $1 = bundle name, $2 = expected sha256
  local name=$1 want=$2 f="$SRC/$1" tmp want_size got
  echo "=== $name ==="
  if [ -f "$f" ] && ! is_pointer "$f" && [ "$(stat -c%s "$f")" -gt 1000 ]; then
    got=$(sha256sum "$f" | cut -d' ' -f1)
    if [ "$got" = "$want" ]; then
      echo "$name already fixed and verified ($got). Skipping."
      return 0
    fi
    echo "WARNING: $name is non-pointer, size $(stat -c%s "$f"), but sha256 $got != expected $want. Re-downloading."
  fi
  # Capture oid + size declared by the pointer we are about to replace
  if [ -f "$f" ]; then
    echo "pointer says: $(grep -E '^(oid|size)' "$f" | tr '\n' ' ')"
    want_size=$(grep '^size ' "$f" | head -n1 | awk '{print $2}')
  else
    want_size=""
  fi
  tmp=$(mktemp "${TMPDIR:-/tmp}/$name.XXXXXX")
  url="https://media.githubusercontent.com/media/StonyBrookNLP/appworld/${COMMIT}/src/appworld/.source/${name}"
  echo "downloading $url"
  curl -fsSL --retry 3 -o "$tmp" "$url"
  got=$(sha256sum "$tmp" | cut -d' ' -f1)
  if [ "$got" != "$want" ]; then
    echo "FATAL: checksum mismatch for $name: got $got expected $want — NOT installing."
    rm -f "$tmp"; exit 1
  fi
  if [ -n "$want_size" ]; then
    local gsz
    gsz=$(stat -c%s "$tmp")
    if [ "$gsz" != "$want_size" ]; then
      echo "FATAL: size mismatch for $name: got $gsz expected $want_size — NOT installing."
      rm -f "$tmp"; exit 1
    fi
  fi
  echo "checksum OK: $got"
  mv "$tmp" "$f"
}

fix_one apps.bundle 88d21fc526c1655bb3eee4adfca78ccac793921e4506f28f734ecdb19af77a62
fix_one tests.bundle 7b93343db5efd81b542e68e68150dd5ea5d59d8dcd64137d41bde4027b235dc9

echo "=== scanning for other LFS pointers under installed appworld ==="
APPWORLD_PKG=$(dirname "$SRC")
found=0
while IFS= read -r -d '' f; do
  sz=$(stat -c%s "$f")
  if [ "$sz" -lt 400 ] && head -c 200 "$f" | head -n1 | grep -q '^version https://git-lfs'; then
    echo "LFS POINTER: $f ($sz bytes)"
    oid=$(grep '^oid sha256:' "$f" | head -n1 | awk '{print $3}')
    size_decl=$(grep '^size ' "$f" | head -n1 | awk '{print $2}')
    rel=${f#"$APPWORLD_PKG"/}
    url="https://media.githubusercontent.com/media/StonyBrookNLP/appworld/${COMMIT}/src/appworld/${rel}"
    tmp=$(mktemp "${TMPDIR:-/tmp}/lfs.XXXXXX")
    if curl -fsSL --retry 3 -o "$tmp" "$url" \
       && [ "$(sha256sum "$tmp" | cut -d' ' -f1)" = "$oid" ] \
       && [ "$(stat -c%s "$tmp")" = "$size_decl" ]; then
      mv "$tmp" "$f"; echo "  fixed + verified: $rel"
    else
      rm -f "$tmp"; echo "  FAILED to verify $rel — leaving pointer in place"; found=1
    fi
  fi
done < <(find "$APPWORLD_PKG" -type f -size -400c -print0)
[ "$found" -eq 0 ] && echo "no unfixable LFS pointers remain" || echo "WARNING: some pointers unresolved"

export PATH="/scratch/n12194778/sidekick/env/bin:${PATH}"

echo "=== appworld install ==="
appworld install
echo "=== appworld download data ==="
appworld download data --root "$APPWORLD_ROOT"
echo "=== appworld verify tasks ==="
appworld verify tasks --root "$APPWORLD_ROOT"

echo "=== running G2 gate ==="
cd "$REPO"
"$PY" scripts/setup/g2_appworld_gate.py
