"""Golden export strings for contract/golden/strings (contract/SPEC.md section 7).

The Lua 5.1 run (the game's runtime) writes the .txt strings. The LuaJIT run must decode to the same JSON.
Every string is also decoded and its HMAC checked here, in Python, independently of the Lua code, from the
rules in contract/SPEC.md section 2. Files under contract/golden are add-only: see contract/golden/README.md.
"""
import hashlib, hmac, json, os, re, zlib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "contract", "golden")
ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789()"
TYPES = {"link": [1, 2], "gbank": [1], "recipes": [1], "ranks": [1]}
# Golden export strings: (file name base, version). The file is strings/<base>.v<version>.txt.
STRINGS = [("link", 1), ("gbank", 1), ("gbank.no-guild", 1), ("recipes", 1), ("ranks", 1), ("link", 2)]

# ---------- link v2 (contract/SPEC.md 3.3.2), written from the SPEC, independently of the Lua code ----------
LINK_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LINK_SALT = b"BF-LINK-V2"
LINK_TEST_CODE = "0123456789ABCDEFGHJKMNPQRS"
# Inputs typed after `<cmd> link`, and the code each normalizes to (None: refused with the usage line).
LINK_INPUTS = [
    "0123456789ABCDEFGHJKMNPQRS", "0123456789abcdefghjkmnpqrs", "01234-56789-ABCDE-FGHJK-MNPQR-S",
    " 01234 56789 ABCDE FGHJK MNPQR S ", "oI23456789ABCDEFGHJKMNPQRS", "OL23456789abcdefghjkmnpqrs",
    "0123456789ABCDEFGHJKMNPQR", "0123456789ABCDEFGHJKMNPQRST", "U123456789ABCDEFGHJKMNPQRS",
    "0123456789ABCDEFGHJKMNPQR!", "0123456789ABCDEFGHJKMNPQR\u00e9",
]


def link_code(s):
    """SPEC 3.3.2 normalization: the v2 code, or None."""
    s = re.sub(r"[\t\n\v\f\r -]", "", s)
    if not re.fullmatch(r"[0-9A-Za-z]*", s, re.ASCII):
        return None
    s = s.upper().replace("O", "0").replace("I", "1").replace("L", "1")
    return s if len(s) == 26 and all(c in LINK_ALPHABET for c in s) else None


def hkdf(salt, ikm, info, length):
    """RFC 5869 HKDF-SHA256. Returns (PRK, OKM)."""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    t, okm, i = b"", b"", 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm, i = okm + t, i + 1
    return prk, okm[:length]


def link_keys(code, guid, n):
    """SPEC 3.3.2: (PRK hex, lookup hex, secret hex) for a normalized code, a character GUID and the nonce `n`."""
    prk, lookup = hkdf(LINK_SALT, code.encode(), b"lookup", 16)
    _, secret = hkdf(LINK_SALT, code.encode(), f"secret:{guid}:{n}".encode(), 32)
    return prk.hex(), lookup.hex(), secret.hex()


def sig_ok(env, secret_hex):
    body = {k: x for k, x in env.items() if k != "sig"}
    want = hmac.new(bytes.fromhex(secret_hex), canonical(body).encode(), hashlib.sha256).hexdigest()
    return env.get("sig") == want
UPLOADER_PROTOCOL = 1

