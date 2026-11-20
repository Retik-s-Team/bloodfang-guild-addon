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
-- Frames remember the events they register; E2E_FIRE delivers an event to them the way the client does. Like the
-- client, RegisterEvent raises an error for an event the client doesn't know (E2E_KNOWN_EVENTS, when set).
local frames = {}
CreateFrame = function()
  local f = setmetatable({ events = {}, SetScript = function(self, k, fn) self[k] = fn end }, frame)
  f.RegisterEvent = function(self, e)
    if E2E_KNOWN_EVENTS and not E2E_KNOWN_EVENTS[e] then error('Attempt to register unknown event "' .. tostring(e) .. '"') end
    self.events[e] = true
  end
  frames[#frames + 1] = f
  return f
end
function E2E_FIRE(e, ...) for _, f in ipairs(frames) do if f.events[e] and f.OnEvent then f.OnEvent(f, e, ...) end end end
function E2E_REGISTERED(e) for _, f in ipairs(frames) do if f.events[e] then return true end end return false end
-- The events the addon may register that the WoW Forever client knows (wowless data/products/wowf/events.yaml,
-- client 1.60.1.70888). CRAFT_SHOW is not one of them. GUILDBANKFRAME_OPENED/_CLOSED are known but never fire there:
-- the guild bank opens through PLAYER_INTERACTION_MANAGER_FRAME_SHOW with Enum.PlayerInteractionType.GuildBanker.
E2E_KNOWN_EVENTS = {}
for _, e in ipairs({ "ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "PLAYER_GUILD_UPDATE", "GUILD_ROSTER_UPDATE",
  "CHAT_MSG_ADDON", "TRADE_SKILL_SHOW", "GUILDBANKFRAME_OPENED", "GUILDBANKFRAME_CLOSED", "GUILDBANKBAGSLOTS_CHANGED",
  "PLAYER_INTERACTION_MANAGER_FRAME_SHOW", "PLAYER_INTERACTION_MANAGER_FRAME_HIDE" }) do E2E_KNOWN_EVENTS[e] = true end
Enum = { PlayerInteractionType = { Merchant = 5, GuildBanker = 10 } }
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
    # Guild bank capture (Bank.lua). The WoW Forever client (interface 16001) opens the guild bank with
    # PLAYER_INTERACTION_MANAGER_FRAME_SHOW(Enum.PlayerInteractionType.GuildBanker), not GUILDBANKFRAME_OPENED.
    bank = lua.eval(r"""function(ns)
      local GB, MERCHANT = Enum.PlayerInteractionType.GuildBanker, Enum.PlayerInteractionType.Merchant
      local timers, queried, interacting = {}, {}, nil
      C_Timer.After = function(d, f) timers[#timers + 1] = { f = f } end
      C_Timer.NewTimer = function(d, f) local t = { f = f } t.Cancel = function() t.cancelled = true end timers[#timers + 1] = t return t end
      local function drain() local i = 1 while timers[i] and i <= 50 do local t = timers[i] if not t.cancelled then t.f() end i = i + 1 end timers = {} end
      local tabs = { { "Mats", true, { [1] = { 2771, 20 }, [5] = { 2771, 5 }, [9] = { 13444, 1 } } }, { "Officers", false, {} }, { "Gear", true, { [3] = { 19019, 1 } } } }
      GetNumGuildBankTabs = function() return #tabs end
      GetGuildBankTabInfo = function(t) return tabs[t][1], 133784, tabs[t][2] end
      GetGuildBankItemInfo = function(t, s) local i = tabs[t][3][s] if i then return 100 + i[1], i[2] end end
      GetGuildBankItemLink = function(t, s) local i = tabs[t][3][s] if i then return "|cffffffff|Hitem:" .. i[1] .. "::::::::60:::::|h[x]|h|r" end end
      QueryGuildBankTab = function(t) queried[#queried + 1] = t end
      GetGuildBankMoney = function() return 4200000 end
      C_PlayerInteractionManager = { IsInteractingWithNpcOfType = function(ty) return interacting == ty end }
      local secret = GuildaddonDB.chars[E2E_GUID]
      local function reset() GuildaddonDB.outbox, queried, timers = {}, {}, {} for k in pairs(printed) do printed[k] = nil end end
      local function captured()
        local n = 0 for _, m in ipairs(printed) do if m:find("Guild bank captured", 1, true) then n = n + 1 end end return n
      end
      local function saved()
        local e = GuildaddonDB.outbox.gbank
        if not e then return "nothing saved" end
        local ty, _, j = ns.decodeString(e.s)
        local parts = {}
        for _, t in ipairs(j.p.tabs) do
          local items = {} for _, it in ipairs(t.items) do items[#items + 1] = it.itemId .. "x" .. it.count end
          parts[#parts + 1] = t.tab .. ":" .. table.concat(items, ",")
        end
        return ty .. " " .. table.concat(parts, " ") .. " " .. tostring(j.p.copper)
      end
      local function open(ty) interacting = ty E2E_FIRE("PLAYER_INTERACTION_MANAGER_FRAME_SHOW", ty) end
      local function close(ty) interacting = nil E2E_FIRE("PLAYER_INTERACTION_MANAGER_FRAME_HIDE", ty) end
      local function last() return printed[#printed] or "" end
      local r = {}
      local function check(name, fn) local ok, v = pcall(fn) r[#r + 1] = name .. "=" .. (ok and tostring(v) or ("error: " .. tostring(v))) end
      -- R1: the Forever client opens the bank: viewable tabs are queried, a gbank string is saved, the capture is printed.
      check("R1", function()
        reset() open(GB) E2E_FIRE("GUILDBANKBAGSLOTS_CHANGED") drain() close(GB)
        return saved() .. " queried=" .. table.concat(queried, ",") .. " printed=" .. captured()
      end)
      -- R2: another interaction window (a merchant) starts no capture.
      check("R2", function() reset() open(MERCHANT) drain() close(MERCHANT) return saved() .. " queried=" .. #queried end)
      -- R3: closing the bank before the capture settles captures straight away, once.
      check("R3", function()
        reset() open(GB) close(GB) local at = saved() drain() return at .. " printed=" .. captured()
      end)
      -- R4: older clients' GUILDBANKFRAME_OPENED/_CLOSED still capture, and a client that sends both kinds captures once.
      check("R4", function()
        reset() E2E_FIRE("GUILDBANKFRAME_OPENED") drain() E2E_FIRE("GUILDBANKFRAME_CLOSED") local a = saved() .. " printed=" .. captured()
        reset() open(GB) E2E_FIRE("GUILDBANKFRAME_OPENED") drain() close(GB) E2E_FIRE("GUILDBANKFRAME_CLOSED")
        return a .. " both=" .. captured()
      end)
      -- R5: events the client doesn't know are skipped without an error (CRAFT_SHOW on Forever).
      check("R5", function()
        local ok, res = pcall(ns.on, "E2E_NOT_AN_EVENT", function() end)
        return tostring(ok) .. " " .. tostring(res) .. " " .. tostring(E2E_REGISTERED("CRAFT_SHOW")) .. " " .. tostring(ns.events.E2E_NOT_AN_EVENT)
      end)
      -- R6: the bank is open when the character gets linked: the capture runs then.
      check("R6", function()
        reset() GuildaddonDB.chars[E2E_GUID] = nil
        open(GB) drain()
        local before = saved()
        local s = ns.encodeString("link-ok", 1, { char = { guid = E2E_GUID }, p = { secret = string.rep("11", 32) } }, nil)
        ns.commands.import(s) drain()
        local after = saved() close(GB)
        return before .. " / " .. after
      end)
      -- R7: export with nothing saved says why: the bank is still being read; or the character isn't linked.
      check("R7", function()
        reset() open(GB) ns.commands.export("") local a = last() drain() close(GB)
        reset() GuildaddonDB.chars[E2E_GUID] = nil ns.commands.export("") local b = last()
        GuildaddonDB.chars[E2E_GUID] = secret
        return tostring(a:find("guild bank is still being read", 1, true) ~= nil) .. " " .. tostring(b:find("isn't linked", 1, true) ~= nil)
      end)
      GuildaddonDB.chars[E2E_GUID] = secret
      GuildaddonDB.outbox = {}
      return table.concat(r, "\n")
    end""")(ns).split("\n")
    full = "gbank 1:2771x25,13444x1 3:19019x1 4200000"
    want = ["R1=%s queried=1,3 printed=1" % full, "R2=nothing saved queried=0", "R3=%s printed=1" % full,
            "R4=%s printed=1 both=1" % full, "R5=true false false nil", "R6=nothing saved / %s" % full, "R7=true true"]
    for got, exp in zip(bank, want):
        assert got == exp, (label, "gbank", got, exp)
    assert len(bank) == len(want), (label, bank)
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
