-- Guild bank capture (SPEC §13, contract/SPEC.md `gbank`): every viewable tab's item IDs and counts, each
-- item's icon as the game reports it, and guild bank gold. Runs when the guild bank window opens: newer clients (WoW
-- Forever, interface 16001) say so with PLAYER_INTERACTION_MANAGER_FRAME_SHOW and the GuildBanker type, older ones with
-- GUILDBANKFRAME_OPENED. Forever still knows GUILDBANKFRAME_OPENED but never fires it.
local _, ns = ...
local MAX_TABS = 8
local SLOTS = 98
local pending, isOpen, timer

-- Pure part, testable outside the game: raw slots -> payload.
-- tabs = { { tab = n, name = "...", slots = { { link = "|Hitem:123:...|h", count = 5, texture = 1234 }, ... } } }
function ns.bankPayload(tabs, copper, iconFor)
  local out = ns.array()
  for _, t in ipairs(tabs) do
    local items, idx = ns.array(), {}
    for _, s in ipairs(t.slots) do
      local id = s.link and tonumber(s.link:match("item:(%d+)"))
      if id and s.count and s.count > 0 then
        local e = idx[id]
        if e then e.count = e.count + s.count
        else
          e = { itemId = id, count = s.count, icon = (iconFor and iconFor(id)) or s.texture }
          idx[id] = e
          items[#items + 1] = e
        end
      end
    end
    out[#out + 1] = { tab = t.tab, name = t.name, items = items }
  end
  local p = { tabs = out }
  if copper then p.copper = copper end
  return p
end

local function iconFor(id)
  local info = (C_Item and C_Item.GetItemInfoInstant) or GetItemInfoInstant
  local icon = info and select(5, info(id))
  return icon
end

local function finish()
  local tabs = {}
  for tab = 1, GetNumGuildBankTabs() do
    local name, _, viewable = GetGuildBankTabInfo(tab)
    if viewable then
      local slots = {}
      for slot = 1, SLOTS do
        local texture, count = GetGuildBankItemInfo(tab, slot)
        local link = GetGuildBankItemLink(tab, slot)
        if link then slots[#slots + 1] = { link = link, count = count, texture = texture } end
      end
      tabs[#tabs + 1] = { tab = tab, name = name, slots = slots }
    end
  end
  if #tabs == 0 then ns.print("No guild bank tabs you can view were found.") return end
  local money = GetGuildBankMoney and GetGuildBankMoney()
  local s = ns.export("gbank", ns.bankPayload(tabs, money, iconFor))
  if s then
    ns.queue("gbank", "gbank", s)
    local n = 0
    for _, t in ipairs(tabs) do n = n + #t.slots end
    ns.print(("Guild bank captured (%d tabs, %d slots). It uploads with the uploader after /reload or logout, or copy it with %s export gbank."):format(#tabs, n, ns.cmd))
  end
end

-- Query each viewable tab once; the server answers with GUILDBANKBAGSLOTS_CHANGED. Capture after a quiet second.
local function settle()
  if timer then timer:Cancel() end
  timer = C_Timer.NewTimer(1.5, function() timer = nil if pending then pending = false finish() end end)
end
local function start()
  pending = true
  for tab = 1, math.min(GetNumGuildBankTabs(), MAX_TABS) do
    local _, _, viewable = GetGuildBankTabInfo(tab)
    if viewable then
      C_Timer.After(0.3 * tab, function() if pending then QueryGuildBankTab(tab) end end)
    end
  end
  settle()
end

-- A client that sends both kinds of event still captures once per visit.
local function opened() if not isOpen then isOpen = true start() end end
local function closed()
  if not isOpen then return end
  isOpen = false
  if pending then pending = false if timer then timer:Cancel() timer = nil end finish() end
end
local function isGuildBanker(ty)
  return ty ~= nil and Enum and Enum.PlayerInteractionType and ty == Enum.PlayerInteractionType.GuildBanker
end

-- nil when the guild bank window is closed, "reading" while a capture runs, "open" otherwise.
function ns.bankState()
  local gb = Enum and Enum.PlayerInteractionType and Enum.PlayerInteractionType.GuildBanker
  local pim = C_PlayerInteractionManager
  local open = isOpen or (gb and pim and pim.IsInteractingWithNpcOfType and pim.IsInteractingWithNpcOfType(gb))
  if not open then return nil end
  return pending and "reading" or "open"
end

ns.on("GUILDBANKFRAME_OPENED", opened)
ns.on("GUILDBANKFRAME_CLOSED", closed)
ns.on("PLAYER_INTERACTION_MANAGER_FRAME_SHOW", function(ty) if isGuildBanker(ty) then opened() end end)
ns.on("PLAYER_INTERACTION_MANAGER_FRAME_HIDE", function(ty) if isGuildBanker(ty) then closed() end end)
ns.on("GUILDBANKBAGSLOTS_CHANGED", function() if pending then settle() end end)

-- Linked while the bank window is open: capture it now rather than wait for the next visit.
table.insert(ns.afterLink, function()
  if ns.bankState() and not pending then
    ns.print("The guild bank is open; reading it now.")
    isOpen = true
    start()
  end
end)
