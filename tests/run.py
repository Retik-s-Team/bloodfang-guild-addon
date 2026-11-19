# Loads the addon under Lua 5.1 and LuaJIT with game API stubs and checks its export strings.
# Then compares what it produces with contract/golden/strings (see contract/golden/README.md).
# `python tests/run.py --write-golden` writes those files instead of comparing (for a NEW version only).
import sys, json, lupa.lua51 as L51, lupa.luajit21 as LJ
root = __import__("os").path.dirname(__file__) + "/../addon/"
import os
SECRET = os.environ.get("E2E_SECRET", "11" * 32)
GUID = os.environ.get("E2E_GUID", "Player-4395-0ABCDEF1")
STUBS = r'''
local t0 = E2E_T0
GetServerTime = function() return t0 end
GetTime = function() return 12.5 end
-- Deterministic math.random (Park-Miller; products stay exact in doubles on Lua 5.1 and LuaJIT), so export ids
-- are the same on both runtimes. E2E_SEED resets the sequence before the golden strings are made.
local seed = 1
function E2E_SEED(n) seed = n end
math.random = function(a, b)
  seed = (seed * 16807) % 2147483647
  if a == nil then return seed / 2147483647 end
  if b == nil then a, b = 1, a end
  return a + seed % (b - a + 1)
end
math.randomseed = function() end
time = GetServerTime
UnitGUID = function() return E2E_GUID end
UnitFullName = function() return "Testchar", "Testrealm" end
GetRealmName = function() return "Testrealm" end
UnitClass = function() return "Mage", "MAGE" end
UnitRace = function() return "Gnome", "Gnome" end
UnitLevel = function() return 60 end
GetAddOnMetadata = function() return "0.1.0" end
printed = {}
DEFAULT_CHAT_FRAME = { AddMessage = function(_, m) printed[#printed+1] = m end }
local frame = {} frame.__index = function() return function() end end
CreateFrame = function() return setmetatable({ RegisterEvent = function() end, SetScript = function(self, k, f) self[k] = f end }, frame) end
C_Timer = { After = function(_, f) end, NewTimer = function() return { Cancel = function() end } end, NewTicker = function() end }
SlashCmdList = {}
UISpecialFrames = {}
tinsert = table.insert
GetItemInfoInstant = function(id) return id, nil, nil, nil, 100000 + id end
IsInGuild = function() return E2E_IN_GUILD end
GetGuildInfo = function(u) return "Example Guild", "Officer", 1 end
GuildControlGetNumRanks = function() return #E2E_RANKS end
GuildControlGetRankName = function(i) return E2E_RANKS[i] end
E2E_IN_GUILD = true
E2E_RANKS = { "Guild Master", " Officer ", "Raid Lead", "Guild Member", "Trial", "Alt" }
'''
def load(lua, shim):
    g = lua.globals()
    ns = lua.table()
    lua.globals().E2E_GUID = GUID
    lua.globals().E2E_T0 = int(os.environ.get("E2E_T0", "1793836800"))
    lua.execute(STUBS)
    if shim: lua.execute(open(__import__("os").path.dirname(__file__) + "/bitshim.lua").read())
    for f in ["Libs/LibDeflate.lua", "Codec.lua", "Core.lua", "Bank.lua", "Recipes.lua", "Guild.lua"]:
        lua.eval("function(src, name, ns) local f = assert(loadstring(src, name)) return f('Guildaddon', ns) end")(open(root + f).read(), f, ns)
    lua.execute("GuildaddonDB = { chars = { [E2E_GUID] = { secret = '%s' } }, outbox = {}, settings = {} }" % SECRET)
    return ns