GEN = r'''function(ns)
  E2E_SEED(20261113)
  E2E_IN_GUILD = true
  GuildaddonDB.guild = nil
  GuildaddonDB.outbox = {}
  ns.captureRanks()
  local out = {}
  local tabs = { { tab = 1, name = "Mats: \"ore\"", slots = {
      { link = "|cffffffff|Hitem:2771::::::::60:::::|h[Tin Ore]|h|r", count = 20, texture = 135 },
      { link = "|Hitem:2771::|h", count = 5 }, { link = "|Hitem:13444::|h", count = 1 } } },
    { tab = 2, name = "Épées", slots = {} } }
  local p = ns.bankPayload(tabs, 1234567, function(id) return 100000 + id end)
  out["gbank"] = ns.export("gbank", p)
  out["recipes"] = ns.export("recipes", { profession = "Alchemy", skill = 300,
    recipes = ns.recipeIds({ "|Henchant:17187|h", "spell:3170" }) })
  out["ranks"] = GuildaddonDB.outbox.ranks.s
  E2E_IN_GUILD = false
  out["gbank.no-guild"] = ns.export("gbank", p)
  E2E_IN_GUILD = true
  local copied, showCopy = nil, ns.showCopy
  ns.showCopy = function(_, text) copied = text end
  local key = next(SlashCmdList)
  SlashCmdList[key]("link ABCD2345")
  ns.showCopy = showCopy
  out["link"] = copied
  -- bad-sig: a recipes string whose envelope changed after signing.
  local _, _, j = ns.decodeString(out["recipes"])
  j.addon = "0.0.0-tampered"
  out["bad/bad-sig"] = ns.encodeString("recipes", 1, j, nil)
  out["canonical"] = ns.jsonEncode({ z = 1, n = -42, big = 9007199254740991, yes = true, no = false,
    s = { "Épées", "tab\tnew\nline", "quote\"back\\slash", "ctl\1" } })
  -- link v2 (SPEC 3.3): the string for the fixed test code, the secret the addon kept, and a tampered copy.
  E2E_SEED(20261121)
  local before = GuildaddonDB.chars[E2E_GUID]
  ns.showCopy = function(_, text) copied = text end
  copied = nil
  SlashCmdList[key]("link " .. E2E_LINK_CODE)
  out["link.v2"] = copied
  out["link.v2.secret"] = GuildaddonDB.chars[E2E_GUID] and GuildaddonDB.chars[E2E_GUID].secret
  for i, s in ipairs(E2E_LINK_INPUTS) do out["norm." .. i] = ns.linkCode(s) or "" end
  if copied then
    local _, _, k = ns.decodeString(copied)
    k.p.level = 1
    out["bad/link-v2-bad-sig"] = ns.encodeString("link", 2, k, nil)
  end
  ns.showCopy = showCopy
  GuildaddonDB.chars[E2E_GUID] = before
  return out
end'''

CANONICAL_INPUT = {"z": 1, "n": -42, "big": 9007199254740991, "yes": True, "no": False,
                   "s": ["Épées", "tab\tnew\nline", "quote\"back\\slash", "ctl\u0001"]}


def make(lua, ns):
    g = lua.globals()
    g.E2E_LINK_CODE = LINK_TEST_CODE
    g.E2E_LINK_INPUTS = lua.table_from(LINK_INPUTS)
    t = lua.eval(GEN)(ns)
    return {k: t[k] for k in list(t)}


