-- Crafting recipe export (SPEC §12, contract/SPEC.md `recipes`): when a profession window opens, the
-- spell IDs this character knows for it. Two client APIs: Classic Era has the GetTradeSkill*/GetCraft* globals
-- (Enchanting uses the craft window there); WoW Forever (interface 16001) has only C_TradeSkillUI.
local _, ns = ...
local KNOWN = { Alchemy = true, Blacksmithing = true, Cooking = true, Enchanting = true, Engineering = true, ["First Aid"] = true, Leatherworking = true, Tailoring = true }

-- Pure: links (or spell IDs) -> sorted unique spell IDs.
function ns.recipeIds(links)
  local seen, ids = {}, ns.array()
  for _, l in ipairs(links) do
    local id = type(l) == "number" and l or (l and tonumber(l:match("enchant:(%d+)") or l:match("spell:(%d+)")))
    if id and not seen[id] then seen[id] = true ids[#ids + 1] = id end
  end
  table.sort(ids)
  return ids
end

local function save(prof, skill, links)
  if not KNOWN[prof] then return end -- names are the English client's; other locales aren't supported yet
  local ids = ns.recipeIds(links)
  if #ids == 0 then return end
  local s = ns.export("recipes", { profession = prof, skill = skill or 0, recipes = ids })
  if s then
    ns.queue("recipes:" .. UnitGUID("player") .. ":" .. prof, "recipes", s)
    ns.print(("%s: %d recipes saved for the site."):format(prof, #ids))
  end
end

local function scanLegacy()
  local prof, skill = GetTradeSkillLine()
  if not prof or prof == "UNKNOWN" then return end
  local links = {}
  for i = 1, GetNumTradeSkills() do
    local _, kind = GetTradeSkillInfo(i)
    if kind ~= "header" and kind ~= "subheader" then
      links[#links + 1] = (GetTradeSkillRecipeLink and GetTradeSkillRecipeLink(i)) or GetTradeSkillItemLink(i)
    end
  end
  save(prof, skill, links)
end
-- C_TradeSkillUI: recipe IDs are the spell IDs; only learned ones count. The list can still be loading when the
-- timer fires, so it is scanned again a few times before giving up.
local function scanModern(tries)
  local T = C_TradeSkillUI
  local function is(f) return T[f] and T[f]() end
  if is("IsTradeSkillLinked") or is("IsTradeSkillGuild") or is("IsNPCCrafting") then return end -- not this character's
  if T.IsTradeSkillReady and not T.IsTradeSkillReady() then
    if tries < 5 then C_Timer.After(1, function() scanModern(tries + 1) end) end
    return
  end
  local base = T.GetBaseProfessionInfo and T.GetBaseProfessionInfo()
  local child = T.GetChildProfessionInfo and T.GetChildProfessionInfo()
  local prof = (base and base.professionName) or (child and (child.parentProfessionName or child.professionName))
  if not prof then return end
  local skill = (child and (child.skillLevel or 0) > 0 and child.skillLevel) or (base and base.skillLevel)
  local ids = {}
  for _, id in ipairs(T.GetAllRecipeIDs() or {}) do
    local info = T.GetRecipeInfo and T.GetRecipeInfo(id)
    if info and info.learned and not info.isDummyRecipe then ids[#ids + 1] = id end
  end
  save(prof, skill, ids)
end
local function scanTrade()
  if GetTradeSkillLine then return scanLegacy() end
  -- Classic Era also has a C_TradeSkillUI, but without the recipe list; check for the function we need.
  if C_TradeSkillUI and C_TradeSkillUI.GetAllRecipeIDs then return scanModern(0) end
end
local function scanCraft()
  if not GetCraftDisplaySkillLine then return end
  local prof, skill = GetCraftDisplaySkillLine()
  if not prof then return end
  local links = {}
  for i = 1, GetNumCrafts() do
    local _, _, kind = GetCraftInfo(i)
    if kind ~= "header" then
      local l = GetCraftRecipeLink and GetCraftRecipeLink(i)
      if not l and GetCraftSpellID then local id = GetCraftSpellID(i) l = id and ("spell:" .. id) end
      links[#links + 1] = l or GetCraftItemLink(i)
    end
  end
  save(prof, skill, links)
end
-- The list fills in a moment after the window opens.
ns.on("TRADE_SKILL_SHOW", function() C_Timer.After(1, scanTrade) end)
ns.on("CRAFT_SHOW", function() C_Timer.After(1, scanCraft) end)
