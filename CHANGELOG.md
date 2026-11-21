# Addon changelog

The release version comes from the `addon-v<version>` tag (see `.github/workflows/addon-release.yml`); nothing in the
source carries it. Pushing the tag publishes the release.

## 0.2.3 (Nov 21, 2026)
- Linking takes two steps instead of three (link v2, `contract/SPEC.md` §3.3). With the long 26-character code the site
  will show, `<cmd> link <code>` derives the character's signing secret from the code (HKDF-SHA256, bound to the
  character) and shows a `!BF:link:v2:` string signed with it. Pasting that on the site finishes the link; there is no
  string to import back. The string carries a lookup id for the code, never the code or the secret. The code may be
  typed in lower case or grouped with spaces or hyphens.
- The 8-character code and the `<cmd> import` step keep working unchanged, and characters already linked keep their
  secret. The site accepts link v2 in a later update; until then it gives 8-character codes only.
- Linking again with a new code replaces the character's secret at once. If that string is never pasted on the site,
  the character's uploads are refused until it is linked again; the addon says so when it relinks a linked character.

## 0.2.2 (Nov 20, 2026)
- Recipes save from the profession window on the WoW Forever client (interface 16001). That client has no
  `GetTradeSkill*` / `GetCraft*` globals, so opening a profession window raised an error and saved nothing. The
  recipe list is now read through `C_TradeSkillUI` (learned recipes only, retried while the list is still loading);
  Classic Era keeps the old path.
- Guild bank capture works on the WoW Forever client (interface 16001). That client announces the bank window with
  `PLAYER_INTERACTION_MANAGER_FRAME_SHOW` / `_HIDE` (the GuildBanker type) and never fires `GUILDBANKFRAME_OPENED`,
  so nothing was captured. Both kinds are handled now, one capture per visit.
- Events a client doesn't know are skipped instead of raising an error.
- Linking a character while the guild bank is open captures it straight away. `export` with nothing saved says why:
  the character isn't linked, or the bank is still being read, or it should be reopened.

## 0.2.1 (Nov 10, 2026)
- Slash commands come from the build config: the short command (`ADDON_SLASH`) and the addon name in lower case are both
  registered, generated into `Config.lua` at package time. `/bf` is no longer registered. Help text and every printed
  hint use the short command.
- AddOns list icon: the build converts the guild logo (`ADDON_ICON`, a PNG path or https URL) to a 64x64 TGA and sets
  `## IconTexture` in the TOC. No logo file is in the source.
- Rank names are read without opening the guild window: a few seconds after login or a /reload the addon requests
  the guild roster (`C_GuildInfo.GuildRoster` or `GuildRoster`) and reads the ranks again shortly after. The guild
  window capture stays.
- `tests/package-check.sh` (run in CI before the build) checks a built zip registers both commands and not `/bf`, and
  ships the icon with the right TOC line.

## 0.2.0 (Nov 9, 2026)
- Reads the guild's rank names in game (`GuildControlGetNumRanks` / `GuildControlGetRankName`, 1-based, Guild Master
  first) on `PLAYER_GUILD_UPDATE` and `GUILD_ROSTER_UPDATE`, and keeps them in SavedVariables as
  `guild = { name, ranks, t }` (`t` = server time when read). Calls are guarded, so a client without them captures nothing.
- Signed `gbank` and `recipes` exports carry that block in their envelope, so the existing uploader sends rank names with
  no change. A separate `!BF:ranks:v1:` string is kept in the outbox (`ranks`) for an uploader that knows that type.
- `/bf ranks` shows the names read.

## 0.1.1
- Last published release.

# Uploader app changelog

The version the app reports comes from `uploader/app/src-tauri/tauri.conf.json` (with `Cargo.toml` and `Cargo.lock`);
the release file names come from the `uploader-app-v<version>` tag (`.github/workflows/uploader-app-release.yml`).
Nothing checks that they match, so bump them together. The tag builds a draft release, which is signed with
`scripts/uploader-sign-release.sh` and then published.

## 0.1.5 (Nov 20, 2026)
- Update now on Windows is one click: the verified installer runs in update mode with only a progress bar, keeps the
  installed app's shortcuts, start-at-login setting, settings and sign-in, and reopens the app when it is done (hidden
  in the tray if it was hidden). It no longer offers to uninstall the old version or walks through the setup pages.
- Before updating, the app waits up to two minutes for a running upload to finish and holds new uploads until it
  closes. If the installer doesn't start, the held uploads run and the app stays open.
- The download, SHA256SUMS and signature checks are unchanged.
- Updating from 0.1.4 to 0.1.5 still opens the setup wizard one last time, because 0.1.4 runs the old Update now code.
  Choose "Do not uninstall" there (or run the new setup as `setup.exe /P /UPDATE /R`). Later updates take one click.
- The Windows installer hook takes the product, publisher and executable names from the packaging config instead of
  spelling them out. The compiled installer behaves as before.

## 0.1.4 (Nov 11, 2026)
- Last published release.
