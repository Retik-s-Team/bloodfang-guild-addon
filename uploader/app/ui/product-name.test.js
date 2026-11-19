const assert = require("assert");
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const conf = JSON.parse(fs.readFileSync(path.join(__dirname, "../src-tauri/tauri.conf.json"), "utf8"));

// The product name, executable name and publisher live only in tauri.conf.json (and the window heading in
// index.html). These checks compare against the config instead of repeating the names.
assert.ok(conf.productName);
assert.strictEqual(conf.identifier, "com.raidgroup.guilduploader");
assert.ok(conf.bundle.publisher);
assert.strictEqual(conf.app.windows[0].title, conf.productName);
assert.match(html, new RegExp(`<title>${conf.productName}</title>`));
assert.match(html, new RegExp(`<h1>${conf.productName}</h1>`));
assert.strictEqual(conf.app.trayIcon, undefined);
assert.strictEqual(conf.bundle.windows.nsis.installerHooks, "windows/hooks.nsh");
assert.strictEqual(conf.mainBinaryName, conf.productName);
assert.strictEqual(conf.bundle.windows.webviewInstallMode.type, "skip");
const cargo = fs.readFileSync(path.join(__dirname, "../src-tauri/Cargo.toml"), "utf8").replace(/\r\n/g, "\n"); // Windows checkouts may use CRLF
assert.match(cargo, /\[\[bin\]\]\nname = "updater"\npath = "src\/bin\/updater.rs"/);
assert.ok(!cargo.includes("guild-uploader-verify-update"));
// Code reads the names at run time (the h1, the Tauri config); no UI source file spells them.
const brandNames = [conf.productName, conf.mainBinaryName, conf.bundle.publisher].map((n) => n.toLowerCase());
for (const file of fs.readdirSync(__dirname).filter((f) => /\.(js|css)$/.test(f))) {
  const text = fs.readFileSync(path.join(__dirname, file), "utf8").toLowerCase();
  for (const name of brandNames) assert.ok(!text.includes(name), `${file} spells a name from tauri.conf.json`);
}
assert.ok(html.includes("Reads the addon's saved files (SavedVariables) only."));
assert.ok(html.includes('class="sub sub-rule">Never touches the game process.</p>'));
const saved = html.indexOf("Reads the addon's saved files");
const rule = html.indexOf("Never touches the game process.");
assert.ok(saved >= 0 && rule > saved);
const hooks = fs.readFileSync(path.join(__dirname, "../src-tauri/windows/hooks.nsh"), "utf8");
assert.ok(hooks.includes("${LEGACYPRODUCTNAME}"));
assert.ok(hooks.includes("Guild Uploader"));
assert.ok(hooks.includes('"guild-uploader-app"'));
assert.ok(hooks.includes("$INSTDIR\\${MAINBINARYNAME}.exe"));
for (const name of brandNames) assert.ok(!hooks.toLowerCase().includes(name), "hooks.nsh spells a name from tauri.conf.json");
assert.ok(!html.includes("Guild Uploader"));
assert.ok(!html.includes("Upload now"));
assert.ok(!html.includes("Update available"));
assert.ok(!html.includes("A new update is available. Would you like to update now?"));
assert.ok(html.includes("Saved scans upload on their own."));

console.log("product-name.test.js ok");