out = {}
for label, mk, shim in [("luajit", LJ.LuaRuntime, False), ("lua51", L51.LuaRuntime, True)]:
    lua = mk()
    ns = load(lua, shim)
    h = lua.eval("function(ns) return ns.toHex(ns.sha256('abc')), ns.toHex(ns.hmac(string.rep(string.char(0x0b),20), 'Hi There')) end")(ns)
    tabs = lua.eval('''function(ns) return { { tab = 1, name = "Mats: \\"ore\\"", slots = {
      { link = "|cffffffff|Hitem:2771::::::::60:::::|h[Tin Ore]|h|r", count = 20, texture = 135 },
      { link = "|Hitem:2771::|h", count = 5 }, { link = "|Hitem:13444::|h", count = 1 } } },
      { tab = 2, name = "Épées", slots = {} } } end''')(ns)
    p = lua.eval("function(ns, tabs) return ns.bankPayload(tabs, 1234567, function(id) return 100000 + id end) end")(ns, tabs)
    gb = ns.export("gbank", p)
    rc = ns.export("recipes", lua.eval("function(ns) return { profession = 'Alchemy', skill = 300, recipes = ns.recipeIds({ '|Henchant:17187|h', 'spell:3170', '|Henchant:17187|h' }) } end")(ns))
    rt = lua.eval("function(ns, s) local ty, v, j = ns.decodeString(s) return ty, v, j.p.tabs[1].items[1].count end")(ns, gb)
    # Guild rank names: pure reader (1-based, GM first), capture into SavedVariables, envelope + `ranks` string.
    rn = lua.eval("""function(ns)
      local a = ns.rankNames(3, function(i) return ({ "GM", " Off ", "Mem" })[i] end)
      local none = ns.rankNames(0, function() return "x" end)
      local bad = ns.rankNames(2, function(i) if i == 1 then return "GM" end end)
      local big = ns.rankNames(12, function(i) return "R" .. i end)
      return table.concat(a, "|"), none == nil, bad == nil, #big
    end""")(ns)
    assert list(rn) == ["GM|Off|Mem", True, True, 10], (label, list(rn))
    lua.eval("function(ns) GuildaddonDB.guild = nil ns.captureRanks() end")(ns)
    cap = lua.eval("function(ns) local g = GuildaddonDB.guild return g.name, table.concat(g.ranks, '|'), g.t, GuildaddonDB.outbox.ranks ~= nil end")(ns)
    assert list(cap) == ["Example Guild", "Guild Master|Officer|Raid Lead|Guild Member|Trial|Alt", int(os.environ.get("E2E_T0", "1793836800")), True], (label, list(cap))
    gb = ns.export("gbank", p)
    rc = ns.export("recipes", lua.eval("function(ns) return { profession = 'Alchemy', skill = 300, recipes = ns.recipeIds({ '|Henchant:17187|h', 'spell:3170', '|Henchant:17187|h' }) } end")(ns))
    rk = lua.eval("function(ns) return GuildaddonDB.outbox.ranks.s end")(ns)
    env = lua.eval("""function(ns, s, r) local _, _, j = ns.decodeString(s) local _, _, k = ns.decodeString(r)
      return j.guild.name, table.concat(j.guild.ranks, '|'), k.p.name, #k.p.ranks, k.guild == nil end""")(ns, gb, rk)
    assert list(env) == ["Example Guild", "Guild Master|Officer|Raid Lead|Guild Member|Trial|Alt", "Example Guild", 6, True], (label, list(env))
    # Not in a guild any more: exports carry no guild block.
    lua.execute("E2E_IN_GUILD = false")
    gb_ng = ns.export("gbank", p)
    assert lua.eval("function(ns, s) local _, _, j = ns.decodeString(s) return j.guild == nil end")(ns, gb_ng), label
    lua.execute("E2E_IN_GUILD = true")
    # Login / entering world: a roster request and a later capture are scheduled (no guild window needed), once per 10 s.
    sched = lua.eval("""function(ns)
      local after, asked = {}, 0
      C_Timer.After = function(d, f) after[#after + 1] = { d = d, f = f } end
      GuildRoster = function() asked = asked + 1 end
      GuildaddonDB.guild = nil
      ns.events.PLAYER_LOGIN[1]()
      ns.events.PLAYER_ENTERING_WORLD[1](true, false)
      local n = #after
      for _, a in ipairs(after) do a.f() end
      return n, asked, GuildaddonDB.guild ~= nil
    end""")(ns)
    assert list(sched) == [2, 1, True], (label, list(sched))
    # Recipes from the profession window (Recipes.lua). The WoW Forever client (interface 16001) has the modern
    # C_TradeSkillUI API and none of the old GetTradeSkill*/GetCraft* globals; Classic Era has the old ones.
    rec = lua.eval(r"""function(ns)
      local queue
      C_Timer.After = function(d, f) queue[#queue + 1] = f end
      local key = "recipes:" .. E2E_GUID .. ":Alchemy"
      -- Opens the window, runs the scheduled scans (and any retries they schedule), returns what was saved.
      local function open()
        queue, GuildaddonDB.outbox[key] = {}, nil
        for _, fn in ipairs(ns.events.TRADE_SKILL_SHOW) do fn() end
        local i, ok, err = 1, true, nil
        while queue[i] and i <= 20 do ok, err = pcall(queue[i]) if not ok then break end i = i + 1 end
        local e = GuildaddonDB.outbox[key]
        if not e then return ok, err, "nothing saved" end
        local _, _, j = ns.decodeString(e.s)
        return ok, err, j.p.profession .. " " .. j.p.skill .. " " .. table.concat(j.p.recipes, ",")
      end
      local legacy = { "GetTradeSkillLine", "GetNumTradeSkills", "GetTradeSkillInfo", "GetTradeSkillRecipeLink", "GetTradeSkillItemLink" }
      for _, n in ipairs(legacy) do _G[n] = nil end
      local r, linked, ready, learned = {}, false, true, { [3170] = true, [2330] = true, [7183] = false }
      C_TradeSkillUI = {
        GetBaseProfessionInfo = function() return { professionID = 171, professionName = "Alchemy", skillLevel = 0, maxSkillLevel = 0 } end,
        GetChildProfessionInfo = function() return { professionID = 2485, professionName = "Alchemy", skillLevel = 215, maxSkillLevel = 225 } end,
        GetAllRecipeIDs = function() return { 3170, 7183, 2330, 3170 } end,
        GetRecipeInfo = function(id) return { recipeID = id, learned = learned[id] } end,
        IsTradeSkillLinked = function() return linked end,
        IsTradeSkillGuild = function() return false end,
        IsNPCCrafting = function() return false end,
        IsTradeSkillReady = function() return ready end,
      }
      -- R1: modern client, own profession: learned recipe IDs and the skill level are saved, no error.
      r[#r + 1] = { open() }
      -- R2: someone else's linked profession window is not saved as this character's.
      linked = true r[#r + 1] = { open() } linked = false
      -- R3: list not ready when the timer fires: scanned again later instead of saving nothing.
      local polls = 0
      C_TradeSkillUI.IsTradeSkillReady = function() polls = polls + 1 return polls > 2 end
      r[#r + 1] = { open() }
      -- R4: neither API present: no error, nothing saved.
      C_TradeSkillUI = nil
      r[#r + 1] = { open() }
      -- R5: Classic Era globals (with Era's partial C_TradeSkillUI) still work.
      C_TradeSkillUI = { GetTradeSkillDisplayName = function() return "Alchemy" end }
      local rows = { { "Elixirs", "header" }, { "Elixir of Lion's Strength", "easy", "|cffffffff|Henchant:2329|h[Elixir of Lion's Strength]|h|r" },
        { "Minor Healing Potion", "trivial", "|Hspell:2330|h" } }
      GetTradeSkillLine = function() return "Alchemy", 120, 150 end
      GetNumTradeSkills = function() return #rows end
      GetTradeSkillInfo = function(i) return rows[i][1], rows[i][2] end
      GetTradeSkillRecipeLink = function(i) return rows[i][3] end
      GetTradeSkillItemLink = function() return nil end
      r[#r + 1] = { open() }
      for _, n in ipairs(legacy) do _G[n] = nil end
      C_TradeSkillUI = nil
      local res = {}
      for i, x in ipairs(r) do res[i] = tostring(x[1]) .. "|" .. tostring(x[2]) .. "|" .. tostring(x[3]) end
      return table.concat(res, "\n")
    end""")(ns).split("\n")
    want = ["true|nil|Alchemy 215 2330,3170", "true|nil|nothing saved", "true|nil|Alchemy 215 2330,3170",
            "true|nil|nothing saved", "true|nil|Alchemy 120 2329,2330"]
    for i, (got, exp) in enumerate(zip(rec, want), 1):
        assert got == exp, (label, "recipes R%d" % i, got, exp)
    out[label] = {"sha": h[0], "hmac": h[1], "gbank": gb, "recipes": rc, "ranks": rk, "roundtrip": list(rt)}
    print(label, h[0][:16], h[1][:16], len(gb), list(rt))
for k, r in out.items():
    assert r["sha"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", k
    assert r["hmac"] == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7", k
    assert r["roundtrip"] == ["gbank", 1, 25], k
    assert r["gbank"].startswith("!BF:gbank:v1:") and r["recipes"].startswith("!BF:recipes:v1:"), k
print("all addon tests passed")

# ---------- golden fixtures (contract/golden/strings) ----------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden
made = {}
for label, mk, shim in [("lua51", L51.LuaRuntime, True), ("luajit", LJ.LuaRuntime, False)]:
    lua = mk()
    ns = load(lua, shim)
    made[label] = golden.make(lua, ns)
sys.exit(golden.check_or_write(made, SECRET, write="--write-golden" in sys.argv))
