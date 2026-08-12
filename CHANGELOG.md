# Changelog

## [1.2.0] - 2026-08-13

## [1.1.0] - 2026-08-11

### Added

- Menu bar / system tray mode — TuFac starts in the tray; quit via the tray icon menu
- Tray icon adapts automatically to light and dark mode (macOS)
- Settings dialog with a "Start at login" option
- No Dock icon on macOS when running in the tray

## [1.0.0] - 2026-08-10

### Added

- Local, encrypted TOTP authenticator with native desktop UI (PySide6)
- Tree-based organization of groups and accounts with drag & drop reordering and per-group colors
- One-time code generation on the device with live countdown and one-click copy
- Import from Google Authenticator `otpauth-migration://` QR codes (image files or webcam), multi-batch supported
- Passphrase-protected encrypted backup export and import
- Flexible accounts: SHA1/SHA256/SHA512/MD5, 6 or 8 digits, configurable period
- Dark theme
- macOS (Intel & Apple Silicon) and Windows standalone binaries built via GitHub Actions
