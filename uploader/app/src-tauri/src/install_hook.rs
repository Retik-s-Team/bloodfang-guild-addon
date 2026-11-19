//! The Windows installer hook is the previous-install handoff. These checks
//! lock the registry identities and the data it must not touch.

#[cfg(test)]
mod tests {
    const HOOK: &str = include_str!("../windows/hooks.nsh");
    const CONF: &str = include_str!("../tauri.conf.json");

    fn conf() -> serde_json::Value {
        serde_json::from_str(CONF).expect("tauri.conf.json parses")
    }

    fn conf_str(conf: &serde_json::Value, pointer: &str) -> String {
        conf.pointer(pointer).and_then(|v| v.as_str()).unwrap_or_else(|| panic!("tauri.conf.json has no {pointer}")).to_string()
    }

    #[test]
    fn previous_install_is_removed_without_deleting_saved_data() {
        assert!(HOOK.contains("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Guild Uploader"));
        assert!(HOOK.contains("Software\\raidgroup\\Guild Uploader"));
        assert!(HOOK.contains("Software\\Microsoft\\Windows\\CurrentVersion\\Run"));
        assert!(HOOK.contains("guild-uploader-app"));
        assert!(HOOK.contains("--hidden"));
        assert!(HOOK.contains("/S"));
        assert!(!HOOK.contains("/UPDATE"));
        assert!(!HOOK.contains("RMDir /r"));
        assert!(!HOOK.contains("DeleteAppData"));
        assert!(!HOOK.contains("guild-uploader\\"));
        assert!(HOOK.contains("Delete \"$INSTDIR\\guild-uploader-verify-update.exe\""));
        assert!(HOOK.contains("NSIS_HOOK_PREINSTALL"));
        assert!(HOOK.contains("NSIS_HOOK_POSTINSTALL"));
        assert!(HOOK.contains("NSIS_HOOK_PREUNINSTALL"));
        assert!(HOOK.contains("Software\\${MANUFACTURER}\\${LEGACYPRODUCTNAME}"));
        assert!(HOOK.contains("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${LEGACYPRODUCTNAME}"));
        assert!(HOOK.contains("$INSTDIR\\${MAINBINARYNAME}.exe"));
        assert!(HOOK.contains("DeleteRegValue HKCU \"Software\\Microsoft\\Windows\\CurrentVersion\\Run\" \"${LEGACYPRODUCTNAME}\""));
        assert!(HOOK.contains("DeleteRegValue HKCU \"Software\\Microsoft\\Windows\\CurrentVersion\\Run\" \"guild-uploader-app\""));
    }

    /// The hook names the product only through the template's defines, which come from
    /// tauri.conf.json. A name copied into the hook would go stale when the config changes.
    #[test]
    fn hook_takes_every_name_from_the_packaging_config() {
        let conf = conf();
        let hook = HOOK.to_lowercase();
        for pointer in ["/productName", "/mainBinaryName", "/bundle/publisher", "/app/windows/0/title"] {
            let name = conf_str(&conf, pointer);
            assert!(!name.is_empty(), "{pointer} is empty");
            assert!(!hook.contains(&name.to_lowercase()), "hooks.nsh spells {pointer}; use the template define instead");
        }
        // The template includes the hook before its defines, so they may only appear inside macros.
        let first_macro = HOOK.find("!macro ").expect("hook has macros");
        for define in ["${PRODUCTNAME}", "${MANUFACTURER}", "${MAINBINARYNAME}", "${LEGACYPRODUCTNAME}"] {
            assert!(!HOOK[..first_macro].lines().any(|l| !l.trim_start().starts_with(';') && l.contains(define)), "{define} used outside a macro");
        }
    }

    /// The earlier "<name> App" build is found by replacing " Uploader" in the product name.
    /// The shipped config must keep that suffix, or the installer stops removing that build.
    #[test]
    fn legacy_product_name_derives_from_the_product_name() {
        assert!(HOOK.contains("!searchreplace LEGACYPRODUCTNAME \"${PRODUCTNAME}\" \" Uploader\" \" App\""));
        assert!(HOOK.contains("!if \"${LEGACYPRODUCTNAME}\" != \"${PRODUCTNAME}\""));
        let conf = conf();
        let product = conf_str(&conf, "/productName");
        assert!(product.ends_with(" Uploader"), "productName must end in \" Uploader\" so the earlier \" App\" install is still removed");
        assert_eq!(conf_str(&conf, "/mainBinaryName"), product);
        assert!(!conf_str(&conf, "/bundle/publisher").is_empty(), "the earlier install's registry key is under the publisher");
    }
}
