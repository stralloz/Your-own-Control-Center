# My Own Control Center

**v1.0.0**: a Windows system diagnostics and optimization utility built with CustomTkinter.

> Aren't you tired of paying for software just to get a complementary tool that's somehow missing a lot of features? My Own Control Center is a full Windows PC toolkit with diagnostics, disk and memory tools, a command center, an AI assistant, full rebranding support and a lightweight Basic mode.

## ☕ Support the project

If this project has been useful to you, you can support its development:

[☕ Buy me a coffee](https://paypal.me/Stralloz)

## What this is

A single-file desktop app for Windows that combines the things you'd normally need several separate tools for: a live system dashboard, safe cleanup and optimization, network diagnostics, disk and memory tools, a command reference with guided execution, and a multi-provider AI assistant that can answer questions about the machine it's running on.

It includes two view modes, allowing it to be as simple or as full-featured as the situation requires. See [Basic vs. Advanced mode](#basic-vs-advanced-mode).

The app's display name is stored as a configuration value instead of being hardcoded, so it can be rebranded without modifying the rest of the code. See [Rebranding](#rebranding).

## Features

- **Dashboard:** live CPU, RAM and disk overview, sparkline history, and background alerts for CPU, RAM, disk and connectivity.
- **Safe Optimizer:** scans for temporary files, broken shortcuts, invalid startup entries and stale registry references. Repairs are performed separately from the scan, so nothing is deleted or changed just by scanning.
- **Network Doctor:** gateway, Internet and DNS checks, along with controlled repair actions such as Winsock reset and adapter reset.
- **Disk Center:** volume analysis, large-file finder, safe defragmentation and optimization using `defrag /A` and `/O`, plus read-only CHKDSK.
- **Memory Inspector:** per-process RAM snapshot and working-set trimming on demand.
- **Command Center:** a library of common Windows diagnostic commands such as `ipconfig`, `netsh`, `sfc` and `chkdsk`. It includes editable parameters, a live preview, guided help and inline execution. Parameter values are checked against a list of unsafe characters before anything is run, and destructive commands require additional confirmation.
- **AI Assistant:** ask questions about the current machine. It supports Anthropic Claude, OpenAI, DeepSeek, a local Ollama endpoint and custom OpenAI-compatible providers. API keys are encrypted at rest. See [Security](#security).
- **HTML Reports:** generates a shareable technical report containing system information, disks, top processes and scan results, with properly escaped output.
- **System tray support:** optional minimize-to-tray functionality through `pystray`.

## Basic vs. Advanced mode

Settings → **Vista de la app** toggles between:

| Mode | What's visible |
|---|---|
| **Completa** (default) | Everything listed above. |
| **Básica** | Dashboard, Safe Optimizer, Reports and Settings only. Network Doctor, Disk Center, Memory Inspector, Command Center and the AI Assistant are hidden from the sidebar and the dashboard's quick actions. |

Basic mode is intended for situations where a simpler, lower-risk tool is more appropriate than the complete power-user toolkit. For example, it can be distributed as a companion utility alongside other software.

Switching modes does not delete anything and can be reversed at any time from Settings.

To make Basic mode the default for a particular build, change `DEFAULT_BASIC_MODE` near the top of the file.

## Rebranding

The display name shown in the title bar, sidebar, tray icon, HTML reports and AI assistant system prompt comes from `config["app_name"]` instead of a hardcoded string.

- **End users** can change it at any time from Settings → **Nombre de la app**.
- **Distributors** can change the factory default by editing `DEFAULT_APP_NAME` at the top of the file. No other code changes are needed.

Internal identifiers remain stable across rebrands. This includes the configuration folder under `%APPDATA%`, the default data folder name and the Python class name.

Keeping these identifiers unchanged prevents existing configurations and backups from being moved or orphaned when the visible app name changes.

## Security

This build includes several security improvements over the original prototype:

- AI provider API keys are encrypted at rest with Windows DPAPI and tied to the current Windows account. They are no longer stored as plaintext in `config.json`. Older plaintext keys can still be read and are automatically upgraded the next time they are saved.
- Command Center parameter values are checked against a list of shell metacharacters before being inserted into a command template. The blocked characters include `& | ; \` $ < > ^ " ' % ( )` and newlines. This closes a shell-injection path that existed when parameters were substituted without validation.
- The risky-command confirmation list has been expanded to include commands such as `del`, `format`, `diskpart`, `vssadmin`, `net user`, `reg add` and `reg delete`.
- Registry-value fixes are backed up to a JSON log before deletion, matching the backup-before-delete behavior already used for shortcut fixes.

## Requirements

- Windows 10 or Windows 11.
- Python 3.9 or newer.
- Required packages: `customtkinter`, `psutil` and `pillow`.
- Optional packages: `pystray` for system tray support, plus `pywin32` and `winshell` for shortcut scanning and some Windows automation.

Some features are only available on Windows, including registry scanning, Wi-Fi profile management, startup management and shortcut repair. The app can still run on Linux and macOS with those features disabled.

## Quick start

```bash
pip install customtkinter psutil pillow pystray pywin32 winshell
python My_Own_Control_Center_v1_0_0.py