def decode_for_print(body):
    out = bytearray()
    for i in range(0, len(body), 4):
        v = 0
        chunk = body[i:i + 4]
        for j, c in enumerate(chunk):
            k = ALPHA.find(c)
            if k < 0:
                raise ValueError("character outside the alphabet")
            v |= k << (6 * j)
        for _ in range(len(chunk) * 6 // 8):
            out.append(v & 255)
            v >>= 8
    return bytes(out)


def decode(s):
    """SPEC 2.1-2.2: !BF:<type>:v<n>:<EncodeForPrint(raw deflate(canonical JSON))>."""
    assert s.startswith("!BF:"), s[:20]
    _, ty, v, body = s.split(":", 3)
    text = zlib.decompress(decode_for_print(body), -15).decode("utf-8")
    return ty, int(v[1:]), text, json.loads(text)


def canonical(v):
    """SPEC 2.6, for the characters the fixtures use (no DEL, no lone surrogates)."""
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build(made, secret):
    """Return {relative path: file text} for everything under contract/golden/strings."""
    a, b = made["lua51"], made["luajit"]
    files, errors = {}, []
    for base, want_v in STRINGS:
        name = base if (base, want_v) != ("link", 2) else "link.v2"
        ty = base.split(".")[0]
        if not a.get(name) or not b.get(name):
            errors.append(f"{name}: the addon made no string")
            continue
        ty_, v, text, env = decode(a[name])
        _, _, _, env_jit = decode(b[name])
        if env != env_jit:
            errors.append(f"{name}: Lua 5.1 and LuaJIT decode to different JSON")
        if ty_ != ty or v != want_v:
            errors.append(f"{name}: header says {ty_} v{v}")
        if text != canonical(env):
            errors.append(f"{name}: body is not canonical JSON")
        if (ty, v) == ("link", 2):
            errors += check_link_v2(a, b, env)
        elif ty != "link" and not sig_ok(env, secret):
            errors.append(f"{name}: HMAC does not verify in Python")
        files[f"strings/{base}.v{v}.txt"] = a[name] + "\n"
        files[f"strings/{base}.v{v}.json"] = json.dumps(env, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if a["canonical"] != canonical(CANONICAL_INPUT):
        errors.append("canonical: Lua and Python canonical JSON differ")
    files["strings/canonical.v1.json"] = json.dumps({"input": CANONICAL_INPUT, "canonical": a["canonical"]},
                                                    indent=2, ensure_ascii=False) + "\n"
    files["strings/secret.v1.hex"] = secret + "\n"
    if a.get("link.v2") and a.get("bad/link-v2-bad-sig"):
        files["strings/link-kdf.v2.json"] = link_kdf_file(a)
        files["strings/bad/link-v2-bad-sig.txt"] = a["bad/link-v2-bad-sig"] + "\n"
    gb = a["gbank"]
    bad = {
        "bad-prefix": ("hello", "bad_prefix"),
        "unknown-type": (gb.replace("!BF:gbank:", "!BF:nope:", 1), "unknown_type"),
        "unsupported-version": (gb.replace(":v1:", ":v9:", 1), "unsupported_version"),
        "decode-failed": ("!BF:gbank:v1:" + "~" * 40, "decode_failed"),
        "bad-sig": (a["bad/bad-sig"], "bad_sig"),
    }
    expected = {}
    for name, (s, err) in bad.items():
        files[f"strings/bad/{name}.txt"] = s + "\n"
        expected[f"{name}.txt"] = err
    expected["too-large"] = {"rule": "'!BF:gbank:v1:' followed by 262144 'a' characters (longer than MAX_STRING)",
                             "error": "too_large"}
    files["strings/bad/expected.json"] = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    return files, errors


def check_link_v2(a, b, env):
    """The link v2 string against SPEC 3.3.2, recomputed here in Python."""
    errors = []
    p = env.get("p", {})
    if set(p) != {"lookup", "n", "class", "race", "level"}:
        errors.append(f"link.v2: payload fields are {sorted(p)}")
    if not re.fullmatch(r"[0-9a-f]{32}", str(p.get("n", ""))):
        errors.append("link.v2: n is not 32 lower hex")
    _, lookup, secret = link_keys(LINK_TEST_CODE, env["char"]["guid"], p.get("n", ""))
    if p.get("lookup") != lookup:
        errors.append("link.v2: lookup differs from the SPEC derivation")
    for label, made in (("Lua 5.1", a), ("LuaJIT", b)):
        if made.get("link.v2.secret") != secret:
            errors.append(f"link.v2: the secret {label} kept differs from the SPEC derivation")
    if not sig_ok(env, secret):
        errors.append("link.v2: sig does not verify with the derived secret")
    if LINK_TEST_CODE in a["link.v2"] or LINK_TEST_CODE in json.dumps(env) or secret in json.dumps(env):
        errors.append("link.v2: the string carries the code or the secret")
    for i, s in enumerate(LINK_INPUTS, 1):
        for label, made in (("Lua 5.1", a), ("LuaJIT", b)):
            if (made.get(f"norm.{i}") or None) != link_code(s):
                errors.append(f"link.v2: {label} normalizes {s!r} to {made.get(f'norm.{i}')!r}, SPEC says {link_code(s)!r}")
    _, _, _, bad = decode(a["bad/link-v2-bad-sig"])
    if sig_ok(bad, secret):
        errors.append("link.v2: the tampered string still verifies")
    return errors


def link_kdf_file(a):
    """strings/link-kdf.v2.json: the vectors the site tests its derivation against (SPEC 3.3.2)."""
    _, _, _, env = decode(a["link.v2"])
    guid, n = env["char"]["guid"], env["p"]["n"]
    prk, lookup, secret = link_keys(LINK_TEST_CODE, guid, n)
    body = {k: x for k, x in env.items() if k != "sig"}
    return json.dumps({
        "spec": "contract/SPEC.md 3.3.2",
        "kdf": "HKDF-SHA256 (RFC 5869)",
        "alphabet": LINK_ALPHABET,
        "codeLength": 26,
        "salt": LINK_SALT.decode(),
        "lookupInfo": "lookup",
        "lookupLength": 16,
        "secretInfo": f"secret:{guid}:{n}",
        "secretLength": 32,
        "code": LINK_TEST_CODE,
        "guid": guid,
        "n": n,
        "prk": prk,
        "lookup": lookup,
        "secret": secret,
        "string": "link.v2.txt",
        "signedText": canonical(body),
        "sig": env["sig"],
        "normalization": [{"input": s, "code": link_code(s)} for s in LINK_INPUTS],
        "bad": {"bad/link-v2-bad-sig.txt": {"change": "p.level set to 1 after signing", "error": "bad_sig"}},
    }, indent=2, ensure_ascii=False) + "\n"


def manifest(files):
    """MANIFEST.json over every file under contract/golden (strings from here, http from cargo)."""
    entries = {}
    for dirpath, _, names in os.walk(ROOT):
        for n in names:
            rel = os.path.relpath(os.path.join(dirpath, n), ROOT).replace(os.sep, "/")
            if rel in ("MANIFEST.json", "README.md") or rel.startswith("strings/"):
                continue
            entries[rel] = open(os.path.join(dirpath, n), "rb").read()
    for rel, text in files.items():
        entries[rel] = text.encode()
    return json.dumps({
        "exportVersions": {k: v for k, v in sorted(TYPES.items())},
        "uploaderProtocol": UPLOADER_PROTOCOL,
        "generators": {"strings/": "python tests/run.py --write-golden",
                       "http/*.request.json": "WRITE_GOLDEN=1 cargo test -p guild-uploader-core golden",
                       "http/*.response.json": "written by hand from contract/SPEC.md section 4.2; checked by the site"},
        "pending": ["link-ok, signup, attendance, kills, signups strings: produced or read only by the site; added by a site PR",
                    "oauth-* http pairs: A5", "stale and bad-envelope strings: need the site's rules"],
        "files": {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(entries.items())},
    }, indent=2) + "\n"


def check_or_write(made, secret, write=False):
    files, errors = build(made, secret)
    for e in errors:
        print("golden:", e)
    if errors:
        return 1
    files["MANIFEST.json"] = manifest(files)
    if write:
        for rel, text in files.items():
            p = os.path.join(ROOT, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        print(f"golden: wrote {len(files)} files under contract/golden")
        return 0
    bad = []
    for rel, text in sorted(files.items()):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            bad.append(f"missing {rel}")
        elif open(p, encoding="utf-8").read() != text:
            bad.append(f"differs {rel}")
    for b in bad:
        print("golden:", b)
    if bad:
        print("golden: output differs from contract/golden. A changed encoding needs a new version (contract/SPEC.md 5.2);"
              " regenerate only for new files: python tests/run.py --write-golden")
        return 1
    print(f"golden: {len(files)} files match")
    return 0
