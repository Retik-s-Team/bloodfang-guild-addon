#!/bin/sh
# Fails if guild names, domains or other branding appear in tracked source. Two lists:
# - the names the packaging config gives the shipped build (product, executable and publisher names in
#   tauri.conf.json, the host in site.url). Code and tests read these from the config, so no other file
#   may spell them. This part needs no secret, so it also runs locally and on fork PRs.
# - the words in the BRANDING_WORDS env var (repo secret in CI), so this file doesn't name them either.
set -eu
cd "$(git rev-parse --show-toplevel)"
# Only the branding and packaging files may name the guild:
# uploader/app/site.url is the deployment address for the desktop build, not logic.
# The desktop product name and publisher live in the packaging config and the window heading.
sources() {
  git ls-files | grep -v -e '^addon/Libs/' -e '^LICENSE$' -e '^uploader/app/site.url$' \
    -e '^uploader/app/src-tauri/tauri.conf.json$' -e '^uploader/app/ui/index.html$'
}
found=0
names=$(python3 - uploader/app/src-tauri/tauri.conf.json uploader/app/site.url <<'EOF'
import json, sys, urllib.parse
conf = json.load(open(sys.argv[1], encoding="utf-8"))
names = [conf.get("productName"), conf.get("mainBinaryName"), conf.get("bundle", {}).get("publisher")]
try:
    names.append(urllib.parse.urlsplit(open(sys.argv[2], encoding="utf-8").read().strip()).hostname)
except OSError:
    pass
print("\n".join(sorted({n for n in names if n})))
EOF
)
if [ -n "$names" ] && sources | xargs grep -I -n -i -F -e "$names"; then
  echo "a name from the packaging config is spelled outside it; read it from tauri.conf.json or site.url"; found=1
fi
if [ -n "${BRANDING_WORDS:-}" ]; then
  pat=$(printf '%s' "$BRANDING_WORDS" | tr ',' '|')
  if sources | xargs grep -I -n -i -E "$pat"; then echo "branding found"; found=1; fi
else
  echo "BRANDING_WORDS not set; checked only the names from the packaging config"
fi
[ "$found" = 0 ] || exit 1
echo "no branding"
