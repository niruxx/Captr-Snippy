fn main() {
    // Tauri's default Windows manifest declares no DPI-awareness at all, so
    // Win32 APIs this app calls directly (GetSystemMetrics, EnumDisplayMonitors,
    // GetWindowRect - see src/capture/win_enum.rs) fall back to Windows'
    // virtualized/scaled coordinates instead of true physical pixels. That's
    // harmless for apps that only ever go through WebView2's own (always
    // per-monitor-aware) content scaling, but this app also feeds those
    // Win32 values straight into the capture-overlay window's physical
    // size/position - so a 150% display scale silently produced a
    // ~1.5x-too-small overlay before this manifest was added. `true/pm` is
    // the pre-Win10-1703 fallback; `PerMonitorV2` is what actually applies
    // on Win10 1703+ (this app's real minimum in practice, since it's
    // Windows-only and already depends on Windows 10 1903+ HDR APIs).
    let windows = tauri_build::WindowsAttributes::new().app_manifest(
        r#"<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <dependency>
    <dependentAssembly>
      <assemblyIdentity
        type="win32"
        name="Microsoft.Windows.Common-Controls"
        version="6.0.0.0"
        processorArchitecture="*"
        publicKeyToken="6595b64144ccf1df"
        language="*"
      />
    </dependentAssembly>
  </dependency>
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2</dpiAwareness>
    </windowsSettings>
  </application>
</assembly>"#,
    );
    tauri_build::try_build(tauri_build::Attributes::new().windows_attributes(windows))
        .expect("failed to run tauri-build");
}
