# My Own Control Center

**v1.0.0** — a Windows system diagnostics & optimization utility built with CustomTkinter.

> Aren't you tired of paying for software just to get a complementary tool that's somehow missing a lot of features? My Own Control Center is a full Windows PC toolkit: diagnostics, disk & memory tools, a command center, and an AI assistant, fully rebrandable, with a lightweight Basic mode built in.

## What this is

A single-file desktop app for Windows that combines the things you'd normally need several separate tools for: a live system dashboard, safe cleanup/optimization, network diagnostics, disk and memory tools, a command reference with guided execution, and a multi-provider AI assistant that can answer questions about the machine it's running on.

It ships in two view modes so it can be as simple or as full-featured as the situation calls for (see [Basic vs. Advanced mode](#basic-vs-advanced-mode)), and the app's display name is a config value, not a hardcoded string, so it can be rebranded without touching code (see [Rebranding](#rebranding)).

## Features

- **Dashboard** — live CPU/RAM/disk overview, sparkline history, background alerts (CPU, RAM, disk, connectivity).
- **Safe Optimizer** — scans for temp files, broken shortcuts, invalid startup entries, and stale registry references, and repairs them separately from the scan step (nothing is deleted or changed just by scanning).
- **Network Doctor** — gateway/Internet/DNS checks and controlled repair actions (Winsock reset, adapter reset, etc.).
- **Disk Center** — volume analysis, large-file finder, safe defrag/optimize (`defrag /A` and `/O`), read-only CHKDSK.
- **Memory Inspector** — per-process RAM snapshot and working-set trim on demand.
- **Command Center** — a library of common Windows diagnostic commands (`ipconfig`, `netsh`, `sfc`, `chkdsk`, etc.) with editable parameters, a live preview, guided help, and inline execution — parameter values are validated against an unsafe-character list before anything is run, and destructive commands require an extra confirmation.
- **AI Assistant** — ask questions about the current machine; supports Anthropic/Claude, OpenAI, DeepSeek, a local Ollama endpoint, or any custom OpenAI-compatible provider. API keys are encrypted at rest (see [Security](#security)).
- **HTML Reports** — generates a shareable technical report (system info, disks, top processes, scan results) with properly escaped output.
- **System tray support** — optional minimize-to-tray via `pystray`.

## Basic vs. Advanced mode

Settings → **Vista de la app** toggles between:

| Mode | What's visible |
|---|---|
| **Completa** (default) | Everything above. |
| **Básica** | Dashboard, Safe Optimizer, Reports, and Settings only — Network Doctor, Disk Center, Memory Inspector, Command Center, and the AI Assistant are hidden from the sidebar and the dashboard's quick actions. |

Basic mode is meant for contexts where a lighter, lower-risk tool is more appropriate than the full power-user toolkit (for example, distributing this as a companion utility alongside other software) — nothing is deleted when you switch, it's fully reversible from Settings at any time.

To make Basic mode the default for a given build, change `DEFAULT_BASIC_MODE` near the top of the file.

## Rebranding

The display name shown in the title bar, sidebar, tray icon, HTML reports, and the AI assistant's system prompt comes from `config["app_name"]`, not a hardcoded string:

- **End users** can change it any time from Settings → **Nombre de la app**.
- **Distributors** can change the factory default by editing `DEFAULT_APP_NAME` at the top of the file — no other code changes needed.

Internal identifiers (the config folder under `%APPDATA%`, the default data folder name, the Python class name) intentionally stay stable across rebrands, so renaming the visible app doesn't move or orphan a user's existing config/backups.

## Security

This build includes a few hardening fixes over the original prototype:

- AI provider API keys are encrypted at rest with Windows DPAPI (tied to the current Windows account) instead of being stored in plaintext in `config.json`. Older plaintext keys are still read correctly and get upgraded automatically the next time they're saved.
- Command Center parameter values are checked against a list of shell metacharacters (`& | ; \` $ < > ^ " ' % ( )`, newlines) before being inserted into a command template, closing off a shell-injection path that existed when parameters were substituted unescaped.
- The "risky command" confirmation list was expanded (`del`, `format`, `diskpart`, `vssadmin`, `net user`, `reg add/delete`, etc.).
- Registry-value fixes are now backed up (to a JSON log) before deletion, matching the backup-then-delete behavior that shortcut fixes already had.

## Requirements

- Windows 10/11 (some features — registry scan, Wi-Fi profile/startup management, shortcut repair — are Windows-only; the app will run on Linux/macOS with those features disabled).
- Python 3.9+.
- Packages: `customtkinter`, `psutil`, `pillow`.
- Optional: `pystray` (system tray), `pywin32` + `winshell` (shortcut scanning, some Windows automation).

## Quick start

```bash
pip install customtkinter psutil pillow pystray pywin32 winshell
python My_Own_Control_Center_v1_0_0.py
```

On first run, a setup wizard walks through the data folder location. Config is stored at `%APPDATA%\StrallozControlCenter\config.json` (Windows) or `~/.stralloz_control_center/config.json` (other platforms).

## Configuration reference

| Setting (in `config.json`) | Where to change it in-app |
|---|---|
| `app_name` | Settings → Nombre de la app |
| `basic_mode` | Settings → Vista de la app |
| `safety_mode` (`safe` / `advanced`) | Settings → Modo de uso |
| `language` | Settings → Idioma |
| `install_path` | Settings → Ruta de datos / backups |
| `ai_providers`, `ai_active_provider` | AI Assistant page |

## License

All rights reserved. This source is published for review purposes; no license is granted to use, copy, modify, or redistribute it without permission from the copyright holder.
