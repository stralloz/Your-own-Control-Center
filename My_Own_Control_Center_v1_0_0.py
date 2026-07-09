#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
My Own Control Center
(basado en Stralloz Control Center)
v1.0.0 edition

Cambios v1.0.0:
- Nombre de marca desacoplado del codigo: por defecto "My Own Control Center",
  editable en Configuracion en cualquier momento (config["app_name"]) y
  configurable de fabrica via DEFAULT_APP_NAME para quien distribuya su
  propia edicion.
- Vista de la app con dos modos: Completa (todo lo que ya existia) y Basica
  (dashboard + limpieza segura + reportes + configuracion), pensada para
  distribuirse como companion ligero de un antivirus sin exponer Red,
  Discos, Memoria, Command Center ni el Asistente IA. Toggle reversible
  desde Configuracion, sin perder datos ni configuracion al cambiar.

Cambios v0.4.3 (revision de seguridad):
- Las API key de los proveedores IA ya no se guardan en texto plano: se cifran
  en disco con DPAPI (Windows) cuando esta disponible.
- Command Center: los valores de parametros se validan contra una lista blanca
  de caracteres antes de insertarse en la plantilla del comando, cerrando la
  via de inyeccion de shell que existia al construir el comando con .format().
- Lista de patrones "riesgosos" ampliada (del, format, diskpart, vssadmin,
  bcdedit, wmic, reg add/delete, net user, netsh advfirewall, etc.).
- SystemCleaner.fix_issue ahora respalda el valor de registro antes de
  eliminarlo, igual que ya se hacia con los accesos directos.
- Import explicito de urllib.error (antes se usaba via efecto colateral de
  importar urllib.request).
- DiskManager.find_large_files ya no reordena toda la lista en cada archivo
  encontrado (insercion ordenada en vez de sort() repetido).

Cambios v0.4.2:
- Sidebar con navegación dentro de CTkScrollableFrame, manteniendo marca y footer fijos.
- Asistente IA flexible con proveedores configurables: Anthropic/Claude, OpenAI-compatible, DeepSeek, Ollama/local y custom.
- Dropdown de proveedor IA, edición de endpoint/modelo/key y botones para añadir/eliminar proveedores.
- Asistente IA integrado (Claude API) con contexto del sistema en tiempo real.
- Bug fix: _set_ctk_textbox dejaba widgets editables (state="normal" → "disabled").
- Dashboard optimizado: actualiza valores sin destruir/recrear widgets cada 3.5s.
- Sistema de alertas automáticas en background (CPU, disco, red, RAM).
- Historial sparkline de CPU y RAM en el dashboard.
- Nav group 'IA' con página dedicada al asistente.
- I18N extendido para nuevas secciones.
"""

from __future__ import annotations

import base64
import bisect
import collections
import ctypes
import ctypes.wintypes
import json
import locale
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

# Nombre de marca por defecto. Editable luego desde Configuracion dentro de la
# app (se guarda en config["app_name"]); quien distribuya/rebrande la
# herramienta puede tambien cambiar este default de fabrica en una sola linea.
# Se define aqui arriba (y no junto a APP_VERSION) porque el instalador de
# dependencias puede ejecutarse -y necesita el nombre- antes de que el resto
# del modulo (incluida la seccion de estilo) se haya terminado de definir.
DEFAULT_APP_NAME = "My Own Control Center"

# Modo por defecto para una instalacion nueva sin config.json todavia.
# False = arranca en modo Completo (todo lo que ya existia: red, disco,
# memoria, command center, IA). True = arranca en modo Basico (solo
# dashboard + limpieza segura + reportes + configuracion), pensado para
# distribuirse como companion ligero de un antivirus. Es editable por el
# usuario en Configuracion en cualquier momento; esto solo fija el arranque
# inicial para quien compile/distribuya su propia edicion.
DEFAULT_BASIC_MODE = False

# Paginas visibles cuando basic_mode esta activo. Todo lo que no este en esta
# lista (red, disco, memoria, command center, asistente IA) queda oculto del
# menu lateral y de los accesos rapidos del dashboard, porque son las
# funciones mas "power user" / con mayor superficie de riesgo o confusion
# para alguien que solo espera un limpiador simple.
BASIC_MODE_VISIBLE_PAGES = {"dashboard", "optimizer", "reports", "settings"}


# =============================================================================
# DEPENDENCIAS
# =============================================================================
def _check_required_dependencies() -> None:
    """Instala/avisa dependencias visuales esenciales antes de importar CTk."""
    required = {
        "customtkinter": "customtkinter",
        "psutil": "psutil",
        "PIL": "pillow",
    }
    missing = []
    for import_name, pip_name in required.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        _show_dependency_installer(missing)
        sys.exit(0)


def _show_dependency_installer(missing_packages: List[str]) -> None:
    """Muestra dependencias faltantes sin ejecutar instaladores desde la app.

    En versiones empaquetadas con PyInstaller las dependencias van incluidas. Para
    ejecutar desde codigo fuente, usa run_source_v0_3_1.bat o instala el archivo
    requirements. Evitar auto-instalar paquetes desde la aplicacion reduce alertas
    heuristicas de antivirus en el primer lanzamiento.
    """
    root = tk.Tk()
    root.title(f"{DEFAULT_APP_NAME} - Dependencias")
    root.geometry("640x360")
    root.configure(bg="#0f172a")

    frame = tk.Frame(root, bg="#0f172a")
    frame.pack(expand=True, fill="both", padx=22, pady=22)

    tk.Label(
        frame,
        text="Faltan dependencias necesarias",
        font=("Segoe UI", 17, "bold"),
        fg="white",
        bg="#0f172a",
    ).pack(anchor="w", pady=(0, 8))
    tk.Label(
        frame,
        text="Instala las dependencias antes de ejecutar desde código fuente:",
        font=("Segoe UI", 10),
        fg="#cbd5e1",
        bg="#0f172a",
    ).pack(anchor="w")
    tk.Label(
        frame,
        text="\n".join(f"• {pkg}" for pkg in missing_packages),
        font=("Consolas", 11),
        fg="#fbbf24",
        bg="#0f172a",
        justify="left",
    ).pack(anchor="w", pady=10)

    cmd = "python -m pip install -r requirements_StrallozControlCenter_v0_3_1.txt"
    output = tk.Text(frame, height=4, bg="#020617", fg="#e5e7eb", font=("Consolas", 10), relief="flat")
    output.pack(fill="x", pady=10)
    output.insert("1.0", cmd)
    output.configure(state="disabled")

    tk.Button(
        frame,
        text="Cerrar",
        command=root.destroy,
        bg="#2563eb",
        fg="white",
        relief="flat",
        padx=18,
        pady=8,
        font=("Segoe UI", 10, "bold"),
    ).pack(side="left", pady=6)
    root.mainloop()


_check_required_dependencies()

import customtkinter as ctk
import psutil
from PIL import Image, ImageDraw, ImageTk

try:
    import pystray  # type: ignore

    HAS_TRAY = True
except Exception:
    pystray = None
    HAS_TRAY = False

if IS_WINDOWS:
    try:
        import winreg  # type: ignore

        HAS_WINREG = True
    except Exception:
        winreg = None
        HAS_WINREG = False

    try:
        import winshell  # type: ignore
        from win32com.client import Dispatch  # type: ignore

        HAS_WINDOWS_AUTOMATION = True
    except Exception:
        winshell = None
        Dispatch = None
        HAS_WINDOWS_AUTOMATION = False
else:
    winreg = None
    winshell = None
    Dispatch = None
    HAS_WINREG = False
    HAS_WINDOWS_AUTOMATION = False


# =============================================================================
# ESTILO
# =============================================================================
APP_VERSION = "1.0.0"

COLORS = {
    "bg": "#0b1220",
    "surface": "#111827",
    "surface2": "#1f2937",
    "surface3": "#243244",
    "border": "#334155",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
    "accent": "#3b82f6",
    "accent2": "#22c55e",
    "warn": "#f59e0b",
    "danger": "#ef4444",
    "purple": "#8b5cf6",
}

ctk.set_default_color_theme("blue")
ctk.set_appearance_mode("dark")


# =============================================================================
# IDIOMAS / TEXTOS BASE
# =============================================================================
I18N: Dict[str, Dict[str, str]] = {
    "es": {
        "app_subtitle": "Centro de Control",
        "status_ready": "Listo",
        "nav_group_home": "Inicio",
        "nav_group_diagnostics": "Diagnóstico",
        "nav_group_optimization": "Optimización",
        "nav_group_tools": "Herramientas",
        "nav_group_system": "Sistema",
        "nav_dashboard": "Panel principal",
        "nav_network": "Red",
        "nav_disk": "Discos",
        "nav_memory": "Memoria",
        "nav_optimizer": "Optimización segura",
        "nav_commands": "Centro de comandos",
        "nav_power": "Energía y sesión",
        "nav_reports": "Reportes",
        "nav_settings": "Configuración",
        "dashboard_title": "Panel principal",
        "dashboard_subtitle": "Vista general del equipo y accesos rápidos a las herramientas principales.",
        "optimizer_title": "Optimización segura",
        "optimizer_subtitle": "Escanea primero, repara después. El escaneo no borra archivos ni modifica el registro.",
        "network_title": "Diagnóstico de red",
        "network_subtitle": "Pruebas de gateway, Internet, DNS y acciones de reparación controladas.",
        "disk_title": "Discos",
        "disk_subtitle": "Analiza espacio, encuentra archivos grandes y optimiza volúmenes con acciones separadas y confirmadas.",
        "memory_title": "Memoria",
        "memory_subtitle": "Analiza uso de RAM y libera working set bajo demanda. No es un acelerador mágico; úsalo con criterio.",
        "commands_title": "Centro de comandos",
        "commands_subtitle": "Biblioteca de comandos con parámetros editables, vista previa, ejecución integrada y ayuda contextual con ?.",
        "power_title": "Energía y sesión",
        "power_subtitle": "Control de apagado/reinicio, temporizador, bloqueo de sesión y herramientas rápidas.",
        "reports_title": "Reportes",
        "reports_subtitle": "Genera reportes técnicos en HTML para soporte, clientes o respaldo propio.",
        "settings_title": "Configuración",
        "settings_subtitle": "Idioma, modo seguro, datos, backups, tema y comportamiento de cierre.",
        "quick_actions": "Acciones rápidas",
        "scan_system": "🧹 Escanear sistema",
        "fix_detected": "✅ Reparar issues detectados",
        "open_commands": "Abrir centro de comandos",
        "settings_preferences": "Preferencias",
        "language": "Idioma:",
        "safety_mode": "Modo de uso:",
        "mode_safe": "Seguro",
        "mode_advanced": "Avanzado",
        "advanced_required_title": "Modo avanzado requerido",
        "advanced_required_message": "Esta acción puede modificar el sistema. Activa el modo Avanzado en Configuración para usarla.",
        "generate_html_report": "Generar reporte HTML",
        "open_reports_folder": "Abrir carpeta de reportes",
        "last_report": "Último reporte",
        "report_ready": "Reporte generado correctamente",
        "nav_group_ai": "Asistente",
        "nav_ai": "Asistente IA",
        "ai_title": "Asistente IA",
        "ai_subtitle": "Haz preguntas técnicas sobre tu sistema. El asistente tiene acceso al contexto en tiempo real.",
        "ai_placeholder": "Ej: ¿Por qué está lenta mi red? ¿Qué proceso consume más RAM?",
        "ai_send": "Enviar",
        "ai_clear": "Limpiar chat",
        "ai_thinking": "Analizando...",
        "ai_context_label": "Contexto del sistema enviado al asistente:",
        "alerts_title": "Alertas del sistema",
        "alert_cpu": "⚠️ CPU alta",
        "alert_ram": "⚠️ RAM alta",
        "alert_disk": "⚠️ Disco casi lleno",
        "alert_net": "⚠️ Sin conexión a internet",
    },
    "en": {
        "app_subtitle": "Control Center",
        "status_ready": "Ready",
        "nav_group_home": "Home",
        "nav_group_diagnostics": "Diagnostics",
        "nav_group_optimization": "Optimization",
        "nav_group_tools": "Tools",
        "nav_group_system": "System",
        "nav_dashboard": "Dashboard",
        "nav_network": "Network",
        "nav_disk": "Disks",
        "nav_memory": "Memory",
        "nav_optimizer": "Safe Optimization",
        "nav_commands": "Command Center",
        "nav_power": "Power & Session",
        "nav_reports": "Reports",
        "nav_settings": "Settings",
        "dashboard_title": "Dashboard",
        "dashboard_subtitle": "System overview and quick access to the main tools.",
        "optimizer_title": "Safe Optimization",
        "optimizer_subtitle": "Scan first, fix later. The scan does not delete files or modify the registry.",
        "network_title": "Network Diagnostics",
        "network_subtitle": "Gateway, Internet, DNS tests and controlled repair actions.",
        "disk_title": "Disks",
        "disk_subtitle": "Analyze space, find large files and optimize volumes with separated confirmed actions.",
        "memory_title": "Memory",
        "memory_subtitle": "Analyze RAM usage and release working sets on demand. Not a magic accelerator; use it carefully.",
        "commands_title": "Command Center",
        "commands_subtitle": "Command library with editable parameters, preview, integrated execution and contextual ? help.",
        "power_title": "Power & Session",
        "power_subtitle": "Shutdown/restart control, timer, session lock and quick tools.",
        "reports_title": "Reports",
        "reports_subtitle": "Generate technical HTML reports for support, clients or your own records.",
        "settings_title": "Settings",
        "settings_subtitle": "Language, safe mode, data, backups, theme and closing behavior.",
        "quick_actions": "Quick actions",
        "scan_system": "🧹 Scan system",
        "fix_detected": "✅ Fix detected issues",
        "open_commands": "Open Command Center",
        "settings_preferences": "Preferences",
        "language": "Language:",
        "safety_mode": "Usage mode:",
        "mode_safe": "Safe",
        "mode_advanced": "Advanced",
        "advanced_required_title": "Advanced mode required",
        "advanced_required_message": "This action can modify the system. Enable Advanced mode in Settings to use it.",
        "generate_html_report": "Generate HTML report",
        "open_reports_folder": "Open reports folder",
        "last_report": "Last report",
        "report_ready": "Report generated successfully",
        "nav_group_ai": "Assistant",
        "nav_ai": "AI Assistant",
        "ai_title": "AI Assistant",
        "ai_subtitle": "Ask technical questions about your system. The assistant has access to real-time context.",
        "ai_placeholder": "E.g.: Why is my network slow? Which process uses the most RAM?",
        "ai_send": "Send",
        "ai_clear": "Clear chat",
        "ai_thinking": "Analyzing...",
        "ai_context_label": "System context sent to assistant:",
        "alerts_title": "System alerts",
        "alert_cpu": "⚠️ High CPU",
        "alert_ram": "⚠️ High RAM",
        "alert_disk": "⚠️ Disk almost full",
        "alert_net": "⚠️ No internet connection",
    },
    "de": {
        "app_subtitle": "Kontrollzentrum",
        "status_ready": "Bereit",
        "nav_group_home": "Start",
        "nav_group_diagnostics": "Diagnose",
        "nav_group_optimization": "Optimierung",
        "nav_group_tools": "Werkzeuge",
        "nav_group_system": "System",
        "nav_dashboard": "Übersicht",
        "nav_network": "Netzwerk",
        "nav_disk": "Datenträger",
        "nav_memory": "Speicher",
        "nav_optimizer": "Sichere Optimierung",
        "nav_commands": "Befehlszentrum",
        "nav_power": "Energie und Sitzung",
        "nav_reports": "Berichte",
        "nav_settings": "Einstellungen",
        "dashboard_title": "Übersicht",
        "dashboard_subtitle": "Systemüberblick und Schnellzugriff auf die wichtigsten Werkzeuge.",
        "optimizer_title": "Sichere Optimierung",
        "optimizer_subtitle": "Erst scannen, danach reparieren. Der Scan löscht keine Dateien und ändert nicht die Registry.",
        "network_title": "Netzwerkdiagnose",
        "network_subtitle": "Gateway-, Internet-, DNS-Tests und kontrollierte Reparaturaktionen.",
        "disk_title": "Datenträger",
        "disk_subtitle": "Speicher analysieren, große Dateien finden und Volumes mit bestätigten Aktionen optimieren.",
        "memory_title": "Speicher",
        "memory_subtitle": "RAM-Nutzung analysieren und Working Sets bei Bedarf freigeben. Kein Wundermittel; mit Bedacht verwenden.",
        "commands_title": "Befehlszentrum",
        "commands_subtitle": "Befehlsbibliothek mit editierbaren Parametern, Vorschau, integrierter Ausführung und kontextbezogener ? Hilfe.",
        "power_title": "Energie und Sitzung",
        "power_subtitle": "Herunterfahren/Neustart, Timer, Sitzungssperre und Schnellwerkzeuge.",
        "reports_title": "Berichte",
        "reports_subtitle": "Technische HTML-Berichte für Support, Kunden oder eigene Dokumentation erstellen.",
        "settings_title": "Einstellungen",
        "settings_subtitle": "Sprache, sicherer Modus, Daten, Backups, Design und Schließverhalten.",
        "quick_actions": "Schnellaktionen",
        "scan_system": "🧹 System scannen",
        "fix_detected": "✅ Erkannte Probleme beheben",
        "open_commands": "Befehlszentrum öffnen",
        "settings_preferences": "Einstellungen",
        "language": "Sprache:",
        "safety_mode": "Nutzungsmodus:",
        "mode_safe": "Sicher",
        "mode_advanced": "Erweitert",
        "advanced_required_title": "Erweiterter Modus erforderlich",
        "advanced_required_message": "Diese Aktion kann das System ändern. Aktiviere den erweiterten Modus in den Einstellungen, um sie zu verwenden.",
        "generate_html_report": "HTML-Bericht erstellen",
        "open_reports_folder": "Berichtsordner öffnen",
        "last_report": "Letzter Bericht",
        "report_ready": "Bericht erfolgreich erstellt",
        "nav_group_ai": "Assistent",
        "nav_ai": "KI-Assistent",
        "ai_title": "KI-Assistent",
        "ai_subtitle": "Stellen Sie technische Fragen zu Ihrem System. Der Assistent hat Zugriff auf Echtzeitkontext.",
        "ai_placeholder": "Z.B.: Warum ist mein Netzwerk langsam? Welcher Prozess verbraucht am meisten RAM?",
        "ai_send": "Senden",
        "ai_clear": "Chat leeren",
        "ai_thinking": "Analysiere...",
        "ai_context_label": "An den Assistenten gesendeter Systemkontext:",
        "alerts_title": "Systemwarnungen",
        "alert_cpu": "⚠️ Hohe CPU",
        "alert_ram": "⚠️ Hoher RAM",
        "alert_disk": "⚠️ Datenträger fast voll",
        "alert_net": "⚠️ Keine Internetverbindung",
    },
}


# =============================================================================
# DETECCIÓN DE IDIOMA DEL SISTEMA
# =============================================================================
def detect_os_language() -> str:
    """Devuelve es/de/en segun el idioma nativo del sistema operativo.

    Prioridad:
    - Windows UI locale cuando esta disponible.
    - locale de Python como respaldo.
    - Ingles si no es espanol ni aleman.
    """
    candidates: List[str] = []

    if IS_WINDOWS:
        try:
            buffer = ctypes.create_unicode_buffer(85)
            # GetUserDefaultLocaleName devuelve valores tipo es-CL, es-ES, de-DE, en-US.
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
                candidates.append(buffer.value)
        except Exception:
            pass

    try:
        loc = locale.getlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:
        pass

    try:
        loc = locale.getdefaultlocale()[0]  # type: ignore[call-arg]
        if loc:
            candidates.append(loc)
    except Exception:
        pass

    for raw in candidates:
        normalized = str(raw).replace("_", "-").lower().strip()
        primary = normalized.split("-")[0]
        if primary == "es":
            return "es"
        if primary == "de":
            return "de"
    return "en"


def resolve_language(config: Dict[str, Any]) -> str:
    """Resuelve el idioma efectivo de la app.

    language='auto' o language_follow_os=True usan el idioma del sistema.
    Cualquier idioma no soportado cae a ingles, salvo espanol/aleman.
    """
    if bool(config.get("language_follow_os", False)) or str(config.get("language", "auto")).lower() == "auto":
        return detect_os_language()
    lang = str(config.get("language", "en")).lower().strip()
    return lang if lang in I18N else "en"


# =============================================================================
# CONFIGURACIÓN
# =============================================================================
class ConfigManager:
    @staticmethod
    def config_dir() -> Path:
        if IS_WINDOWS and os.getenv("APPDATA"):
            return Path(os.getenv("APPDATA", "")) / "StrallozControlCenter"
        return Path.home() / ".stralloz_control_center"

    @classmethod
    def config_file(cls) -> Path:
        return cls.config_dir() / "config.json"

    @classmethod
    def default_config(cls) -> Dict[str, Any]:
        return {
            "app_name": DEFAULT_APP_NAME,
            "basic_mode": DEFAULT_BASIC_MODE,
            "install_path": str(Path.home() / "StrallozData"),
            "close_to_tray": False,
            "theme": "dark",
            "backup_enabled": True,
            "first_run": True,
            "language": "auto",
            "language_follow_os": True,
            "safety_mode": "safe",
            "temp_file_min_age_hours": 24,
            "ai_active_provider": "Claude (Anthropic)",
            "ai_providers": {},
        }

    @classmethod
    def ensure_config_dir(cls) -> None:
        cls.config_file().parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        cls.ensure_config_dir()
        config_file = cls.config_file()
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                config = cls.default_config()
                config.update(loaded)
                return config
            except Exception:
                return cls.default_config()
        return cls.default_config()

    @classmethod
    def save_config(cls, config: Dict[str, Any]) -> None:
        cls.ensure_config_dir()
        with open(cls.config_file(), "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)


class SystemTheme:
    @staticmethod
    def get_windows_theme() -> str:
        if not IS_WINDOWS or not HAS_WINREG:
            return "dark"
        try:
            key = winreg.OpenKey(  # type: ignore[union-attr]
                winreg.HKEY_CURRENT_USER,  # type: ignore[union-attr]
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")  # type: ignore[union-attr]
            winreg.CloseKey(key)  # type: ignore[union-attr]
            return "light" if value == 1 else "dark"
        except Exception:
            return "dark"

    @staticmethod
    def apply_theme(theme_setting: str) -> None:
        if theme_setting == "system":
            ctk.set_appearance_mode(SystemTheme.get_windows_theme())
        else:
            ctk.set_appearance_mode(theme_setting)


# =============================================================================
# HELPERS DE SISTEMA / ENERGÍA
# =============================================================================
def hidden_subprocess_kwargs(capture: bool = True) -> Dict[str, Any]:
    """Kwargs para ejecutar procesos internos sin ventanas CMD/PowerShell visibles.

    Importante: usar solo para operaciones internas. Los botones "Abrir CMD" y
    "Abrir PowerShell" deben seguir abriendo consola visible por decisión del usuario.
    """
    kwargs: Dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    if IS_WINDOWS:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def run_cmd(cmd_list: List[str], on_error: Optional[Any] = None, hidden: bool = False) -> bool:
    try:
        if hidden:
            subprocess.Popen(cmd_list, **hidden_subprocess_kwargs(capture=False))
        else:
            subprocess.Popen(cmd_list)
        return True
    except Exception as exc:
        if on_error:
            on_error(str(exc))
        return False


def cmd_shutdown(seconds: int = 0) -> List[str]:
    if IS_WINDOWS:
        return ["shutdown", "/s", "/t", str(seconds)]
    return ["shutdown", "-h", f"+{seconds // 60}" if seconds else "now"]


def cmd_restart(seconds: int = 0) -> List[str]:
    if IS_WINDOWS:
        return ["shutdown", "/r", "/t", str(seconds)]
    return ["shutdown", "-r", f"+{seconds // 60}" if seconds else "now"]


def cmd_cancel_shutdown() -> List[str]:
    if IS_WINDOWS:
        return ["shutdown", "/a"]
    return ["shutdown", "-c"]


def cmd_lock() -> List[str]:
    if IS_WINDOWS:
        return ["rundll32.exe", "user32.dll,LockWorkStation"]
    if IS_MAC:
        return ["pmset", "displaysleepnow"]
    return ["xdg-screensaver", "lock"]


def cmd_sleep() -> List[str]:
    if IS_WINDOWS:
        return ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
    if IS_MAC:
        return ["pmset", "sleepnow"]
    return ["systemctl", "suspend"]


def format_bytes(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


# =============================================================================
# OPTIMIZADOR SEGURO
# =============================================================================
SCAN_CATEGORIES = {
    "temp_files": "Archivos temporales",
    "shortcuts": "Accesos directos rotos",
    "startup": "Entradas de inicio inválidas",
    "registry": "Referencias de registro obsoletas",
}


class SystemCleaner:
    """
    Scanner/optimizer con separación real entre detectar y reparar.
    A diferencia del prototipo original, scan_* no borra archivos ni toca registro.
    """

    def __init__(self, backup_path: Path, temp_file_min_age_hours: int = 24):
        self.backup_path = backup_path
        self.backup_path.mkdir(parents=True, exist_ok=True)
        self.temp_file_min_age_hours = max(0, int(temp_file_min_age_hours))

    def set_backup_path(self, path: Path) -> None:
        self.backup_path = path
        self.backup_path.mkdir(parents=True, exist_ok=True)

    def _issue(self, category: str, kind: str, title: str, path: str = "", **extra: Any) -> Dict[str, Any]:
        data = {"category": category, "kind": kind, "title": title, "path": path}
        data.update(extra)
        return data

    # ---------- TEMP ----------
    def _temp_locations(self) -> List[str]:
        locations = [
            tempfile.gettempdir(),
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
        ]
        if IS_WINDOWS:
            locations.extend(
                [
                    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Temp"),
                    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
                ]
            )
        clean: List[str] = []
        for loc in locations:
            if loc and os.path.exists(loc) and loc not in clean:
                clean.append(loc)
        return clean

    def scan_temp_files(self, max_items: int = 25000) -> Tuple[List[Dict[str, Any]], List[str]]:
        issues: List[Dict[str, Any]] = []
        errors: List[str] = []
        cutoff = time.time() - (self.temp_file_min_age_hours * 3600)

        for location in self._temp_locations():
            if len(issues) >= max_items:
                break
            try:
                for root, dirs, files in os.walk(location):
                    # Evita seguir en árboles enormes si ya alcanzamos el límite.
                    if len(issues) >= max_items:
                        break
                    for file_name in files:
                        if len(issues) >= max_items:
                            break
                        file_path = os.path.join(root, file_name)
                        try:
                            stat = os.stat(file_path)
                            if stat.st_mtime <= cutoff:
                                issues.append(
                                    self._issue(
                                        "temp_files",
                                        "temp_file",
                                        "Archivo temporal antiguo",
                                        file_path,
                                        size=stat.st_size,
                                        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                                    )
                                )
                        except (FileNotFoundError, PermissionError, OSError):
                            continue
            except Exception as exc:
                errors.append(f"Error escaneando {location}: {exc}")
        return issues, errors

    # ---------- SHORTCUTS ----------
    def _shortcut_locations(self) -> List[str]:
        if not IS_WINDOWS or not HAS_WINDOWS_AUTOMATION:
            return []
        locations: List[str] = []
        try:
            locations.extend([winshell.desktop(), winshell.programs(), winshell.startup()])  # type: ignore[union-attr]
        except Exception:
            pass
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            locations.extend(
                [
                    os.path.join(appdata, r"Microsoft\Internet Explorer\Quick Launch"),
                    os.path.join(appdata, r"Microsoft\Windows\Start Menu"),
                ]
            )
        return [loc for loc in dict.fromkeys(locations) if loc and os.path.exists(loc)]

    def scan_broken_shortcuts(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        issues: List[Dict[str, Any]] = []
        errors: List[str] = []
        if not IS_WINDOWS:
            return issues, ["Accesos directos .lnk solo aplica en Windows."]
        if not HAS_WINDOWS_AUTOMATION:
            return issues, ["Faltan winshell/pywin32; no se pudieron analizar accesos directos."]
        try:
            shell = Dispatch("WScript.Shell")  # type: ignore[misc]
        except Exception as exc:
            return issues, [f"No se pudo iniciar WScript.Shell: {exc}"]

        for location in self._shortcut_locations():
            try:
                for root, dirs, files in os.walk(location):
                    for file_name in files:
                        if not file_name.lower().endswith(".lnk"):
                            continue
                        shortcut_path = os.path.join(root, file_name)
                        try:
                            shortcut = shell.CreateShortcut(shortcut_path)
                            target = os.path.expandvars(shortcut.TargetPath or "")
                            if not target or not os.path.exists(target):
                                issues.append(
                                    self._issue(
                                        "shortcuts",
                                        "shortcut",
                                        "Acceso directo sin destino válido",
                                        shortcut_path,
                                        target=target,
                                    )
                                )
                        except Exception as exc:
                            errors.append(f"Error procesando {shortcut_path}: {exc}")
            except Exception as exc:
                errors.append(f"Error escaneando {location}: {exc}")
        return issues, errors

    # ---------- REGISTRY / STARTUP ----------
    @staticmethod
    def _extract_executable_path(command: Any) -> Optional[str]:
        if not isinstance(command, str):
            return None
        text = os.path.expandvars(command.strip())
        if not text:
            return None
        lower = text.lower()
        # Entradas válidas que son comandos del sistema y no rutas directas.
        system_prefixes = (
            "rundll32",
            "regsvr32",
            "cmd ",
            "cmd.exe",
            "powershell",
            "pwsh",
            "explorer",
            "msiexec",
            "javaw",
            "schtasks",
        )
        if lower.startswith(system_prefixes):
            return None
        if text.startswith('"'):
            end = text.find('"', 1)
            if end > 1:
                return text[1:end]
        match = re.match(r"^(.+?\.(?:exe|bat|cmd|ps1|vbs|js|com))(?:\s|$)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        first = text.split()[0]
        return first if (":" in first or "\\" in first or "/" in first) else None

    def _reg_roots(self) -> Dict[str, Any]:
        if not HAS_WINREG:
            return {}
        return {
            "HKCU": winreg.HKEY_CURRENT_USER,  # type: ignore[union-attr]
            "HKLM": winreg.HKEY_LOCAL_MACHINE,  # type: ignore[union-attr]
        }

    def scan_startup_entries(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        issues: List[Dict[str, Any]] = []
        errors: List[str] = []
        if not IS_WINDOWS or not HAS_WINREG:
            return issues, ["Registro de inicio solo disponible en Windows."]

        startup_keys = [
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        ]
        roots = self._reg_roots()
        for root_name, subkey in startup_keys:
            try:
                key = winreg.OpenKey(roots[root_name], subkey, 0, winreg.KEY_READ)  # type: ignore[union-attr]
                value_count = winreg.QueryInfoKey(key)[1]  # type: ignore[union-attr]
                for index in range(value_count):
                    try:
                        value_name, value_data, _ = winreg.EnumValue(key, index)  # type: ignore[union-attr]
                        executable = self._extract_executable_path(value_data)
                        if executable and not os.path.exists(executable):
                            issues.append(
                                self._issue(
                                    "startup",
                                    "registry_value",
                                    "Entrada de inicio apunta a un ejecutable inexistente",
                                    executable,
                                    root=root_name,
                                    subkey=subkey,
                                    value_name=value_name,
                                    value_data=str(value_data),
                                )
                            )
                    except Exception:
                        continue
                winreg.CloseKey(key)  # type: ignore[union-attr]
            except Exception as exc:
                errors.append(f"No se pudo leer {root_name}\\{subkey}: {exc}")
        return issues, errors

    def scan_registry_references(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        issues: List[Dict[str, Any]] = []
        errors: List[str] = []
        if not IS_WINDOWS or not HAS_WINREG:
            return issues, ["Registro de Windows no disponible en este sistema."]

        roots = self._reg_roots()
        root_name = "HKLM"
        subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\SharedDLLs"
        try:
            key = winreg.OpenKey(roots[root_name], subkey, 0, winreg.KEY_READ)  # type: ignore[union-attr]
            value_count = winreg.QueryInfoKey(key)[1]  # type: ignore[union-attr]
            for index in range(value_count):
                try:
                    value_name, value_data, _ = winreg.EnumValue(key, index)  # type: ignore[union-attr]
                    expanded = os.path.expandvars(str(value_name))
                    if expanded and (":" in expanded or expanded.startswith("\\\\")) and not os.path.exists(expanded):
                        issues.append(
                            self._issue(
                                "registry",
                                "registry_value",
                                "Referencia SharedDLLs apunta a archivo inexistente",
                                expanded,
                                root=root_name,
                                subkey=subkey,
                                value_name=value_name,
                                value_data=str(value_data),
                            )
                        )
                except Exception:
                    continue
            winreg.CloseKey(key)  # type: ignore[union-attr]
        except Exception as exc:
            errors.append(f"No se pudo leer {root_name}\\{subkey}: {exc}")
        return issues, errors

    def scan(self, categories: List[str]) -> Dict[str, Dict[str, Any]]:
        mapping = {
            "temp_files": self.scan_temp_files,
            "shortcuts": self.scan_broken_shortcuts,
            "startup": self.scan_startup_entries,
            "registry": self.scan_registry_references,
        }
        results: Dict[str, Dict[str, Any]] = {}
        for category in categories:
            func = mapping.get(category)
            if not func:
                continue
            issues, errors = func()
            results[category] = {"issues": issues, "errors": errors, "timestamp": datetime.now().isoformat(timespec="seconds")}
        return results

    def _backup_registry_value(self, backup_dir: Path, issue: Dict[str, Any]) -> None:
        """Guarda una copia del valor de registro antes de borrarlo.

        No es un undo automatico de un clic, pero deja el dato necesario
        (root/subkey/value_name/value_data) para restaurarlo a mano, igual que
        fix_issue ya hacia para accesos directos via shutil.copy2.
        """
        try:
            registry_backup_dir = backup_dir / "registry"
            registry_backup_dir.mkdir(parents=True, exist_ok=True)
            entry = {
                "root": issue.get("root"),
                "subkey": issue.get("subkey"),
                "value_name": issue.get("value_name"),
                "value_data": issue.get("value_data"),
                "backed_up_at": datetime.now().isoformat(timespec="seconds"),
            }
            log_file = registry_backup_dir / "deleted_values.jsonl"
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            # No bloquear la reparacion si el respaldo falla: es mejor dejar
            # reparar el issue detectado que dejarlo sin poder repararlo.
            pass

    def fix_issue(self, issue: Dict[str, Any], backup_dir: Optional[Path] = None) -> Tuple[bool, str]:
        kind = issue.get("kind")
        path = issue.get("path", "")
        try:
            if kind == "temp_file":
                if path and os.path.exists(path):
                    os.remove(path)
                return True, "Archivo temporal eliminado"

            if kind == "shortcut":
                if backup_dir and path and os.path.exists(path):
                    shortcuts_dir = backup_dir / "shortcuts"
                    shortcuts_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, shortcuts_dir / Path(path).name)
                if path and os.path.exists(path):
                    os.remove(path)
                return True, "Acceso directo eliminado"

            if kind == "registry_value":
                if not IS_WINDOWS or not HAS_WINREG:
                    return False, "Registro de Windows no disponible"
                roots = self._reg_roots()
                root_name = issue.get("root")
                subkey = issue.get("subkey")
                value_name = issue.get("value_name")
                if root_name not in roots or not subkey or value_name is None:
                    return False, "Issue de registro incompleto"
                if backup_dir:
                    self._backup_registry_value(backup_dir, issue)
                key = winreg.OpenKey(roots[root_name], subkey, 0, winreg.KEY_SET_VALUE)  # type: ignore[union-attr]
                winreg.DeleteValue(key, value_name)  # type: ignore[union-attr]
                winreg.CloseKey(key)  # type: ignore[union-attr]
                return True, f"Valor de registro eliminado: {root_name}\\{subkey}\\{value_name}"

            return False, f"Tipo de issue no soportado: {kind}"
        except Exception as exc:
            return False, str(exc)




# =============================================================================
# DISK CENTER / MEMORY INSPECTOR / NETWORK DOCTOR
# =============================================================================
class DiskManager:
    """Herramientas seguras para analizar y optimizar discos en Windows."""

    @staticmethod
    def list_volumes() -> List[Dict[str, Any]]:
        volumes: List[Dict[str, Any]] = []
        media_map = DiskManager.get_media_type_map()
        for part in psutil.disk_partitions(all=False):
            opts = (part.opts or "").lower()
            if "cdrom" in opts or not part.fstype:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except Exception:
                continue
            drive = part.device.replace('\\', '').replace('/', '').strip()
            drive_letter = drive[:1].upper() if drive else part.mountpoint[:1].upper()
            volumes.append({
                "device": part.device,
                "drive_letter": drive_letter,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "opts": part.opts,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
                "media_type": media_map.get(drive_letter, "Unknown"),
            })
        return volumes

    @staticmethod
    def get_media_type_map() -> Dict[str, str]:
        """Obtiene tipo de disco sin abrir PowerShell/CMD.

        Usa WMI/COM si pywin32 esta disponible. Si no se puede resolver, devuelve
        Unknown; la optimizacion usa defrag /O, que permite a Windows elegir la
        accion adecuada para el volumen.
        """
        if not (IS_WINDOWS and HAS_WINDOWS_AUTOMATION and Dispatch):
            return {}
        result: Dict[str, str] = {}
        try:
            locator = Dispatch("WbemScripting.SWbemLocator")
            cimv2 = locator.ConnectServer(".", r"root\cimv2")

            disk_media: Dict[int, str] = {}
            try:
                storage = locator.ConnectServer(".", r"root\Microsoft\Windows\Storage")
                for disk in storage.ExecQuery("SELECT Number, MediaType FROM MSFT_PhysicalDisk"):
                    try:
                        number = int(getattr(disk, "Number", -1))
                        media_code = int(getattr(disk, "MediaType", 0) or 0)
                        media = {3: "HDD", 4: "SSD", 5: "SCM"}.get(media_code, "Unknown")
                        if number >= 0:
                            disk_media[number] = media
                    except Exception:
                        continue
            except Exception:
                disk_media = {}

            for logical in cimv2.ExecQuery("SELECT DeviceID FROM Win32_LogicalDisk WHERE DriveType=3"):
                try:
                    device_id = str(getattr(logical, "DeviceID", ""))
                    letter = device_id.replace(":", "").strip().upper()
                    if not letter:
                        continue
                    media = "Unknown"
                    for partition in logical.Associators_("Win32_LogicalDiskToPartition"):
                        part_id = str(getattr(partition, "DeviceID", ""))
                        m = re.search(r"Disk #(\d+)", part_id, re.IGNORECASE)
                        if m:
                            media = disk_media.get(int(m.group(1)), "Unknown")
                            break
                    result[letter] = media
                except Exception:
                    continue
        except Exception:
            return {}
        return result

    @staticmethod
    def get_media_type(drive_letter: str) -> str:
        if not drive_letter:
            return "Unknown"
        return DiskManager.get_media_type_map().get(drive_letter.strip(':\\/ ').upper(), "Unknown")

    @staticmethod
    def analyze_volume(drive_letter: str) -> Tuple[int, str]:
        if not IS_WINDOWS:
            return 1, "Analisis de disco implementado para Windows."
        drive = drive_letter.strip(":\\/ ").upper()
        if not drive:
            return 1, "Unidad invalida."
        cmd = ["defrag", f"{drive}:", "/A", "/U", "/V"]
        return run_capture(cmd, timeout=180)

    @staticmethod
    def optimize_volume(drive_letter: str, media_type: str = "Unknown") -> Tuple[int, str]:
        if not IS_WINDOWS:
            return 1, "Optimizacion de disco implementada para Windows."
        drive = drive_letter.strip(":\\/ ").upper()
        if not drive:
            return 1, "Unidad invalida."
        # defrag /O ejecuta la optimizacion apropiada segun el tipo de medio cuando Windows puede detectarlo.
        # Evitamos PowerShell aqui para reducir falsos positivos y ventanas inesperadas en builds PyInstaller.
        return run_capture(["defrag", f"{drive}:", "/O", "/U", "/V"], timeout=900)

    @staticmethod
    def chkdsk_readonly(drive_letter: str) -> Tuple[int, str]:
        if not IS_WINDOWS:
            return 1, "CHKDSK solo aplica en Windows."
        drive = drive_letter.strip(":\\/ ").upper()
        if not drive:
            return 1, "Unidad invalida."
        return run_capture(["chkdsk", f"{drive}:"], timeout=900)

    @staticmethod
    def find_large_files(root_path: str, min_size_mb: int = 500, limit: int = 80) -> Tuple[List[Dict[str, Any]], List[str]]:
        root = os.path.expandvars(os.path.expanduser(root_path.strip()))
        if not root or not os.path.exists(root):
            return [], [f"Ruta no encontrada: {root_path}"]
        min_bytes = max(1, int(min_size_mb)) * 1024 * 1024
        # Mantiene "found"/"sizes" ordenados ascendente por tamaño e inserta con
        # bisect, en vez de hacer found.sort() completo por cada archivo que
        # califica (evita re-ordenar toda la lista en discos con muchos
        # archivos grandes).
        found: List[Dict[str, Any]] = []
        sizes: List[int] = []
        errors: List[str] = []
        for current_root, dirs, files in os.walk(root):
            # Evita carpetas que normalmente generan errores o recorridos enormes en Windows.
            dirs[:] = [d for d in dirs if d.lower() not in {"system volume information", "$recycle.bin"}]
            for file_name in files:
                file_path = os.path.join(current_root, file_name)
                try:
                    size = os.path.getsize(file_path)
                    if size >= min_bytes:
                        idx = bisect.bisect_left(sizes, size)
                        sizes.insert(idx, size)
                        found.insert(idx, {"path": file_path, "size": size})
                        if len(found) > limit:
                            sizes.pop(0)
                            found.pop(0)
                except (PermissionError, FileNotFoundError, OSError):
                    continue
                except Exception as exc:
                    if len(errors) < 10:
                        errors.append(f"{file_path}: {exc}")
        found.reverse()  # de mayor a menor tamaño, igual que antes
        return found, errors


class MemoryManager:
    """Inspector de memoria. El trim usa EmptyWorkingSet en Windows."""

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_SET_QUOTA = 0x0100

    @staticmethod
    def snapshot(limit: int = 25) -> Dict[str, Any]:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        processes: List[Dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "username", "memory_info", "memory_percent", "status"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                rss = int(getattr(mem, "rss", 0) or 0)
                processes.append({
                    "pid": int(info.get("pid") or 0),
                    "name": info.get("name") or "unknown",
                    "username": info.get("username") or "",
                    "rss": rss,
                    "memory_percent": float(info.get("memory_percent") or 0.0),
                    "status": info.get("status") or "",
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        processes.sort(key=lambda item: item["rss"], reverse=True)
        return {"virtual": vm, "swap": swap, "processes": processes[:limit]}

    @staticmethod
    def empty_working_set(pid: int) -> Tuple[bool, str]:
        if not IS_WINDOWS:
            return False, "EmptyWorkingSet esta disponible solo en Windows."
        if pid <= 0:
            return False, "PID invalido."
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            access = MemoryManager.PROCESS_QUERY_INFORMATION | MemoryManager.PROCESS_SET_QUOTA
            handle = kernel32.OpenProcess(access, False, int(pid))
            if not handle:
                err = ctypes.get_last_error()
                return False, f"No se pudo abrir el proceso {pid}. Windows error {err}."
            try:
                ok = bool(psapi.EmptyWorkingSet(handle))
                if ok:
                    return True, f"Working set liberado para PID {pid}."
                err = ctypes.get_last_error()
                return False, f"EmptyWorkingSet fallo para PID {pid}. Windows error {err}."
            finally:
                kernel32.CloseHandle(handle)
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def trim_non_critical(min_rss_mb: int = 150) -> Tuple[int, int, List[str]]:
        min_rss = max(1, int(min_rss_mb)) * 1024 * 1024
        current_pid = os.getpid()
        protected_names = {
            "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
            "lsass.exe", "svchost.exe", "winlogon.exe", "dwm.exe", "fontdrvhost.exe",
        }
        ok_count = 0
        fail_count = 0
        messages: List[str] = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                pid = int(proc.info.get("pid") or 0)
                name = (proc.info.get("name") or "").lower()
                mem = proc.info.get("memory_info")
                rss = int(getattr(mem, "rss", 0) or 0)
                if pid in (0, current_pid) or rss < min_rss or name in protected_names:
                    continue
                ok, msg = MemoryManager.empty_working_set(pid)
                if ok:
                    ok_count += 1
                else:
                    fail_count += 1
                if len(messages) < 40:
                    messages.append(f"{name or pid}: {msg}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as exc:
                fail_count += 1
                if len(messages) < 40:
                    messages.append(str(exc))
        return ok_count, fail_count, messages


class NetworkDoctor:
    """Diagnostico basico de red pensado para soporte TI."""

    @staticmethod
    def _default_gateway_windows() -> str:
        if not IS_WINDOWS:
            return ""
        code, out = run_capture(["cmd", "/c", "ipconfig"], timeout=20)
        if code != 0:
            return ""
        candidates = re.findall(r"(?:Puerta de enlace predeterminada|Default Gateway)[^:]*:\s*([0-9]+(?:\.[0-9]+){3})", out)
        return candidates[0] if candidates else ""

    @staticmethod
    def run_basic_diagnostic() -> str:
        lines: List[str] = []
        lines.append(f"=== Network Doctor {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ===")
        lines.append(f"Host: {platform.node()}")
        lines.append("")
        lines.append("[Interfaces]")
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            for name, st in stats.items():
                ipv4 = []
                for addr in addrs.get(name, []):
                    if getattr(addr, "family", None) == socket.AF_INET:
                        ipv4.append(addr.address)
                lines.append(f"- {name}: {'UP' if st.isup else 'DOWN'} | speed={st.speed} Mbps | IPv4={', '.join(ipv4) or '-'}")
        except Exception as exc:
            lines.append(f"No se pudieron leer interfaces: {exc}")
        lines.append("")
        gateway = NetworkDoctor._default_gateway_windows()
        if gateway:
            lines.append(f"Gateway detectado: {gateway}")
        else:
            lines.append("Gateway detectado: no disponible")
        tests = []
        if gateway:
            tests.append(("Gateway", gateway))
        tests.extend([("Cloudflare DNS", "1.1.1.1"), ("Google DNS", "8.8.8.8"), ("DNS resolve", "google.com")])
        lines.append("")
        lines.append("[Pruebas de conectividad]")
        for label, host in tests:
            if IS_WINDOWS:
                cmd = ["ping", host, "-n", "2"]
            else:
                cmd = ["ping", "-c", "2", host]
            code, out = run_capture(cmd, timeout=20)
            status = "OK" if code == 0 else "FAIL"
            loss_match = re.search(r"(\d+)%\s*(?:loss|perdidos)", out, re.IGNORECASE)
            loss = f" | loss={loss_match.group(1)}%" if loss_match else ""
            avg_match = re.search(r"(?:Media|Average)\s*=\s*([0-9]+ms)", out, re.IGNORECASE)
            avg = f" | avg={avg_match.group(1)}" if avg_match else ""
            lines.append(f"- {label} ({host}): {status}{loss}{avg}")
        lines.append("")
        lines.append("[DNS]")
        try:
            ip = socket.gethostbyname("google.com")
            lines.append(f"google.com -> {ip}")
        except Exception as exc:
            lines.append(f"Fallo resolviendo google.com: {exc}")
        return "\n".join(lines)


def run_capture(cmd: List[str], timeout: int = 120) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, timeout=timeout, **hidden_subprocess_kwargs(capture=True))
        out = (r.stdout or "")
        err = (r.stderr or "")
        joined = out + (("\n" + err) if err else "")
        return int(r.returncode), joined.strip()
    except subprocess.TimeoutExpired:
        return 124, f"Timeout ejecutando: {' '.join(cmd)}"
    except Exception as exc:
        return 1, str(exc)


def run_powershell_hidden(script: str, timeout: int = 120) -> Tuple[int, str]:
    """Ejecuta PowerShell capturando salida sin usar parametros de ventana oculta de PowerShell.

    CREATE_NO_WINDOW/STARTUPINFO ya controlan la consola del proceso hijo en
    Windows. Evitamos parametros explicitos de ventana oculta porque algunos
    antivirus lo ponderan negativamente cuando el EXE es nuevo y no firmado.
    """
    return run_capture(
        [
            "powershell.exe" if IS_WINDOWS else "powershell",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=timeout,
    )

# =============================================================================
# BIBLIOTECA DE COMANDOS DEL PANEL ORIGINAL
# =============================================================================
WIN_COMMANDS = [{'cat': '🌐 Red / Network / Netzwerk',
  'name': 'ipconfig',
  'shell': 'cmd',
  'desc': {'es': 'Muestra la configuración IP de todos los adaptadores. /all incluye MAC, DHCP y DNS.',
           'en': 'Shows IP configuration for all adapters. /all includes MAC, DHCP and DNS.',
           'de': 'Zeigt die IP-Konfiguration aller Adapter. /all zeigt MAC, DHCP und DNS.'},
  'template': 'ipconfig {flags}',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/all',
              'hint': '/all  /release  /renew  /flushdns  /displaydns'}]},
 {'cat': '🌐 Red / Network / Netzwerk',
  'name': 'ping',
  'shell': 'cmd',
  'desc': {'es': 'Envía paquetes ICMP para comprobar conectividad y latencia con un host.',
           'en': 'Sends ICMP packets to check connectivity and latency to a host.',
           'de': 'Sendet ICMP-Pakete zur Konnektivitäts- und Latenzmessung.'},
  'template': 'ping {host} -n {count} {extra}',
  'params': [{'label': {'es': 'Host / IP', 'en': 'Host / IP', 'de': 'Host / IP'},
              'key': 'host',
              'default': 'google.com',
              'hint': 'IP or domain'},
             {'label': {'es': 'Paquetes', 'en': 'Packets', 'de': 'Pakete'},
              'key': 'count',
              'default': '4',
              'hint': 'Number of pings'},
             {'label': {'es': 'Extra', 'en': 'Extra', 'de': 'Extra'},
              'key': 'extra',
              'default': '',
              'hint': '-t (continuous)  -l 1000 (size)'}]},
 {'cat': '🌐 Red / Network / Netzwerk',
  'name': 'tracert',
  'shell': 'cmd',
  'desc': {'es': 'Traza la ruta de paquetes hacia un destino, mostrando cada salto (router).',
           'en': 'Traces the packet route to a destination, showing each hop.',
           'de': 'Verfolgt den Paketweg zum Ziel und zeigt jeden Hop.'},
  'template': 'tracert {host}',
  'params': [{'label': {'es': 'Host / IP', 'en': 'Host / IP', 'de': 'Host / IP'},
              'key': 'host',
              'default': '8.8.8.8',
              'hint': ''}]},
 {'cat': '🌐 Red / Network / Netzwerk',
  'name': 'netstat',
  'shell': 'cmd',
  'desc': {'es': 'Muestra conexiones de red activas, puertos en escucha y estadísticas.',
           'en': 'Shows active network connections, listening ports and statistics.',
           'de': 'Zeigt aktive Netzwerkverbindungen, lauschende Ports und Statistiken.'},
  'template': 'netstat {flags}',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '-ano',
              'hint': '-a (all)  -n (numeric)  -o (PID)  -b (process)  -e (stats)'}]},
 {'cat': '🌐 Red / Network / Netzwerk',
  'name': 'nslookup',
  'shell': 'cmd',
  'desc': {'es': 'Consulta servidores DNS para resolver nombres de dominio a IPs.',
           'en': 'Queries DNS servers to resolve domain names to IPs.',
           'de': 'Fragt DNS-Server ab um Domainnamen in IPs aufzulösen.'},
  'template': 'nslookup {host} {server}',
  'params': [{'label': {'es': 'Dominio', 'en': 'Domain', 'de': 'Domäne'},
              'key': 'host',
              'default': 'google.com',
              'hint': ''},
             {'label': {'es': 'Servidor DNS', 'en': 'DNS Server', 'de': 'DNS-Server'},
              'key': 'server',
              'default': '',
              'hint': '8.8.8.8 / 1.1.1.1'}]},
 {'cat': '🌐 Red / Network / Netzwerk',
  'name': 'netsh wlan',
  'shell': 'cmd',
  'desc': {'es': 'Gestión avanzada de Wi-Fi: ver perfiles y contraseñas guardadas.',
           'en': 'Advanced Wi-Fi management: view profiles and saved passwords.',
           'de': 'Erweiterte WLAN-Verwaltung: Profile und gespeicherte Passwörter anzeigen.'},
  'template': 'netsh wlan {sub}',
  'params': [{'label': {'es': 'Subcomando', 'en': 'Subcommand', 'de': 'Unterbefehl'},
              'key': 'sub',
              'default': 'show profiles',
              'hint': 'show profiles  show profile name=WIFI key=clear  show interfaces'}]},
 {'cat': '⚙️ Sistema / System / System',
  'name': 'systeminfo',
  'shell': 'cmd',
  'desc': {'es': 'Información detallada del sistema: SO, RAM, parches, dominio, arranque.',
           'en': 'Detailed system info: OS, RAM, patches, domain, boot time.',
           'de': 'Detaillierte Systeminformationen: OS, RAM, Patches, Domäne, Startzeit.'},
  'template': 'systeminfo',
  'params': []},
 {'cat': '⚙️ Sistema / System / System',
  'name': 'tasklist',
  'shell': 'cmd',
  'desc': {'es': 'Lista todos los procesos en ejecución con PID y uso de memoria.',
           'en': 'Lists all running processes with PID and memory usage.',
           'de': 'Listet alle laufenden Prozesse mit PID und Speichernutzung.'},
  'template': 'tasklist {flags}',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '',
              'hint': '/fi "STATUS eq RUNNING"  /fo csv  /v'}]},
 {'cat': '⚙️ Sistema / System / System',
  'name': 'taskkill',
  'shell': 'cmd',
  'desc': {'es': 'Termina procesos por nombre o PID. /F fuerza, /T cierra hijos también.',
           'en': 'Kills processes by name or PID. /F forces, /T also kills children.',
           'de': 'Beendet Prozesse nach Name oder PID. /F erzwingt, /T beendet Kindprozesse.'},
  'template': 'taskkill {flags}',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/IM notepad.exe /F',
              'hint': '/IM name.exe /F    /PID 1234 /F /T'}]},
 {'cat': '⚙️ Sistema / System / System',
  'name': 'sfc',
  'shell': 'cmd',
  'desc': {'es': 'Escáner de archivos de sistema. Detecta y repara archivos de Windows corruptos.',
           'en': 'System file scanner. Detects and repairs corrupted Windows files.',
           'de': 'Systemdateiprüfung. Erkennt und repariert beschädigte Windows-Dateien.'},
  'template': 'sfc {flags}',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/scannow',
              'hint': '/scannow  /verifyonly'}]},
 {'cat': '⚙️ Sistema / System / System',
  'name': 'DISM',
  'shell': 'cmd',
  'desc': {'es': 'Mantenimiento de imagen de Windows. Repara el almacén de componentes.',
           'en': 'Windows image maintenance. Repairs the component store.',
           'de': 'Windows-Image-Wartung. Repariert den Komponentenspeicher.'},
  'template': 'DISM {flags}',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/Online /Cleanup-Image /RestoreHealth',
              'hint': '/Online /Cleanup-Image /CheckHealth  /ScanHealth  /RestoreHealth'}]},
 {'cat': '⚙️ Sistema / System / System',
  'name': 'wmic',
  'shell': 'cmd',
  'desc': {'es': 'Interfaz WMI de línea de comandos. Consulta hardware, software y OS.',
           'en': 'WMI command-line interface. Query hardware, software and OS.',
           'de': 'WMI-Befehlszeilenschnittstelle. Hardware, Software und OS abfragen.'},
  'template': 'wmic {query}',
  'params': [{'label': {'es': 'Consulta', 'en': 'Query', 'de': 'Abfrage'},
              'key': 'query',
              'default': 'cpu get name,CurrentClockSpeed,NumberOfCores',
              'hint': 'bios get version  memorychip get capacity  diskdrive get model,size'}]},
 {'cat': '⚙️ Sistema / System / System',
  'name': 'sc',
  'shell': 'cmd',
  'desc': {'es': 'Gestiona servicios de Windows: iniciar, detener, consultar estado.',
           'en': 'Manages Windows services: start, stop, query status.',
           'de': 'Verwaltet Windows-Dienste: starten, stoppen, Status abfragen.'},
  'template': 'sc {action} {service}',
  'params': [{'label': {'es': 'Acción', 'en': 'Action', 'de': 'Aktion'},
              'key': 'action',
              'default': 'query',
              'hint': 'query  start  stop  config  delete'},
             {'label': {'es': 'Servicio', 'en': 'Service', 'de': 'Dienst'},
              'key': 'service',
              'default': 'wuauserv',
              'hint': 'service name (empty to list all)'}]},
 {'cat': '⚙️ Sistema / System / System',
  'name': 'powercfg',
  'shell': 'cmd',
  'desc': {'es': 'Gestiona la configuración de energía y genera informes de batería.',
           'en': 'Manages power settings and generates battery reports.',
           'de': 'Verwaltet Energieeinstellungen und erstellt Akkuberichte.'},
  'template': 'powercfg {flags}',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/energy',
              'hint': '/energy  /batteryreport  /list  /hibernate on|off'}]},
 {'cat': '💾 Disco / Disk / Datenträger',
  'name': 'chkdsk',
  'shell': 'cmd',
  'desc': {'es': 'Comprueba integridad del disco. /F corrige errores, /R busca sectores dañados.',
           'en': 'Checks disk integrity. /F fixes errors, /R finds bad sectors.',
           'de': 'Überprüft die Datenträgerstruktur. /F behebt Fehler, /R sucht fehlerhafte Sektoren.'},
  'template': 'chkdsk {drive} {flags}',
  'params': [{'label': {'es': 'Unidad', 'en': 'Drive', 'de': 'Laufwerk'},
              'key': 'drive',
              'default': 'C:',
              'hint': 'C:  D:  etc.'},
             {'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/F /R',
              'hint': '/F  /R  /X'}]},
 {'cat': '💾 Disco / Disk / Datenträger',
  'name': 'robocopy',
  'shell': 'cmd',
  'desc': {'es': 'Copia robusta de archivos con reintentos, exclusiones y sincronización.',
           'en': 'Robust file copy with retries, exclusions and synchronization.',
           'de': 'Robustes Dateikopieren mit Wiederholungen, Ausschlüssen und Synchronisation.'},
  'template': 'robocopy {src} {dst} {flags}',
  'params': [{'label': {'es': 'Origen', 'en': 'Source', 'de': 'Quelle'},
              'key': 'src',
              'default': 'C:\\Origen',
              'hint': ''},
             {'label': {'es': 'Destino', 'en': 'Dest', 'de': 'Ziel'},
              'key': 'dst',
              'default': 'D:\\Backup',
              'hint': ''},
             {'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/E /Z /COPYALL /LOG:log.txt',
              'hint': '/E  /MIR  /XF *.tmp  /MT:8'}]},
 {'cat': '💾 Disco / Disk / Datenträger',
  'name': 'dir',
  'shell': 'cmd',
  'desc': {'es': 'Lista archivos y directorios. Soporta filtros y ordenación.',
           'en': 'Lists files and directories. Supports filters and sorting.',
           'de': 'Listet Dateien und Verzeichnisse auf. Unterstützt Filter und Sortierung.'},
  'template': 'dir {path} {flags}',
  'params': [{'label': {'es': 'Ruta', 'en': 'Path', 'de': 'Pfad'}, 'key': 'path', 'default': 'C:\\', 'hint': ''},
             {'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/s /b',
              'hint': '/s  /b  /o:s  /a:h'}]},
 {'cat': '💾 Disco / Disk / Datenträger',
  'name': 'fsutil',
  'shell': 'cmd',
  'desc': {'es': 'Utilidad de bajo nivel para el sistema de archivos.',
           'en': 'Low-level file system utility.',
           'de': 'Dateisystem-Dienstprogramm auf niedriger Ebene.'},
  'template': 'fsutil {sub}',
  'params': [{'label': {'es': 'Subcomando', 'en': 'Subcommand', 'de': 'Unterbefehl'},
              'key': 'sub',
              'default': 'volume list',
              'hint': 'volume list  dirty query C:  fsinfo drives'}]},
 {'cat': '👤 Usuarios / Users / Benutzer',
  'name': 'net user',
  'shell': 'cmd',
  'desc': {'es': 'Gestiona cuentas de usuario locales: crear, eliminar, cambiar contraseña.',
           'en': 'Manages local user accounts: create, delete, change password.',
           'de': 'Verwaltet lokale Benutzerkonten: erstellen, löschen, Passwort ändern.'},
  'template': 'net user {args}',
  'params': [{'label': {'es': 'Argumentos', 'en': 'Arguments', 'de': 'Argumente'},
              'key': 'args',
              'default': '',
              'hint': '(empty=list)  name /add  name * (change pass)  name /delete'}]},
 {'cat': '👤 Usuarios / Users / Benutzer',
  'name': 'whoami',
  'shell': 'cmd',
  'desc': {'es': 'Muestra el usuario actual y opcionalmente sus grupos y privilegios.',
           'en': 'Shows the current user and optionally groups and privileges.',
           'de': 'Zeigt den aktuellen Benutzer und optional Gruppen und Berechtigungen.'},
  'template': 'whoami {flags}',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '/all',
              'hint': '/all  /user  /groups  /priv'}]},
 {'cat': '💙 PowerShell',
  'name': 'Get-Process',
  'shell': 'powershell',
  'desc': {'es': 'Lista procesos con CPU y memoria. Más potente que tasklist.',
           'en': 'Lists processes with CPU and memory. More powerful than tasklist.',
           'de': 'Listet Prozesse mit CPU und Speicher. Leistungsfähiger als tasklist.'},
  'template': 'Get-Process {filter} | Sort-Object {sort} | Select-Object -First {n} | Format-Table -AutoSize',
  'params': [{'label': {'es': 'Filtro', 'en': 'Filter', 'de': 'Filter'},
              'key': 'filter',
              'default': '',
              'hint': '-Name chrome  -Name *edge*'},
             {'label': {'es': 'Ordenar', 'en': 'Sort by', 'de': 'Sortieren'},
              'key': 'sort',
              'default': 'CPU',
              'hint': 'CPU  WorkingSet  Name  Id'},
             {'label': {'es': 'Mostrar N', 'en': 'Show N', 'de': 'Zeige N'}, 'key': 'n', 'default': '20', 'hint': ''}]},
 {'cat': '💙 PowerShell',
  'name': 'Get-Service',
  'shell': 'powershell',
  'desc': {'es': 'Lista servicios del sistema con estado filtrable.',
           'en': 'Lists system services with filterable status.',
           'de': 'Listet Systemdienste mit filterbarem Status.'},
  'template': 'Get-Service {filter} | Where-Object {where} | Format-Table Name,Status,DisplayName -AutoSize',
  'params': [{'label': {'es': 'Filtro', 'en': 'Filter', 'de': 'Filter'},
              'key': 'filter',
              'default': '',
              'hint': "-Name W*  -Name 'wuauserv'"},
             {'label': {'es': 'Where', 'en': 'Where', 'de': 'Bedingung'},
              'key': 'where',
              'default': "{$_.Status -eq 'Running'}",
              'hint': "{$_.Status -eq 'Stopped'}"}]},
 {'cat': '💙 PowerShell',
  'name': 'Get-EventLog',
  'shell': 'powershell',
  'desc': {'es': 'Consulta el registro de eventos de Windows para auditoría y errores.',
           'en': 'Queries the Windows event log for auditing and errors.',
           'de': 'Fragt das Windows-Ereignisprotokoll für Überwachung und Fehler ab.'},
  'template': 'Get-EventLog -LogName {log} -Newest {n} -EntryType {type} | Format-Table TimeGenerated,Source,Message '
              '-AutoSize',
  'params': [{'label': {'es': 'Log', 'en': 'Log', 'de': 'Protokoll'},
              'key': 'log',
              'default': 'System',
              'hint': 'System  Application  Security'},
             {'label': {'es': 'Últimos', 'en': 'Last', 'de': 'Letzte'}, 'key': 'n', 'default': '20', 'hint': ''},
             {'label': {'es': 'Tipo', 'en': 'Type', 'de': 'Typ'},
              'key': 'type',
              'default': 'Error',
              'hint': 'Error  Warning  Information'}]},
 {'cat': '💙 PowerShell',
  'name': 'Get-NetIPAddress',
  'shell': 'powershell',
  'desc': {'es': 'Muestra todas las direcciones IP de los adaptadores de red.',
           'en': 'Shows all IP addresses of network adapters.',
           'de': 'Zeigt alle IP-Adressen der Netzwerkadapter.'},
  'template': 'Get-NetIPAddress {flags} | Format-Table InterfaceAlias,AddressFamily,IPAddress,PrefixLength -AutoSize',
  'params': [{'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '-AddressFamily IPv4',
              'hint': '-AddressFamily IPv4  -AddressFamily IPv6'}]},
 {'cat': '💙 PowerShell',
  'name': 'Test-Connection',
  'shell': 'powershell',
  'desc': {'es': 'Equivalente a ping pero con salida de objetos PowerShell.',
           'en': 'Ping equivalent with PowerShell object output.',
           'de': 'Ping-Äquivalent mit PowerShell-Objektausgabe.'},
  'template': 'Test-Connection -ComputerName {host} -Count {count} {flags}',
  'params': [{'label': {'es': 'Host', 'en': 'Host', 'de': 'Host'},
              'key': 'host',
              'default': 'google.com,8.8.8.8',
              'hint': ''},
             {'label': {'es': 'Paquetes', 'en': 'Packets', 'de': 'Pakete'}, 'key': 'count', 'default': '3', 'hint': ''},
             {'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '',
              'hint': '-Quiet  -TTL 64'}]},
 {'cat': '💙 PowerShell',
  'name': 'Get-Disk',
  'shell': 'powershell',
  'desc': {'es': 'Muestra información de discos físicos: modelo, tamaño, estado.',
           'en': 'Shows physical disk information: model, size, health.',
           'de': 'Zeigt Informationen zu physischen Datenträgern: Modell, Größe, Zustand.'},
  'template': 'Get-Disk | Format-Table Number,FriendlyName,OperationalStatus,Size,PartitionStyle -AutoSize',
  'params': []},
 {'cat': '💙 PowerShell',
  'name': 'Get-HotFix',
  'shell': 'powershell',
  'desc': {'es': 'Lista los parches y actualizaciones de Windows instalados.',
           'en': 'Lists installed Windows patches and updates.',
           'de': 'Listet installierte Windows-Patches und -Updates.'},
  'template': 'Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First {n} | Format-Table '
              'HotFixID,InstalledOn,Description -AutoSize',
  'params': [{'label': {'es': 'Mostrar N', 'en': 'Show N', 'de': 'Zeige N'}, 'key': 'n', 'default': '20', 'hint': ''}]},
 {'cat': '💙 PowerShell',
  'name': 'Invoke-WebRequest',
  'shell': 'powershell',
  'desc': {'es': 'Realiza peticiones HTTP/HTTPS. Útil para probar APIs y descargar archivos.',
           'en': 'Makes HTTP/HTTPS requests. Useful for testing APIs and downloading files.',
           'de': 'Führt HTTP/HTTPS-Anfragen durch. Nützlich zum Testen von APIs und Herunterladen von Dateien.'},
  'template': "Invoke-WebRequest -Uri '{url}' {flags}",
  'params': [{'label': {'es': 'URL', 'en': 'URL', 'de': 'URL'},
              'key': 'url',
              'default': 'https://google.com',
              'hint': ''},
             {'label': {'es': 'Flags', 'en': 'Flags', 'de': 'Flags'},
              'key': 'flags',
              'default': '-Method GET -UseBasicParsing',
              'hint': '-Method POST  -OutFile file.zip  -Headers @{...}'}]}]


COMMAND_TUTOR_SCHEMA: Dict[str, Dict[str, Any]] = {
    "ipconfig": {
        "syntax": "ipconfig [opcion]",
        "description": "Muestra o administra configuracion IP/DNS de Windows.",
        "options": [
            ("/all", "Muestra informacion completa: MAC, DHCP, DNS, gateway."),
            ("/release", "Libera la direccion IPv4 del adaptador."),
            ("/renew", "Solicita una nueva direccion IPv4 por DHCP."),
            ("/flushdns", "Limpia la cache DNS local."),
            ("/displaydns", "Muestra la cache DNS local."),
            ("/registerdns", "Registra nuevamente nombres DNS del equipo."),
        ],
        "examples": ["ipconfig /all", "ipconfig /flushdns", "ipconfig /release", "ipconfig /renew"],
    },
    "ping": {
        "syntax": "ping <host> [opciones]",
        "description": "Prueba conectividad ICMP y latencia contra un host.",
        "options": [
            ("-n <cantidad>", "Numero de paquetes en Windows."),
            ("-t", "Ping continuo hasta Ctrl+C."),
            ("-l <bytes>", "Tamano del paquete."),
            ("-4", "Forzar IPv4."),
            ("-6", "Forzar IPv6."),
            ("-w <ms>", "Timeout en milisegundos."),
        ],
        "examples": ["ping 8.8.8.8 -n 4", "ping google.com -t", "ping 1.1.1.1 -4"],
    },
    "tracert": {
        "syntax": "tracert <host> [opciones]",
        "description": "Muestra los saltos de red hasta el destino.",
        "options": [("-d", "No resolver nombres DNS."), ("-h <max>", "Maximo de saltos."), ("-w <ms>", "Timeout por salto.")],
        "examples": ["tracert 8.8.8.8", "tracert -d google.com"],
    },
    "netstat": {
        "syntax": "netstat [opciones]",
        "description": "Muestra conexiones activas, puertos y estadisticas.",
        "options": [("-a", "Todas las conexiones y puertos."), ("-n", "Numerico, sin resolver nombres."), ("-o", "Incluye PID."), ("-b", "Muestra ejecutable, requiere admin."), ("-e", "Estadisticas Ethernet.")],
        "examples": ["netstat -ano", "netstat -abno"],
    },
    "nslookup": {
        "syntax": "nslookup <dominio> [servidor_dns]",
        "description": "Consulta DNS usando el resolvedor configurado o uno especifico.",
        "options": [("<dominio>", "Nombre a resolver."), ("8.8.8.8", "Servidor DNS alternativo."), ("1.1.1.1", "Servidor DNS alternativo.")],
        "examples": ["nslookup google.com", "nslookup google.com 1.1.1.1"],
    },
    "netsh": {
        "syntax": "netsh <contexto> <subcomando>",
        "description": "Configuracion avanzada de red en Windows.",
        "options": [("wlan", "Administrar Wi-Fi."), ("interface ip", "Configurar TCP/IP."), ("winsock reset", "Resetear catalogo Winsock."), ("int ip reset", "Resetear pila TCP/IP.")],
        "examples": ["netsh wlan show profiles", "netsh winsock reset", "netsh int ip reset"],
    },
    "netsh wlan": {
        "syntax": "netsh wlan <accion>",
        "description": "Administracion de perfiles e interfaces Wi-Fi.",
        "options": [("show", "Mostrar informacion Wi-Fi."), ("delete profile", "Eliminar perfil Wi-Fi guardado."), ("export profile", "Exportar perfiles Wi-Fi."), ("connect", "Conectar a un perfil.")],
        "examples": ["netsh wlan show profiles", "netsh wlan show interfaces"],
    },
    "netsh wlan show": {
        "syntax": "netsh wlan show <objeto>",
        "description": "Consulta informacion Wi-Fi.",
        "options": [("profiles", "Lista perfiles Wi-Fi guardados."), ("interfaces", "Estado de interfaces Wi-Fi."), ("drivers", "Informacion del driver Wi-Fi."), ("networks", "Redes visibles."), ("profile name=<SSID>", "Detalle de un perfil especifico."), ("profile name=<SSID> key=clear", "Detalle incluyendo clave guardada; informacion sensible.")],
        "examples": ["netsh wlan show profiles", "netsh wlan show profile name=MiWifi", "netsh wlan show interfaces"],
    },
    "chkdsk": {
        "syntax": "chkdsk <unidad> [opciones]",
        "description": "Comprueba integridad del sistema de archivos. Usar reparacion con cuidado.",
        "options": [("C:", "Unidad a revisar."), ("/F", "Corrige errores; puede requerir reinicio."), ("/R", "Busca sectores danados; puede tardar mucho."), ("/X", "Fuerza desmontaje si es necesario."), ("/SCAN", "Analisis online en NTFS.")],
        "examples": ["chkdsk C:", "chkdsk C: /F", "chkdsk C: /F /R"],
    },
    "sfc": {
        "syntax": "sfc <opcion>",
        "description": "Verifica y repara archivos protegidos del sistema.",
        "options": [("/scannow", "Analiza y repara."), ("/verifyonly", "Solo verifica."), ("/scanfile=<archivo>", "Analiza un archivo especifico.")],
        "examples": ["sfc /scannow", "sfc /verifyonly"],
    },
    "dism": {
        "syntax": "DISM /Online /Cleanup-Image <opcion>",
        "description": "Repara la imagen/component store de Windows.",
        "options": [("/CheckHealth", "Revision rapida."), ("/ScanHealth", "Escaneo profundo."), ("/RestoreHealth", "Intenta reparar la imagen."), ("/AnalyzeComponentStore", "Analiza WinSxS.")],
        "examples": ["DISM /Online /Cleanup-Image /CheckHealth", "DISM /Online /Cleanup-Image /RestoreHealth"],
    },
    "powercfg": {
        "syntax": "powercfg <opcion>",
        "description": "Gestiona energia, bateria e hibernacion.",
        "options": [("/energy", "Genera reporte de energia."), ("/batteryreport", "Genera reporte de bateria."), ("/list", "Lista planes de energia."), ("/hibernate on", "Activa hibernacion."), ("/hibernate off", "Desactiva hibernacion.")],
        "examples": ["powercfg /batteryreport", "powercfg /energy"],
    },
    "sc": {
        "syntax": "sc <accion> <servicio>",
        "description": "Consulta y administra servicios de Windows.",
        "options": [("query", "Consultar servicios."), ("start <servicio>", "Iniciar servicio."), ("stop <servicio>", "Detener servicio."), ("qc <servicio>", "Ver configuracion."), ("config <servicio>", "Cambiar configuracion; avanzado.")],
        "examples": ["sc query wuauserv", "sc query type= service state= all"],
    },
    "get-process": {
        "syntax": "Get-Process [parametros]",
        "description": "Lista procesos con propiedades PowerShell.",
        "options": [("-Name <nombre>", "Filtra por nombre."), ("| Sort-Object CPU -Descending", "Ordena por CPU."), ("| Sort-Object WorkingSet -Descending", "Ordena por memoria."), ("| Select-Object -First 20", "Limita resultados.")],
        "examples": ["Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 20"],
    },
    "get-service": {
        "syntax": "Get-Service [parametros]",
        "description": "Lista servicios desde PowerShell.",
        "options": [("-Name <nombre>", "Filtra por nombre tecnico."), ("| Where-Object {$_.Status -eq 'Running'}", "Solo servicios corriendo."), ("| Where-Object {$_.Status -eq 'Stopped'}", "Solo detenidos.")],
        "examples": ["Get-Service -Name W*", "Get-Service | Where-Object {$_.Status -eq 'Running'}"],
    },
}


def command_tutor_response(query: str) -> str:
    raw = (query or "").strip()
    if not raw:
        return "Escribe un comando con ? al final. Ejemplo: ipconfig ? o netsh wlan show ?"
    cleaned = raw.replace("?", " ").strip()
    cleaned_lower = re.sub(r"\s+", " ", cleaned.lower())
    if not cleaned_lower:
        return "Ejemplos: ipconfig ?, ping ?, netsh wlan show ?, chkdsk ?"

    # Preferir la clave mas especifica que calce con el inicio.
    best_key = ""
    for key in sorted(COMMAND_TUTOR_SCHEMA.keys(), key=len, reverse=True):
        if cleaned_lower == key or cleaned_lower.startswith(key + " "):
            best_key = key
            break

    if not best_key:
        matches = [name for name in COMMAND_TUTOR_SCHEMA if name.startswith(cleaned_lower)]
        if matches:
            return "Comandos que calzan:\n" + "\n".join(f"  - {m} ?" for m in matches[:20])
        return (
            "No tengo una ficha guiada para ese comando aun.\n"
            "Prueba con: ipconfig ?, ping ?, netsh ?, netsh wlan show ?, chkdsk ?, sfc ?, dism ?, powercfg ?, sc ?"
        )

    data = COMMAND_TUTOR_SCHEMA[best_key]
    lines = [f"{best_key} - {data.get('description', '')}", "", f"Sintaxis: {data.get('syntax', best_key)}", "", "Opciones validas sugeridas:"]
    for opt, desc in data.get("options", []):
        lines.append(f"  {opt:<28} {desc}")
    examples = data.get("examples") or []
    if examples:
        lines.extend(["", "Ejemplos:"])
        for example in examples:
            lines.append(f"  {example}")
    return "\n".join(lines)

RISKY_COMMAND_PATTERNS = [
    "taskkill",
    " chkdsk ",
    "chkdsk",
    " /f",
    " /r",
    " /x",
    "dism",
    "sfc ",
    "fsutil",
    "sc stop",
    "sc delete",
    "shutdown",
    " del ",
    "del /",
    " erase ",
    " rd /",
    " rmdir /",
    "format ",
    "diskpart",
    "vssadmin",
    "bcdedit",
    "wmic",
    "reg add",
    "reg delete",
    "net user",
    "netsh advfirewall",
    "cipher /w",
    "takeown",
    "icacls",
]

# Caracteres que NO deben aparecer en un valor de parametro del Command Center.
# El comando final se ejecuta via cmd/powershell (o shell=True en Linux/Mac), asi
# que si un parametro pudiera contener estos caracteres se podria "escapar" de su
# campo e inyectar comandos adicionales (encadenamiento con &, |, ;, backticks,
# expansion de variables %VAR%/$VAR, redireccion < >, etc.). En vez de intentar
# escapar correctamente cada shell objetivo (particularmente fragil en cmd.exe),
# se rechaza el valor directamente.
UNSAFE_PARAM_CHARS = set("&|;`$<>^\"'%()\r\n")


# =============================================================================
# ASISTENTE IA (Claude API)
# =============================================================================
# =============================================================================
# SECRETOS (API keys) - cifrado en disco
# =============================================================================
class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class SecretCrypto:
    """Cifra/descifra secretos (API keys) para que no queden en texto plano en config.json.

    - Windows: usa DPAPI (CryptProtectData/CryptUnprotectData), atado a la cuenta
      de Windows del usuario actual -- es el mismo mecanismo que usa Credential
      Manager. El archivo config.json por si solo no permite recuperar la key en
      otra maquina o con otra cuenta.
    - Otras plataformas / si DPAPI falla: no hay backend de cifrado disponible
      sin dependencias externas (p. ej. `keyring`), asi que se aplica un
      ofuscado base64 con marca "b64:" solo para evitar dejar la key a simple
      vista al abrir el archivo. Esto NO es cifrado real; para seguridad real
      en Linux/Mac habria que integrar `keyring`/`secretstorage`.
    - Valores heredados de versiones anteriores (guardados en texto plano, sin
      prefijo reconocido) se siguen leyendo correctamente para no romper
      configuraciones existentes, y se re-cifran la proxima vez que se guardan.
    """

    _PREFIX_DPAPI = "dpapi:"
    _PREFIX_B64 = "b64:"

    @classmethod
    def is_protected(cls, stored: str) -> bool:
        return bool(stored) and (stored.startswith(cls._PREFIX_DPAPI) or stored.startswith(cls._PREFIX_B64))

    @classmethod
    def protect(cls, plaintext: str) -> str:
        if not plaintext:
            return ""
        if IS_WINDOWS:
            try:
                return cls._PREFIX_DPAPI + cls._dpapi_protect(plaintext)
            except Exception:
                pass
        return cls._PREFIX_B64 + base64.b64encode(plaintext.encode("utf-8")).decode("ascii")

    @classmethod
    def unprotect(cls, stored: str) -> str:
        if not stored:
            return ""
        if stored.startswith(cls._PREFIX_DPAPI):
            try:
                return cls._dpapi_unprotect(stored[len(cls._PREFIX_DPAPI):])
            except Exception:
                return ""
        if stored.startswith(cls._PREFIX_B64):
            try:
                return base64.b64decode(stored[len(cls._PREFIX_B64):].encode("ascii")).decode("utf-8")
            except Exception:
                return ""
        # Valor heredado (texto plano de versiones anteriores a la 0.4.3).
        return stored

    @staticmethod
    def _dpapi_protect(plaintext: str) -> str:
        data = plaintext.encode("utf-8")
        buf_in = ctypes.create_string_buffer(data, len(data))
        blob_in = _DATA_BLOB(len(data), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_byte)))
        blob_out = _DATA_BLOB()
        ok = ctypes.windll.crypt32.CryptProtectData(  # type: ignore[attr-defined]
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        )
        if not ok:
            raise OSError("CryptProtectData fallo")
        try:
            encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)  # type: ignore[attr-defined]
        return base64.b64encode(encrypted).decode("ascii")

    @staticmethod
    def _dpapi_unprotect(token: str) -> str:
        data = base64.b64decode(token.encode("ascii"))
        buf_in = ctypes.create_string_buffer(data, len(data))
        blob_in = _DATA_BLOB(len(data), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_byte)))
        blob_out = _DATA_BLOB()
        ok = ctypes.windll.crypt32.CryptUnprotectData(  # type: ignore[attr-defined]
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        )
        if not ok:
            raise OSError("CryptUnprotectData fallo")
        try:
            decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)  # type: ignore[attr-defined]
        return decrypted.decode("utf-8")


# =============================================================================
# PROVEEDORES IA
# =============================================================================
def default_ai_providers() -> Dict[str, Dict[str, Any]]:
    """Perfiles base de IA.

    kind:
      - anthropic: usa Anthropic Messages API.
      - openai_compatible: usa /chat/completions estilo OpenAI.

    Los endpoints y modelos son editables desde la UI para no amarrar el
    producto a un proveedor ni a un modelo especifico.
    """
    return {
        "Claude (Anthropic)": {
            "name": "Claude (Anthropic)",
            "kind": "anthropic",
            "endpoint": "https://api.anthropic.com/v1/messages",
            "model": "claude-sonnet-4-6",
            "api_key": "",
            "api_key_env": "ANTHROPIC_API_KEY",
            "max_tokens": 1024,
        },
        "OpenAI": {
            "name": "OpenAI",
            "kind": "openai_compatible",
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-5.5",
            "api_key": "",
            "api_key_env": "OPENAI_API_KEY",
            "max_tokens": 1024,
        },
        "DeepSeek": {
            "name": "DeepSeek",
            "kind": "openai_compatible",
            "endpoint": "https://api.deepseek.com/chat/completions",
            "model": "deepseek-v4-pro",
            "api_key": "",
            "api_key_env": "DEEPSEEK_API_KEY",
            "max_tokens": 1024,
        },
        "Ollama Local": {
            "name": "Ollama Local",
            "kind": "openai_compatible",
            "endpoint": "http://localhost:11434/v1/chat/completions",
            "model": "llama3.1",
            "api_key": "",
            "api_key_env": "",
            "max_tokens": 1024,
        },
    }


class AIAssistant:
    """
    Cliente liviano y multi-proveedor para IA.

    No usa SDKs externos: solo urllib. Soporta Anthropic Messages API y
    proveedores OpenAI-compatible, lo que permite conectar OpenAI, DeepSeek,
    Ollama, LM Studio, OpenRouter, Groq u otros gateways que expongan
    /chat/completions.
    """

    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.histories: Dict[str, List[Dict[str, str]]] = {}
        self.ensure_provider_config()

    @property
    def history(self) -> List[Dict[str, str]]:
        return self.histories.setdefault(self.active_provider_name(), [])

    def ensure_provider_config(self) -> None:
        defaults = default_ai_providers()
        providers = self.config.get("ai_providers")
        if not isinstance(providers, dict) or not providers:
            providers = {name: data.copy() for name, data in defaults.items()}
        else:
            # Mantener proveedores custom del usuario, pero agregar defaults faltantes.
            normalized: Dict[str, Dict[str, Any]] = {}
            for name, data in providers.items():
                if isinstance(data, dict):
                    item = data.copy()
                    item.setdefault("name", str(name))
                    item.setdefault("kind", "openai_compatible")
                    item.setdefault("endpoint", "")
                    item.setdefault("model", "")
                    item.setdefault("api_key", "")
                    item.setdefault("api_key_env", "")
                    item.setdefault("max_tokens", 1024)
                    normalized[item["name"]] = item
            for name, data in defaults.items():
                normalized.setdefault(name, data.copy())
            providers = normalized

        # Migracion suave desde versiones previas que guardaban una sola key Anthropic
        # en texto plano en config["ai_api_key"].
        legacy_key = str(self.config.get("ai_api_key", "") or "").strip()
        if legacy_key and "Claude (Anthropic)" in providers and not str(providers["Claude (Anthropic)"].get("api_key", "")).strip():
            providers["Claude (Anthropic)"]["api_key"] = SecretCrypto.protect(legacy_key)

        # Re-cifra en el acto cualquier api_key que haya quedado en texto plano
        # (configs guardados por versiones anteriores a la 0.4.3).
        for provider in providers.values():
            raw_key = str(provider.get("api_key", "") or "")
            if raw_key and not SecretCrypto.is_protected(raw_key):
                provider["api_key"] = SecretCrypto.protect(raw_key)

        self.config["ai_providers"] = providers
        active = str(self.config.get("ai_active_provider", "") or "")
        if active not in providers:
            self.config["ai_active_provider"] = next(iter(providers.keys()))

    def provider_names(self) -> List[str]:
        self.ensure_provider_config()
        return list(self.config.get("ai_providers", {}).keys())

    def active_provider_name(self) -> str:
        self.ensure_provider_config()
        return str(self.config.get("ai_active_provider") or self.provider_names()[0])

    def get_provider(self, name: Optional[str] = None) -> Dict[str, Any]:
        self.ensure_provider_config()
        providers = self.config.get("ai_providers", {})
        provider_name = name or self.active_provider_name()
        return providers.get(provider_name, next(iter(providers.values()))).copy()

    def set_active_provider(self, name: str) -> None:
        if name in self.config.get("ai_providers", {}):
            self.config["ai_active_provider"] = name

    def _unique_name(self, desired: str) -> str:
        base = (desired or "Proveedor personalizado").strip()
        providers = self.config.get("ai_providers", {})
        if base not in providers:
            return base
        idx = 2
        while f"{base} {idx}" in providers:
            idx += 1
        return f"{base} {idx}"

    def save_provider(self, original_name: str, provider_data: Dict[str, Any]) -> str:
        self.ensure_provider_config()
        providers = self.config["ai_providers"]
        new_name = str(provider_data.get("name", original_name) or original_name).strip() or original_name
        if new_name != original_name and new_name in providers:
            new_name = self._unique_name(new_name)
        provider_data = provider_data.copy()
        provider_data["name"] = new_name
        provider_data["kind"] = provider_data.get("kind") if provider_data.get("kind") in {"anthropic", "openai_compatible"} else "openai_compatible"
        provider_data["max_tokens"] = int(provider_data.get("max_tokens") or 1024)
        # La UI de edicion trabaja con la key en texto plano; se cifra recien aqui,
        # justo antes de que quede guardada en self.config (y por lo tanto en disco).
        raw_key = str(provider_data.get("api_key", "") or "")
        if raw_key and not SecretCrypto.is_protected(raw_key):
            provider_data["api_key"] = SecretCrypto.protect(raw_key)
        if original_name in providers and original_name != new_name:
            providers.pop(original_name, None)
            self.histories[new_name] = self.histories.pop(original_name, [])
        providers[new_name] = provider_data
        self.config["ai_active_provider"] = new_name
        return new_name

    def add_provider(self, provider_data: Dict[str, Any]) -> str:
        self.ensure_provider_config()
        provider_data = provider_data.copy()
        provider_data["name"] = self._unique_name(str(provider_data.get("name") or "Proveedor personalizado"))
        raw_key = str(provider_data.get("api_key", "") or "")
        if raw_key and not SecretCrypto.is_protected(raw_key):
            provider_data["api_key"] = SecretCrypto.protect(raw_key)
        name = provider_data["name"]
        self.config["ai_providers"][name] = provider_data
        self.config["ai_active_provider"] = name
        return name

    def delete_provider(self, name: str) -> Tuple[bool, str]:
        self.ensure_provider_config()
        providers = self.config["ai_providers"]
        if name not in providers:
            return False, "Proveedor no encontrado."
        if len(providers) <= 1:
            return False, "Debe quedar al menos un proveedor IA configurado."
        providers.pop(name, None)
        self.histories.pop(name, None)
        if self.config.get("ai_active_provider") == name:
            self.config["ai_active_provider"] = next(iter(providers.keys()))
        return True, "Proveedor eliminado."

    def set_key(self, key: str) -> None:
        # Compatibilidad con código anterior.
        provider = self.get_provider()
        provider["api_key"] = key.strip()
        self.save_provider(self.active_provider_name(), provider)

    def _provider_api_key(self, provider: Dict[str, Any]) -> str:
        stored = str(provider.get("api_key", "") or "").strip()
        if stored:
            return SecretCrypto.unprotect(stored).strip()
        env_name = str(provider.get("api_key_env", "") or "").strip()
        return os.environ.get(env_name, "").strip() if env_name else ""

    @staticmethod
    def _allows_empty_key(provider: Dict[str, Any]) -> bool:
        endpoint = str(provider.get("endpoint", "") or "").lower()
        return "localhost" in endpoint or "127.0.0.1" in endpoint

    def build_system_prompt(self, context: Dict[str, Any]) -> str:
        app_name = str(self.config.get("app_name") or DEFAULT_APP_NAME).strip() or DEFAULT_APP_NAME
        lines = [
            "Eres un asistente técnico experto en sistemas Windows, redes y optimización de PCs.",
            f"El usuario usa {app_name}, una herramienta de diagnóstico y optimización.",
            "Tienes acceso al siguiente contexto en tiempo real del sistema del usuario:",
            "",
        ]
        for key, val in context.items():
            lines.append(f"- {key}: {val}")
        lines += [
            "",
            "Responde siempre en el mismo idioma en que el usuario escribe.",
            "Sé directo, técnico y práctico. Cuando sea posible sugiere acciones concretas.",
            "Nunca inventes datos del sistema; solo usa los del contexto provisto.",
        ]
        return "\n".join(lines)

    def ask(self, user_message: str, system_context: Dict[str, Any]) -> str:
        provider_name = self.active_provider_name()
        provider = self.get_provider(provider_name)
        kind = str(provider.get("kind", "openai_compatible"))
        endpoint = str(provider.get("endpoint", "") or "").strip()
        model = str(provider.get("model", "") or "").strip()
        max_tokens = int(provider.get("max_tokens") or 1024)
        api_key = self._provider_api_key(provider)

        if not endpoint or not model:
            return "⚠️ Proveedor IA incompleto. Revisa endpoint y modelo en el panel del asistente."
        if not api_key and not self._allows_empty_key(provider):
            env_name = str(provider.get("api_key_env", "") or "").strip()
            hint = f" o define la variable de entorno {env_name}" if env_name else ""
            return f"⚠️ API key no configurada para {provider_name}{hint}."

        history = self.histories.setdefault(provider_name, [])
        history.append({"role": "user", "content": user_message})
        system_prompt = self.build_system_prompt(system_context)

        try:
            if kind == "anthropic":
                payload = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": history[-20:],
                }
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": self.ANTHROPIC_VERSION,
                }
            else:
                messages = [{"role": "system", "content": system_prompt}] + history[-20:]
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "stream": False,
                }
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            reply = self._extract_reply(body, kind)
            history.append({"role": "assistant", "content": reply})
            return reply
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(err_body).get("error", {}).get("message", err_body)
            except Exception:
                detail = err_body
            if history and history[-1].get("role") == "user":
                history.pop()
            return f"❌ Error de API en {provider_name} ({exc.code}): {detail}"
        except Exception as exc:
            if history and history[-1].get("role") == "user":
                history.pop()
            return f"❌ Error de conexión con {provider_name}: {exc}"

    @staticmethod
    def _extract_reply(body: Dict[str, Any], kind: str) -> str:
        if kind == "anthropic":
            content = body.get("content") or []
            if content and isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") in ("text", None):
                        txt = item.get("text")
                        if txt:
                            parts.append(str(txt))
                if parts:
                    return "\n".join(parts)
        choices = body.get("choices") or []
        if choices and isinstance(choices, list):
            msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            if isinstance(msg, dict) and msg.get("content") is not None:
                return str(msg.get("content"))
            if isinstance(choices[0], dict) and choices[0].get("text") is not None:
                return str(choices[0].get("text"))
        if body.get("output_text"):
            return str(body["output_text"])
        return json.dumps(body, ensure_ascii=False, indent=2)[:4000]

    def clear_history(self) -> None:
        self.histories[self.active_provider_name()] = []


# =============================================================================
# MONITOR DE ALERTAS
# =============================================================================
class AlertMonitor:
    """
    Corre en un hilo daemon y evalúa umbrales cada N segundos.
    Llama a callback(alert_key, message) cuando detecta una condición.
    """

    CHECK_INTERVAL = 30  # segundos entre chequeos
    CPU_THRESHOLD = 90.0
    RAM_THRESHOLD = 88.0
    DISK_THRESHOLD = 90.0

    def __init__(self, callback: Any) -> None:
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # Cooldown: evita spam de alertas repetidas
        self._last_alert: Dict[str, float] = {}
        self._cooldown = 300.0  # 5 minutos entre alertas del mismo tipo

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _can_alert(self, key: str) -> bool:
        now = time.time()
        last = self._last_alert.get(key, 0.0)
        if now - last >= self._cooldown:
            self._last_alert[key] = now
            return True
        return False

    def _loop(self) -> None:
        while self._running:
            try:
                self._check()
            except Exception:
                pass
            time.sleep(self.CHECK_INTERVAL)

    def _check(self) -> None:
        # CPU
        cpu = psutil.cpu_percent(interval=1)
        if cpu >= self.CPU_THRESHOLD and self._can_alert("cpu"):
            self.callback("alert_cpu", f"CPU al {cpu:.0f}%")

        # RAM
        ram = psutil.virtual_memory().percent
        if ram >= self.RAM_THRESHOLD and self._can_alert("ram"):
            self.callback("alert_ram", f"RAM al {ram:.0f}%")

        # Disco
        for part in psutil.disk_partitions(all=False):
            if not part.fstype:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                if usage.percent >= self.DISK_THRESHOLD:
                    key = f"disk_{part.device}"
                    if self._can_alert(key):
                        self.callback(
                            "alert_disk",
                            f"Disco {part.device} al {usage.percent:.0f}% ({format_bytes(usage.free)} libres)",
                        )
            except Exception:
                continue

        # Conexión a internet
        try:
            socket.setdefaulttimeout(4)
            socket.getaddrinfo("8.8.8.8", 53)
        except Exception:
            if self._can_alert("net"):
                self.callback("alert_net", "No se detecta conexión a internet")


# =============================================================================
# APP PRINCIPAL
# =============================================================================
class StrallozControlCenter(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.config_data = ConfigManager.load_config()
        SystemTheme.apply_theme(self.config_data.get("theme", "dark"))

        self.backup_path = Path(self.config_data["install_path"]) / "backups"
        self.cleaner = SystemCleaner(
            self.backup_path,
            temp_file_min_age_hours=int(self.config_data.get("temp_file_min_age_hours", 24)),
        )
        self.disk_manager = DiskManager()
        self.memory_manager = MemoryManager()

        self.scan_results: Dict[str, Dict[str, Any]] = {
            key: {"issues": [], "errors": [], "timestamp": None} for key in SCAN_CATEGORIES
        }
        self.scan_vars: Dict[str, ctk.BooleanVar] = {
            key: ctk.BooleanVar(value=True) for key in SCAN_CATEGORIES
        }
        self.scanning = False
        self.fixing = False
        self.last_scan_timestamp: Optional[str] = None

        self._current_cmd: Optional[Dict[str, Any]] = None
        self._visible_commands: List[Dict[str, Any]] = list(WIN_COMMANDS)
        self._param_vars: Dict[str, tk.StringVar] = {}

        self.countdown_active = False
        self.countdown_total_seconds = 0
        self.countdown_end_time = 0.0

        self.tray_icon = None
        self.theme_watcher_running = True
        self.last_system_theme = SystemTheme.get_windows_theme()
        self.current_page = ""

        # --- IA ---
        self.ai_assistant = AIAssistant(self.config_data)
        ConfigManager.save_config(self.config_data)

        # --- Alertas ---
        self.alert_monitor = AlertMonitor(callback=self._on_alert)
        self.alert_monitor.start()
        self._alert_history: List[Tuple[str, str, str]] = []  # (timestamp, key, msg)

        # --- Sparkline history (últimos 60 puntos ≈ 3.5min a 3.5s) ---
        self._cpu_history: Deque[float] = deque(maxlen=60)
        self._ram_history: Deque[float] = deque(maxlen=60)

        # --- Dashboard refs para actualización incremental ---
        self._dash_initialized = False

        self.title(f"{self.app_name()} - {APP_VERSION}")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(fg_color=COLORS["bg"])
        self._setup_app_icon()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._build_shell()
        self.show_dashboard()
        self._setup_tray()
        self.poll_system_theme()
        if self.config_data.get("first_run", True):
            self.after(350, self.show_welcome_wizard)

    # ------------------------------------------------------------------
    # Shell / navegación
    # ------------------------------------------------------------------
    def tr(self, key: str) -> str:
        lang = resolve_language(self.config_data)
        return I18N.get(lang, I18N["en"]).get(key, I18N["en"].get(key, key))

    def app_name(self) -> str:
        """Nombre de marca mostrado en la UI; editable en Configuracion.

        Quien distribuya/rebrande esta herramienta con otro nombre no necesita
        tocar el codigo: alcanza con cambiarlo aqui en tiempo de ejecucion.
        """
        return str(self.config_data.get("app_name") or DEFAULT_APP_NAME).strip() or DEFAULT_APP_NAME

    def is_basic_mode(self) -> bool:
        """True si la UI debe mostrar solo dashboard + limpieza + reportes + config.

        Pensado para cuando esta herramienta se distribuye como companion
        liviano (p. ej. bundleado con un antivirus): oculta Red, Discos,
        Memoria, Command Center y el Asistente IA del menu y de los accesos
        rapidos, sin borrar el codigo ni los datos -- es 100% reversible desde
        Configuracion.
        """
        return bool(self.config_data.get("basic_mode", DEFAULT_BASIC_MODE))

    def is_advanced_mode(self) -> bool:
        return str(self.config_data.get("safety_mode", "safe")) == "advanced"

    def _requires_advanced(self) -> bool:
        if self.is_advanced_mode():
            return True
        messagebox.showinfo(self.tr("advanced_required_title"), self.tr("advanced_required_message"))
        return False

    def _navigate_page(self, key: str) -> None:
        routes = {
            "dashboard": self.show_dashboard,
            "ai": self.show_ai_assistant,
            "optimizer": self.show_optimizer,
            "network": self.show_network_doctor,
            "disk": self.show_disk_center,
            "memory": self.show_memory_inspector,
            "commands": self.show_command_center,
            "power": self.show_power_center,
            "reports": self.show_report_center,
            "settings": self.show_settings,
        }
        routes.get(key, self.show_dashboard)()

    def _rebuild_shell_keep_page(self) -> None:
        current = self.current_page or "dashboard"
        if self.is_basic_mode() and current not in BASIC_MODE_VISIBLE_PAGES:
            # La pagina en la que estabamos quedo oculta al pasar a modo
            # Basico (p. ej. Red, Discos, Memoria, Command Center, IA):
            # volvemos al dashboard en vez de dejar una pagina "fantasma".
            current = "dashboard"
        for widget in self.winfo_children():
            widget.destroy()
        self.nav_buttons = {}
        self._build_shell()
        self._navigate_page(current)

    def _build_shell(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar layout:
        #   row 0 -> brand fijo
        #   row 1 -> nav scrollable
        #   row 2 -> footer fijo
        # Esto evita que botones nuevos queden cortados en pantallas pequenas
        # y mantiene la identidad visual siempre visible.
        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=COLORS["surface"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(0, weight=0)
        self.sidebar.grid_rowconfigure(1, weight=1)
        self.sidebar.grid_rowconfigure(2, weight=0)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(24, 10))
        ctk.CTkLabel(brand, text=self.app_name(), font=ctk.CTkFont(size=25, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text=self.tr("app_subtitle"),
            font=ctk.CTkFont(size=13),
            text_color=COLORS["muted"],
        ).pack(anchor="w")

        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        nav_groups = [
            ("nav_group_home", [("dashboard", "nav_dashboard", self.show_dashboard)]),
            ("nav_group_ai", [("ai", "nav_ai", self.show_ai_assistant)]),
            ("nav_group_diagnostics", [
                ("network", "nav_network", self.show_network_doctor),
                ("disk", "nav_disk", self.show_disk_center),
                ("memory", "nav_memory", self.show_memory_inspector),
            ]),
            ("nav_group_optimization", [("optimizer", "nav_optimizer", self.show_optimizer)]),
            ("nav_group_tools", [
                ("commands", "nav_commands", self.show_command_center),
                ("power", "nav_power", self.show_power_center),
                ("reports", "nav_reports", self.show_report_center),
            ]),
            ("nav_group_system", [("settings", "nav_settings", self.show_settings)]),
        ]

        if self.is_basic_mode():
            filtered_groups = []
            for group_key, items in nav_groups:
                visible_items = [item for item in items if item[0] in BASIC_MODE_VISIBLE_PAGES]
                if visible_items:
                    filtered_groups.append((group_key, visible_items))
            nav_groups = filtered_groups

        nav_scroll = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["surface2"],
            scrollbar_button_hover_color=COLORS["surface3"],
        )
        nav_scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 6))
        nav_scroll.grid_columnconfigure(0, weight=1)

        for group_key, items in nav_groups:
            ctk.CTkLabel(
                nav_scroll,
                text=self.tr(group_key).upper(),
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(anchor="w", padx=18, pady=(12, 3))
            for key, label_key, command in items:
                btn = ctk.CTkButton(
                    nav_scroll,
                    text=self.tr(label_key),
                    command=command,
                    anchor="w",
                    height=38,
                    fg_color="transparent",
                    hover_color=COLORS["surface2"],
                    text_color=COLORS["text"],
                    font=ctk.CTkFont(size=13, weight="bold"),
                )
                btn.pack(fill="x", padx=14, pady=3)
                self.nav_buttons[key] = btn

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 16))
        ctk.CTkLabel(
            footer,
            text=f"v{APP_VERSION}\n{platform.system()} {platform.release()}\n{platform.node()}",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11),
            justify="left",
        ).pack(anchor="w")

        self.content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=COLORS["bg"])
        self.content_frame.grid(row=0, column=1, sticky="nsew")

        self.status_var = tk.StringVar(value=self.tr("status_ready"))
        status = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color=COLORS["surface"])
        status.grid(row=1, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(status, textvariable=self.status_var, text_color=COLORS["muted"], anchor="w").pack(
            side="left", fill="x", expand=True, padx=14
        )
        self.clock_var = tk.StringVar()
        ctk.CTkLabel(status, textvariable=self.clock_var, text_color=COLORS["muted"]).pack(side="right", padx=14)
        self._tick_clock()

    def _set_active_nav(self, key: str) -> None:
        self.current_page = key
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=COLORS["accent"], text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text"])

    def clear_content(self) -> None:
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def update_status(self, message: str) -> None:
        def _do() -> None:
            self.status_var.set(message)

        try:
            self.after(0, _do)
        except Exception:
            pass

    def log(self, message: str) -> None:
        self._write_activity_log(message)

        def _do() -> None:
            timestamp = datetime.now().strftime("%H:%M:%S")
            if hasattr(self, "log_text") and self.log_text.winfo_exists():
                self.log_text.configure(state="normal")
                self.log_text.insert("end", f"[{timestamp}] {message}\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")

        try:
            self.after(0, _do)
        except Exception:
            pass

    def _write_activity_log(self, message: str) -> None:
        try:
            base = Path(self.config_data.get("install_path", str(Path.home() / "StrallozData")))
            log_dir = base / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file = log_dir / f"actions_{datetime.now().strftime('%Y-%m-%d')}.log"
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(f"[{stamp}] {message}\n")
        except Exception:
            pass

    def _tick_clock(self) -> None:
        self.clock_var.set(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        self.after(1000, self._tick_clock)

    def poll_system_theme(self) -> None:
        if not self.theme_watcher_running:
            return
        if self.config_data.get("theme") == "system":
            current = SystemTheme.get_windows_theme()
            if current != self.last_system_theme:
                self.last_system_theme = current
                SystemTheme.apply_theme("system")
        self.after(5000, self.poll_system_theme)

    def _setup_app_icon(self) -> None:
        try:
            img = Image.new("RGB", (64, 64), color="#2563eb")
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle([12, 12, 52, 52], radius=8, fill="#eff6ff")
            draw.rectangle([22, 22, 42, 42], fill="#2563eb")
            self.icon_image = ImageTk.PhotoImage(img)
            self.iconphoto(True, self.icon_image)
        except Exception:
            pass

    def _setup_tray(self) -> None:
        if not HAS_TRAY or not self.config_data.get("close_to_tray", False):
            return
        try:
            icon_img = Image.new("RGB", (64, 64), color="#2563eb")
            draw = ImageDraw.Draw(icon_img)
            draw.rounded_rectangle([12, 12, 52, 52], radius=8, fill="#ffffff")
            draw.rectangle([22, 22, 42, 42], fill="#2563eb")

            def on_show_window(icon: Any, item: Any) -> None:
                self.after(0, self.show_window)

            def on_quit(icon: Any, item: Any) -> None:
                try:
                    icon.stop()
                except Exception:
                    pass
                self.after(0, self.destroy)

            menu = pystray.Menu(  # type: ignore[union-attr]
                pystray.MenuItem(f"Mostrar {self.app_name()}", on_show_window),  # type: ignore[union-attr]
                pystray.MenuItem("Salir", on_quit),  # type: ignore[union-attr]
            )
            self.tray_icon = pystray.Icon("stralloz_control_center", icon_img, self.app_name(), menu)  # type: ignore[union-attr]
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as exc:
            self.tray_icon = None
            self.update_status(f"Tray no disponible: {exc}")

    def show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def on_closing(self) -> None:
        if self.config_data.get("close_to_tray", False) and self.tray_icon:
            self.withdraw()
            try:
                self.tray_icon.notify(f"{self.app_name()} sigue ejecutándose en la bandeja", self.app_name())
            except Exception:
                pass
            return
        if messagebox.askyesno("Salir", f"¿Quieres cerrar {self.app_name()}?"):
            self.theme_watcher_running = False
            self.alert_monitor.stop()
            try:
                if self.tray_icon:
                    self.tray_icon.stop()
            except Exception:
                pass
            self.destroy()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _page(self, key: str, title: str, subtitle: str = "") -> ctk.CTkFrame:
        self._set_active_nav(key)
        self.clear_content()
        page = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=22, pady=20)
        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=29, weight="bold")).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(header, text=subtitle, text_color=COLORS["muted"], font=ctk.CTkFont(size=13)).pack(anchor="w")
        return page

    def _card(self, parent: Any, title: str, value: str = "", width: Optional[int] = None) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        if width:
            card.configure(width=width)
        ctk.CTkLabel(card, text=title, text_color=COLORS["muted"], font=ctk.CTkFont(size=13)).pack(
            anchor="w", padx=16, pady=(14, 2)
        )
        if value:
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=23, weight="bold")).pack(anchor="w", padx=16, pady=(0, 14))
        return card

    def _button(self, parent: Any, text: str, command: Any, color: str = "accent", **kwargs: Any) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=COLORS.get(color, color),
            hover_color=COLORS["surface3"],
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def show_dashboard(self) -> None:
        page = self._page(
            "dashboard",
            self.tr("dashboard_title"),
            self.tr("dashboard_subtitle"),
        )
        self._dash_initialized = False

        # --- Fila de tarjetas métricas ---
        cards = ctk.CTkFrame(page, fg_color="transparent")
        cards.pack(fill="x")
        for i in range(5):
            cards.grid_columnconfigure(i, weight=1)

        self.dashboard_cards: Dict[str, ctk.CTkLabel] = {}
        self.dashboard_bars: Dict[str, ctk.CTkProgressBar] = {}
        for i, (key, title) in enumerate([
            ("cpu", "CPU"),
            ("ram", "RAM"),
            ("disk", "Disco principal"),
            ("issues", "Issues actuales"),
            ("alerts", "Alertas hoy"),
        ]):
            card = ctk.CTkFrame(cards, fg_color=COLORS["surface"], corner_radius=14,
                                border_width=1, border_color=COLORS["border"])
            card.grid(row=0, column=i, padx=5, pady=7, sticky="nsew")
            ctk.CTkLabel(card, text=title, text_color=COLORS["muted"],
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=14, pady=(12, 1))
            label = ctk.CTkLabel(card, text="-", font=ctk.CTkFont(size=22, weight="bold"))
            label.pack(anchor="w", padx=14, pady=(0, 4))
            if key in ("cpu", "ram", "disk"):
                bar = ctk.CTkProgressBar(card, height=6)
                bar.pack(fill="x", padx=14, pady=(0, 10))
                bar.set(0)
                self.dashboard_bars[key] = bar
            else:
                ctk.CTkFrame(card, height=10, fg_color="transparent").pack()
            self.dashboard_cards[key] = label

        # --- Sparkline canvas ---
        spark_frame = ctk.CTkFrame(page, fg_color=COLORS["surface"], corner_radius=14,
                                   border_width=1, border_color=COLORS["border"])
        spark_frame.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(spark_frame, text="Historial CPU / RAM (últimos 3 min)",
                     text_color=COLORS["muted"], font=ctk.CTkFont(size=12)).pack(anchor="w", padx=14, pady=(10, 2))
        self.spark_canvas = tk.Canvas(spark_frame, height=52, bg=COLORS["surface"],
                                      highlightthickness=0, bd=0)
        self.spark_canvas.pack(fill="x", padx=14, pady=(0, 10))

        # --- Cuerpo principal ---
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(8, 0))
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.disk_panel = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=14,
                                       border_width=1, border_color=COLORS["border"])
        self.disk_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        ctk.CTkLabel(self.disk_panel, text="Uso de discos",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        self.disk_rows_frame = ctk.CTkFrame(self.disk_panel, fg_color="transparent")
        self.disk_rows_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        # Mapa de progress bars de disco para actualización incremental
        self._disk_progress_map: Dict[str, ctk.CTkProgressBar] = {}
        self._disk_label_map: Dict[str, ctk.CTkLabel] = {}

        actions = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=14,
                                border_width=1, border_color=COLORS["border"])
        actions.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        ctk.CTkLabel(actions, text=self.tr("quick_actions"),
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        self._button(actions, self.tr("scan_system"),
                     lambda: (self.show_optimizer(), self.start_scan()), "accent").pack(fill="x", padx=16, pady=4)
        self._button(actions, self.tr("fix_detected"),
                     lambda: (self.show_optimizer(), self.fix_all_issues()), "accent2").pack(fill="x", padx=16, pady=4)
        if not self.is_basic_mode():
            # Accesos rapidos a las paginas "power user"; ocultos en modo
            # Basico igual que sus entradas en el menu lateral.
            self._button(actions, self.tr("network_title"),
                         self.show_network_doctor, "accent").pack(fill="x", padx=16, pady=4)
            self._button(actions, self.tr("disk_title"),
                         self.show_disk_center, "warn").pack(fill="x", padx=16, pady=4)
            self._button(actions, self.tr("memory_title"),
                         self.show_memory_inspector, "accent2").pack(fill="x", padx=16, pady=4)
            self._button(actions, self.tr("open_commands"),
                         self.show_command_center, "purple").pack(fill="x", padx=16, pady=4)
            self._button(actions, "🤖 " + self.tr("nav_ai"),
                         self.show_ai_assistant, "accent").pack(fill="x", padx=16, pady=4)

        self.dashboard_scan_label = ctk.CTkLabel(
            actions, text="Aún no hay escaneo en esta sesión.",
            text_color=COLORS["muted"], wraplength=290, justify="left",
        )
        self.dashboard_scan_label.pack(anchor="w", padx=16, pady=(10, 2))

        self.alert_badge_label = ctk.CTkLabel(
            actions, text="🔔 Sin alertas activas",
            text_color=COLORS["muted"], font=ctk.CTkFont(size=12),
        )
        self.alert_badge_label.pack(anchor="w", padx=16, pady=(0, 12))
        if self._alert_history:
            self.alert_badge_label.configure(
                text=f"🔔 {len(self._alert_history)} alerta(s) hoy",
                text_color=COLORS["warn"],
            )

        self._dash_initialized = True
        self.refresh_dashboard_stats()

    def _draw_sparkline(self, canvas: tk.Canvas, cpu_data: List[float], ram_data: List[float]) -> None:
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10 or h < 10 or not cpu_data:
            return
        pad = 4

        def points(data: List[float]) -> List[Tuple[float, float]]:
            n = len(data)
            if n < 2:
                return []
            step = (w - pad * 2) / (n - 1)
            return [(pad + i * step, h - pad - (v / 100.0) * (h - pad * 2)) for i, v in enumerate(data)]

        def draw_line(pts: List[Tuple[float, float]], color: str) -> None:
            if len(pts) < 2:
                return
            flat = [coord for pt in pts for coord in pt]
            canvas.create_line(*flat, fill=color, width=2, smooth=True)

        draw_line(points(cpu_data), COLORS["accent"])
        draw_line(points(ram_data), COLORS["accent2"])
        # Leyenda
        canvas.create_rectangle(pad, h - 14, pad + 14, h - 6, fill=COLORS["accent"], outline="")
        canvas.create_text(pad + 18, h - 10, text="CPU", fill=COLORS["muted"], anchor="w", font=("Segoe UI", 8))
        canvas.create_rectangle(pad + 54, h - 14, pad + 68, h - 6, fill=COLORS["accent2"], outline="")
        canvas.create_text(pad + 72, h - 10, text="RAM", fill=COLORS["muted"], anchor="w", font=("Segoe UI", 8))

    def refresh_dashboard_stats(self) -> None:
        if self.current_page != "dashboard" or not self._dash_initialized:
            return
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent

            # Actualizar historial sparkline
            self._cpu_history.append(cpu)
            self._ram_history.append(ram)

            disk_pct = 0.0
            disk_text = "-"
            try:
                du = psutil.disk_usage(Path.home().anchor or "/")
                disk_pct = du.percent
                disk_text = f"{disk_pct:.0f}%"
            except Exception:
                pass
            total_issues = self.total_current_issues()
            total_alerts = len(self._alert_history)

            # Actualizar labels (sin destruir widgets)
            self.dashboard_cards["cpu"].configure(text=f"{cpu:.0f}%")
            self.dashboard_cards["ram"].configure(text=f"{ram:.0f}%")
            self.dashboard_cards["disk"].configure(text=disk_text)
            self.dashboard_cards["issues"].configure(text=str(total_issues))
            self.dashboard_cards["alerts"].configure(
                text=str(total_alerts),
                text_color=COLORS["warn"] if total_alerts > 0 else COLORS["text"],
            )

            # Actualizar barras de progreso
            self.dashboard_bars["cpu"].set(cpu / 100)
            self.dashboard_bars["ram"].set(ram / 100)
            self.dashboard_bars["disk"].set(disk_pct / 100)

            # Colores dinámicos según umbral
            for key, val in [("cpu", cpu), ("ram", ram), ("disk", disk_pct)]:
                color = COLORS["danger"] if val > 88 else COLORS["warn"] if val > 70 else COLORS["accent2"]
                self.dashboard_cards[key].configure(text_color=color)

            if self.last_scan_timestamp:
                self.dashboard_scan_label.configure(
                    text=f"Último escaneo: {self.last_scan_timestamp}\nIssues actuales: {total_issues}"
                )

            # Sparkline
            self._draw_sparkline(
                self.spark_canvas,
                list(self._cpu_history),
                list(self._ram_history),
            )

            # Discos: actualizar o crear filas
            partitions = [p for p in psutil.disk_partitions()
                          if "cdrom" not in p.opts.lower() and p.fstype]
            current_devices = set()
            for part in partitions:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                except Exception:
                    continue
                dev = part.device
                current_devices.add(dev)
                text = (f"{dev}  {usage.percent:.0f}% · "
                        f"{format_bytes(usage.free)} libres / {format_bytes(usage.total)}")
                if dev in self._disk_label_map:
                    self._disk_label_map[dev].configure(text=text)
                    self._disk_progress_map[dev].set(usage.percent / 100)
                else:
                    row = ctk.CTkFrame(self.disk_rows_frame, fg_color=COLORS["surface2"], corner_radius=10)
                    row.pack(fill="x", pady=4)
                    lbl = ctk.CTkLabel(row, text=text, anchor="w")
                    lbl.pack(side="left", padx=12, pady=8, fill="x", expand=True)
                    bar = ctk.CTkProgressBar(row, width=160)
                    bar.pack(side="right", padx=10)
                    bar.set(usage.percent / 100)
                    self._disk_label_map[dev] = lbl
                    self._disk_progress_map[dev] = bar

            # Eliminar filas de dispositivos que ya no existen
            for dev in list(self._disk_label_map.keys()):
                if dev not in current_devices:
                    del self._disk_label_map[dev]
                    del self._disk_progress_map[dev]

        except Exception as exc:
            self.update_status(f"Error actualizando dashboard: {exc}")
        self.after(3500, self.refresh_dashboard_stats)

    def total_current_issues(self) -> int:
        return sum(len(data.get("issues", [])) for data in self.scan_results.values())

    # ------------------------------------------------------------------
    # Asistente IA
    # ------------------------------------------------------------------
    def show_ai_assistant(self) -> None:
        page = self._page("ai", self.tr("ai_title"), self.tr("ai_subtitle"))

        # --- Panel flexible de proveedores IA ---
        provider_frame = ctk.CTkFrame(page, fg_color=COLORS["surface"], corner_radius=14,
                                      border_width=1, border_color=COLORS["border"])
        provider_frame.pack(fill="x", pady=(0, 8))
        provider_frame.grid_columnconfigure(1, weight=1)

        header_row = ctk.CTkFrame(provider_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(header_row, text="Proveedor IA:", width=120, anchor="w").pack(side="left")
        self._ai_provider_var = tk.StringVar(value=self.ai_assistant.active_provider_name())
        self._ai_provider_menu = ctk.CTkOptionMenu(
            header_row,
            values=self.ai_assistant.provider_names(),
            variable=self._ai_provider_var,
            command=self._ai_provider_changed,
            width=230,
        )
        self._ai_provider_menu.pack(side="left", padx=(0, 8))
        self._button(header_row, "Guardar", self._save_ai_provider_from_fields, "accent", width=100).pack(side="left", padx=(0, 6))
        self._button(header_row, "Añadir IA", self._add_ai_provider_from_fields, "accent2", width=105).pack(side="left", padx=(0, 6))
        self._button(header_row, "Eliminar", self._delete_ai_provider, "danger", width=90).pack(side="left")

        form = ctk.CTkFrame(provider_frame, fg_color="transparent")
        form.pack(fill="x", padx=16, pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)

        self._ai_provider_name_var = tk.StringVar()
        self._ai_provider_kind_var = tk.StringVar()
        self._ai_model_var = tk.StringVar()
        self._ai_endpoint_var = tk.StringVar()
        self._ai_key_var = tk.StringVar()
        self._ai_env_var = tk.StringVar()
        self._ai_max_tokens_var = tk.StringVar()

        ctk.CTkLabel(form, text="Nombre:", width=90, anchor="w").grid(row=0, column=0, sticky="w", pady=3)
        ctk.CTkEntry(form, textvariable=self._ai_provider_name_var).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=3)
        ctk.CTkLabel(form, text="Tipo:", width=70, anchor="w").grid(row=0, column=2, sticky="w", pady=3)
        ctk.CTkOptionMenu(
            form,
            values=["anthropic", "openai_compatible"],
            variable=self._ai_provider_kind_var,
            width=190,
        ).grid(row=0, column=3, sticky="ew", pady=3)

        ctk.CTkLabel(form, text="Modelo:", width=90, anchor="w").grid(row=1, column=0, sticky="w", pady=3)
        ctk.CTkEntry(form, textvariable=self._ai_model_var).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=3)
        ctk.CTkLabel(form, text="Max tokens:", width=70, anchor="w").grid(row=1, column=2, sticky="w", pady=3)
        ctk.CTkEntry(form, textvariable=self._ai_max_tokens_var, width=190).grid(row=1, column=3, sticky="ew", pady=3)

        ctk.CTkLabel(form, text="Endpoint:", width=90, anchor="w").grid(row=2, column=0, sticky="w", pady=3)
        ctk.CTkEntry(form, textvariable=self._ai_endpoint_var).grid(row=2, column=1, columnspan=3, sticky="ew", pady=3)

        ctk.CTkLabel(form, text="API key:", width=90, anchor="w").grid(row=3, column=0, sticky="w", pady=3)
        self._ai_key_entry = ctk.CTkEntry(form, textvariable=self._ai_key_var, show="•")
        self._ai_key_entry.grid(row=3, column=1, sticky="ew", padx=(0, 10), pady=3)
        ctk.CTkLabel(form, text="Env var:", width=70, anchor="w").grid(row=3, column=2, sticky="w", pady=3)
        env_wrap = ctk.CTkFrame(form, fg_color="transparent")
        env_wrap.grid(row=3, column=3, sticky="ew", pady=3)
        env_wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(env_wrap, textvariable=self._ai_env_var).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._button(env_wrap, "👁", self._toggle_ai_key_visibility, "surface3", width=42).grid(row=0, column=1)

        ctk.CTkLabel(
            provider_frame,
            text="Tip: usa 'openai_compatible' para OpenAI, DeepSeek, Ollama, LM Studio, OpenRouter o cualquier gateway con /chat/completions. Las keys se guardan localmente en config.json.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        self._load_ai_provider_into_fields(self.ai_assistant.active_provider_name())

        # --- Contexto enviado ---
        ctx_frame = ctk.CTkFrame(page, fg_color=COLORS["surface2"], corner_radius=10)
        ctx_frame.pack(fill="x", pady=(0, 8))
        self._ai_ctx_var = tk.StringVar(value="Calculando contexto...")
        ctk.CTkLabel(ctx_frame, text=self.tr("ai_context_label"),
                     text_color=COLORS["muted"], font=ctk.CTkFont(size=11)).pack(anchor="w", padx=12, pady=(6, 0))
        ctk.CTkLabel(ctx_frame, textvariable=self._ai_ctx_var,
                     text_color=COLORS["accent2"], font=ctk.CTkFont(family="Consolas", size=11),
                     wraplength=900, justify="left").pack(anchor="w", padx=12, pady=(0, 6))
        self._refresh_ai_context()

        # --- Área de chat ---
        chat_frame = ctk.CTkFrame(page, fg_color="#020617", corner_radius=14,
                                  border_width=1, border_color=COLORS["border"])
        chat_frame.pack(fill="both", expand=True, pady=(0, 8))
        self.ai_chat_box = tk.Text(
            chat_frame, bg="#020617", fg=COLORS["text"],
            insertbackground=COLORS["text"], relief="flat", borderwidth=0,
            font=("Segoe UI", 11), wrap="word", state="disabled",
        )
        chat_scroll = ttk.Scrollbar(chat_frame, orient="vertical", command=self.ai_chat_box.yview)
        self.ai_chat_box.configure(yscrollcommand=chat_scroll.set)
        chat_scroll.pack(side="right", fill="y")
        self.ai_chat_box.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.ai_chat_box.tag_configure("user", foreground=COLORS["accent"], font=("Segoe UI", 11, "bold"))
        self.ai_chat_box.tag_configure("assistant", foreground=COLORS["text"])
        self.ai_chat_box.tag_configure("thinking", foreground=COLORS["muted"], font=("Segoe UI", 10, "italic"))
        self.ai_chat_box.tag_configure("error", foreground=COLORS["danger"])
        self.ai_chat_box.tag_configure("sep", foreground=COLORS["border"])

        if self.ai_assistant.history:
            self._repopulate_chat()

        # --- Input de usuario ---
        input_frame = ctk.CTkFrame(page, fg_color=COLORS["surface"], corner_radius=14,
                                   border_width=1, border_color=COLORS["border"])
        input_frame.pack(fill="x")
        input_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=14, pady=12)
        self.ai_input_var = tk.StringVar()
        ai_entry = ctk.CTkEntry(
            input_row, textvariable=self.ai_input_var,
            placeholder_text=self.tr("ai_placeholder"),
            height=38, font=ctk.CTkFont(size=13),
        )
        ai_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ai_entry.bind("<Return>", lambda _: self._ai_send())
        self._button(input_row, self.tr("ai_send"), self._ai_send, "accent", width=100).pack(side="left", padx=(0, 6))
        self._button(input_row, self.tr("ai_clear"), self._ai_clear, "surface3", width=110).pack(side="left")

        suggestions = [
            "¿Por qué puede estar lenta la red?",
            "¿Qué proceso consume más RAM?",
            "Resume el estado de salud del equipo",
            "¿Qué disco tiene menos espacio?",
            "Sugiere optimizaciones para este sistema",
        ]
        sugg_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        sugg_row.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(sugg_row, text="Sugerencias:", text_color=COLORS["muted"],
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        for s in suggestions:
            ctk.CTkButton(
                sugg_row, text=s, height=26, font=ctk.CTkFont(size=11),
                fg_color=COLORS["surface2"], hover_color=COLORS["surface3"],
                text_color=COLORS["muted"], corner_radius=8,
                command=lambda q=s: self._ai_quick_send(q),
            ).pack(side="left", padx=3)

    def _load_ai_provider_into_fields(self, name: str) -> None:
        provider = self.ai_assistant.get_provider(name)
        if hasattr(self, "_ai_provider_name_var"):
            self._ai_provider_name_var.set(str(provider.get("name", name)))
            self._ai_provider_kind_var.set(str(provider.get("kind", "openai_compatible")))
            self._ai_model_var.set(str(provider.get("model", "")))
            self._ai_endpoint_var.set(str(provider.get("endpoint", "")))
            self._ai_key_var.set(SecretCrypto.unprotect(str(provider.get("api_key", ""))))
            self._ai_env_var.set(str(provider.get("api_key_env", "")))
            self._ai_max_tokens_var.set(str(provider.get("max_tokens", 1024)))

    def _ai_provider_changed(self, name: str) -> None:
        self.ai_assistant.set_active_provider(name)
        ConfigManager.save_config(self.config_data)
        self._load_ai_provider_into_fields(name)
        if hasattr(self, "ai_chat_box") and self.ai_chat_box.winfo_exists():
            self.ai_chat_box.configure(state="normal")
            self.ai_chat_box.delete("1.0", "end")
            self.ai_chat_box.configure(state="disabled")
            self._repopulate_chat()
        self.update_status(f"Proveedor IA activo: {name}")

    def _current_ai_provider_from_fields(self) -> Dict[str, Any]:
        try:
            max_tokens = int(self._ai_max_tokens_var.get().strip() or "1024")
        except Exception:
            max_tokens = 1024
        return {
            "name": self._ai_provider_name_var.get().strip() or self._ai_provider_var.get(),
            "kind": self._ai_provider_kind_var.get().strip() or "openai_compatible",
            "endpoint": self._ai_endpoint_var.get().strip(),
            "model": self._ai_model_var.get().strip(),
            "api_key": self._ai_key_var.get().strip(),
            "api_key_env": self._ai_env_var.get().strip(),
            "max_tokens": max_tokens,
        }

    def _refresh_ai_provider_menu(self) -> None:
        names = self.ai_assistant.provider_names()
        if hasattr(self, "_ai_provider_menu") and self._ai_provider_menu.winfo_exists():
            self._ai_provider_menu.configure(values=names)
        if hasattr(self, "_ai_provider_var"):
            self._ai_provider_var.set(self.ai_assistant.active_provider_name())

    def _save_ai_provider_from_fields(self) -> None:
        original = self._ai_provider_var.get()
        provider = self._current_ai_provider_from_fields()
        new_name = self.ai_assistant.save_provider(original, provider)
        ConfigManager.save_config(self.config_data)
        self._refresh_ai_provider_menu()
        self._load_ai_provider_into_fields(new_name)
        self.update_status(f"Proveedor IA guardado: {new_name}")

    def _add_ai_provider_from_fields(self) -> None:
        provider = self._current_ai_provider_from_fields()
        provider["name"] = provider.get("name") or "Proveedor personalizado"
        new_name = self.ai_assistant.add_provider(provider)
        ConfigManager.save_config(self.config_data)
        self._refresh_ai_provider_menu()
        self._load_ai_provider_into_fields(new_name)
        self.update_status(f"Proveedor IA añadido: {new_name}")

    def _delete_ai_provider(self) -> None:
        name = self._ai_provider_var.get()
        if not messagebox.askyesno("Eliminar proveedor", f"¿Eliminar el proveedor IA '{name}'?", icon="warning"):
            return
        ok, msg = self.ai_assistant.delete_provider(name)
        if not ok:
            messagebox.showwarning("Proveedor IA", msg)
            return
        ConfigManager.save_config(self.config_data)
        self._refresh_ai_provider_menu()
        self._load_ai_provider_into_fields(self.ai_assistant.active_provider_name())
        self.update_status(msg)

    def _toggle_ai_key_visibility(self) -> None:
        if hasattr(self, "_ai_key_entry"):
            current = self._ai_key_entry.cget("show")
            self._ai_key_entry.configure(show="" if current == "•" else "•")

    def _refresh_ai_context(self) -> None:
        """Actualiza el label de contexto del sistema en la página de IA."""
        if not hasattr(self, "_ai_ctx_var"):
            return
        ctx = self._build_ai_context()
        lines = [f"{k}: {v}" for k, v in list(ctx.items())[:6]]
        self._ai_ctx_var.set("  ·  ".join(lines))

    def _build_ai_context(self) -> Dict[str, Any]:
        """Construye el contexto del sistema para enviar al asistente IA."""
        ctx: Dict[str, Any] = {}
        try:
            ctx["SO"] = f"{platform.system()} {platform.release()}"
            ctx["Host"] = platform.node()
            ctx["CPU_%"] = f"{psutil.cpu_percent(interval=None):.0f}%"
            ctx["CPU_cores"] = psutil.cpu_count(logical=True)
            vm = psutil.virtual_memory()
            ctx["RAM_total"] = format_bytes(vm.total)
            ctx["RAM_usada"] = f"{vm.percent:.0f}%"
            ctx["RAM_libre"] = format_bytes(vm.available)
            swap = psutil.swap_memory()
            ctx["Swap_%"] = f"{swap.percent:.0f}%"
            # Discos
            disk_info = []
            for part in psutil.disk_partitions(all=False):
                if not part.fstype or "cdrom" in part.opts.lower():
                    continue
                try:
                    u = psutil.disk_usage(part.mountpoint)
                    disk_info.append(f"{part.device} {u.percent:.0f}% ({format_bytes(u.free)} libres)")
                except Exception:
                    pass
            ctx["Discos"] = " | ".join(disk_info) if disk_info else "N/A"
            # Red
            stats = psutil.net_if_stats()
            up_ifaces = [n for n, s in stats.items() if s.isup]
            ctx["Interfaces_UP"] = ", ".join(up_ifaces[:4]) if up_ifaces else "ninguna"
            ctx["Issues_scanner"] = self.total_current_issues()
            ctx["Alertas_sesion"] = len(self._alert_history)
            ctx["Ultimo_escaneo"] = self.last_scan_timestamp or "ninguno"
        except Exception as exc:
            ctx["error_contexto"] = str(exc)
        return ctx

    def _ai_append(self, text: str, tag: str = "assistant") -> None:
        self.ai_chat_box.configure(state="normal")
        self.ai_chat_box.insert("end", text, tag)
        self.ai_chat_box.see("end")
        self.ai_chat_box.configure(state="disabled")

    def _ai_send(self) -> None:
        msg = self.ai_input_var.get().strip()
        if not msg:
            return
        self.ai_input_var.set("")
        self._ai_dispatch(msg)

    def _ai_quick_send(self, msg: str) -> None:
        self._ai_dispatch(msg)

    def _ai_dispatch(self, msg: str) -> None:
        self._ai_append("─" * 72 + "\n", "sep")
        self._ai_append(f"Tú: {msg}\n", "user")
        self._ai_append(f"{self.tr('ai_thinking')}\n", "thinking")
        ctx = self._build_ai_context()
        self._refresh_ai_context()
        self.update_status("Consultando asistente IA...")
        threading.Thread(target=self._ai_thread, args=(msg, ctx), daemon=True).start()

    def _ai_thread(self, msg: str, ctx: Dict[str, Any]) -> None:
        reply = self.ai_assistant.ask(msg, ctx)
        def _show() -> None:
            # Eliminar el "Analizando..." (última línea con tag thinking)
            self.ai_chat_box.configure(state="normal")
            # Buscar y borrar la línea de thinking
            content = self.ai_chat_box.get("1.0", "end")
            thinking = self.tr("ai_thinking") + "\n"
            idx = content.rfind(thinking)
            if idx >= 0:
                line_start = content[:idx].count("\n") + 1
                self.ai_chat_box.delete(f"{line_start}.0", f"{line_start}.end+1c")
            self.ai_chat_box.configure(state="disabled")
            tag = "error" if reply.startswith("❌") else "assistant"
            self._ai_append(f"Asistente: {reply}\n\n", tag)
            self.update_status("Asistente IA listo")
        self.after(0, _show)

    def _repopulate_chat(self) -> None:
        for turn in self.ai_assistant.history:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role == "user":
                self._ai_append("─" * 72 + "\n", "sep")
                self._ai_append(f"Tú: {content}\n", "user")
            elif role == "assistant":
                self._ai_append(f"Asistente: {content}\n\n", "assistant")

    def _ai_clear(self) -> None:
        self.ai_assistant.clear_history()
        self.ai_chat_box.configure(state="normal")
        self.ai_chat_box.delete("1.0", "end")
        self.ai_chat_box.configure(state="disabled")
        self.update_status("Chat de IA limpiado")

    # ------------------------------------------------------------------
    # Optimizer
    # ------------------------------------------------------------------
    def show_optimizer(self) -> None:
        page = self._page(
            "optimizer",
            self.tr("optimizer_title"),
            self.tr("optimizer_subtitle"),
        )

        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=1)

        options = ctk.CTkFrame(top, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        options.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=5)
        ctk.CTkLabel(options, text="Categorías de escaneo", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 8)
        )
        for key, label in SCAN_CATEGORIES.items():
            ctk.CTkCheckBox(options, text=label, variable=self.scan_vars[key]).pack(anchor="w", padx=18, pady=5)

        actions = ctk.CTkFrame(top, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        actions.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=5)
        ctk.CTkLabel(actions, text="Acciones", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        row = ctk.CTkFrame(actions, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=4)
        self._button(row, "🔍 Escanear", self.start_scan, "accent", width=145).pack(side="left", padx=(0, 8))
        self._button(row, "✅ Reparar", self.fix_all_issues, "accent2", width=145).pack(side="left", padx=8)
        self._button(row, "🛡 Backup", self.create_backup, "warn", width=145).pack(side="left", padx=8)

        self.scan_status_label = ctk.CTkLabel(
            actions,
            text="Listo para escanear.",
            text_color=COLORS["muted"],
            anchor="w",
            justify="left",
        )
        self.scan_status_label.pack(fill="x", padx=16, pady=(12, 4))
        self.scan_progress = ctk.CTkProgressBar(actions)
        self.scan_progress.pack(fill="x", padx=16, pady=(4, 14))
        self.scan_progress.set(0)

        lower = ctk.CTkFrame(page, fg_color="transparent")
        lower.pack(fill="both", expand=True, pady=(10, 0))
        lower.grid_columnconfigure(0, weight=1)
        lower.grid_columnconfigure(1, weight=1)
        lower.grid_rowconfigure(0, weight=1)

        results_frame = ctk.CTkFrame(lower, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        results_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(results_frame, text="Resultados", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 8)
        )
        self.results_text = ctk.CTkTextbox(results_frame, height=280, font=ctk.CTkFont(family="Consolas", size=12))
        self.results_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", self._format_scan_results())
        self.results_text.configure(state="disabled")

        log_frame = ctk.CTkFrame(lower, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        log_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(log_frame, text="Log de operaciones", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 8)
        )
        self.log_text = ctk.CTkTextbox(log_frame, height=280, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.log_text.configure(state="disabled")

    def _selected_categories(self) -> List[str]:
        selected = [key for key, var in self.scan_vars.items() if var.get()]
        return selected or list(SCAN_CATEGORIES.keys())

    def start_scan(self) -> None:
        if self.scanning:
            self.update_status("Ya hay un escaneo en ejecución.")
            return
        self.scanning = True
        self.update_status("Escaneando sistema...")
        if hasattr(self, "scan_status_label") and self.scan_status_label.winfo_exists():
            self.scan_status_label.configure(text="Escaneando... esto no modifica tu equipo.")
            self.scan_progress.set(0.15)
        if hasattr(self, "results_text") and self.results_text.winfo_exists():
            self.results_text.configure(state="normal")
            self.results_text.delete("1.0", "end")
            self.results_text.insert("1.0", "Escaneo en progreso...\n")
            self.results_text.configure(state="disabled")
        threading.Thread(target=self._run_scan_thread, args=(self._selected_categories(),), daemon=True).start()

    def _run_scan_thread(self, categories: List[str]) -> None:
        try:
            self.log("Iniciando escaneo seguro")
            results = self.cleaner.scan(categories)
            for key, data in results.items():
                self.scan_results[key] = data
            self.last_scan_timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.after(0, self._display_scan_results)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Error de escaneo", str(exc)))
        finally:
            self.scanning = False
            self.update_status("Escaneo terminado")

    def _display_scan_results(self) -> None:
        total = self.total_current_issues()
        if hasattr(self, "scan_status_label") and self.scan_status_label.winfo_exists():
            self.scan_status_label.configure(text=f"Último escaneo: {self.last_scan_timestamp} · Issues encontrados: {total}")
            self.scan_progress.set(1)
        if hasattr(self, "results_text") and self.results_text.winfo_exists():
            self.results_text.configure(state="normal")
            self.results_text.delete("1.0", "end")
            self.results_text.insert("1.0", self._format_scan_results())
            self.results_text.configure(state="disabled")
        self.log(f"Escaneo terminado: {total} issue(s)")

    def _format_scan_results(self) -> str:
        lines: List[str] = []
        if self.last_scan_timestamp:
            lines.append(f"=== ÚLTIMO ESCANEO: {self.last_scan_timestamp} ===")
        else:
            lines.append("=== SIN ESCANEO EN ESTA SESIÓN ===")
        lines.append(f"Total issues: {self.total_current_issues()}\n")

        for key, label in SCAN_CATEGORIES.items():
            data = self.scan_results.get(key, {})
            issues = data.get("issues", []) or []
            errors = data.get("errors", []) or []
            lines.append(f"[{label}] {len(issues)} issue(s)")
            if key == "temp_files" and issues:
                total_size = sum(int(i.get("size", 0) or 0) for i in issues)
                lines.append(f"  Tamaño estimado recuperable: {format_bytes(total_size)}")
            for issue in issues[:20]:
                descriptor = issue.get("path") or issue.get("title")
                lines.append(f"  • {descriptor}")
            if len(issues) > 20:
                lines.append(f"  ... y {len(issues) - 20} más")
            if errors:
                lines.append(f"  Errores/avisos: {len(errors)}")
                for err in errors[:5]:
                    lines.append(f"    - {err}")
            lines.append("")
        lines.append("Nota: 'Reparar' creará backup si está activado y pedirá confirmación antes de modificar.")
        return "\n".join(lines)

    def create_backup(self, show_message: bool = True) -> Optional[Path]:
        backup_dir = self.backup_path / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        try:
            snapshot = backup_dir / "scan_snapshot.json"
            with open(snapshot, "w", encoding="utf-8") as fh:
                json.dump(self.scan_results, fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            self.log(f"No se pudo guardar snapshot del escaneo: {exc}")

        if IS_WINDOWS:
            exports = [
                ("HKCU", "HKEY_CURRENT_USER"),
                ("HKCU_Run", r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"),
                ("HKLM_Run", r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                ("HKLM_SharedDLLs", r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\SharedDLLs"),
            ]
            for name, key in exports:
                try:
                    run_capture(["reg", "export", key, str(backup_dir / f"{name}.reg"), "/y"], timeout=30)
                except Exception as exc:
                    self.log(f"No se pudo exportar {key}: {exc}")

        if IS_WINDOWS and HAS_WINDOWS_AUTOMATION:
            try:
                shortcuts_dir = backup_dir / "shortcuts"
                shortcuts_dir.mkdir(exist_ok=True)
                for location in self.cleaner._shortcut_locations():
                    for item in Path(location).glob("*.lnk"):
                        try:
                            shutil.copy2(item, shortcuts_dir / item.name)
                        except Exception:
                            pass
            except Exception as exc:
                self.log(f"No se pudieron respaldar accesos directos: {exc}")

        self.log(f"Backup creado: {backup_dir}")
        self.update_status(f"Backup creado en {backup_dir}")
        if show_message and hasattr(self, "log_text") and self.log_text.winfo_exists():
            messagebox.showinfo("Backup creado", f"Backup guardado en:\n{backup_dir}")
        return backup_dir

    def fix_all_issues(self) -> None:
        if self.fixing:
            self.update_status("Ya hay una reparación en ejecución.")
            return
        total = self.total_current_issues()
        if total == 0:
            messagebox.showinfo(
                "Sin issues",
                "No hay issues detectados para reparar. Ejecuta un escaneo primero.",
            )
            return
        if not messagebox.askyesno(
            "Confirmar reparación",
            f"Se intentarán reparar {total} issue(s).\n\n"
            "Si backup está activado, se creará un respaldo antes de modificar.\n"
            "¿Continuar?",
            icon="warning",
        ):
            return
        self.fixing = True
        self.update_status("Reparando issues...")
        threading.Thread(target=self._run_fix_thread, daemon=True).start()

    def _run_fix_thread(self) -> None:
        backup_dir: Optional[Path] = None
        if self.config_data.get("backup_enabled", True):
            backup_dir = self.create_backup(show_message=False)
        fixed = 0
        failed = 0
        new_results = {key: {"issues": [], "errors": [], "timestamp": data.get("timestamp")} for key, data in self.scan_results.items()}
        try:
            for category, data in self.scan_results.items():
                for issue in data.get("issues", []) or []:
                    ok, msg = self.cleaner.fix_issue(issue, backup_dir=backup_dir)
                    if ok:
                        fixed += 1
                        self.log(f"OK: {msg}")
                    else:
                        failed += 1
                        new_results[category]["issues"].append(issue)
                        new_results[category]["errors"].append(msg)
                        self.log(f"ERROR: {msg}")
            self.scan_results = new_results
            self.after(0, lambda: self._display_fix_results(fixed, failed))
        finally:
            self.fixing = False

    def _display_fix_results(self, fixed: int, failed: int) -> None:
        self.update_status(f"Reparación terminada: {fixed} OK, {failed} error(es)")
        if hasattr(self, "results_text") and self.results_text.winfo_exists():
            self.results_text.configure(state="normal")
            self.results_text.delete("1.0", "end")
            self.results_text.insert("1.0", self._format_scan_results())
            self.results_text.configure(state="disabled")
        messagebox.showinfo("Reparación finalizada", f"Reparados: {fixed}\nCon error: {failed}")

    # ------------------------------------------------------------------
    # Command Center
    # ------------------------------------------------------------------
    def show_command_center(self) -> None:
        page = self._page(
            "commands",
            self.tr("commands_title"),
            self.tr("commands_subtitle"),
        )
        if not IS_WINDOWS:
            warn = ctk.CTkFrame(page, fg_color="#3b2505", corner_radius=12)
            warn.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(
                warn,
                text="⚠️ Esta biblioteca está pensada principalmente para Windows. Algunas ejecuciones pueden no funcionar aquí.",
                text_color="#fbbf24",
            ).pack(anchor="w", padx=14, pady=10)

        layout = ctk.CTkFrame(page, fg_color="transparent")
        layout.pack(fill="both", expand=True)
        layout.grid_columnconfigure(0, weight=0)
        layout.grid_columnconfigure(1, weight=1)
        layout.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(layout, width=270, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Buscar", text_color=COLORS["muted"]).pack(anchor="w", padx=12, pady=(14, 4))
        self.cmd_search_var = tk.StringVar()
        self.cmd_search_var.trace_add("write", lambda *_: self._filter_commands())
        ctk.CTkEntry(left, textvariable=self.cmd_search_var, placeholder_text="ping, DNS, disco...").pack(
            fill="x", padx=12, pady=(0, 8)
        )

        ctk.CTkLabel(left, text="Categoría", text_color=COLORS["muted"]).pack(anchor="w", padx=12, pady=(2, 4))
        self.cmd_category_var = tk.StringVar(value="Todas")
        categories = ["Todas"] + sorted({cmd["cat"] for cmd in WIN_COMMANDS})
        self.cmd_category_menu = ctk.CTkOptionMenu(left, values=categories, variable=self.cmd_category_var, command=lambda _: self._filter_commands())
        self.cmd_category_menu.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(left, text="Comandos", font=ctk.CTkFont(weight="bold"), text_color=COLORS["muted"]).pack(
            anchor="w", padx=12, pady=(4, 4)
        )
        list_frame = ctk.CTkFrame(left, fg_color=COLORS["surface2"], corner_radius=8)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.cmd_listbox = tk.Listbox(
            list_frame,
            bg=COLORS["surface2"],
            fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="white",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            font=("Consolas", 10),
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.cmd_listbox.yview)
        self.cmd_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.cmd_listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.cmd_listbox.bind("<<ListboxSelect>>", self._on_command_selected)

        right = ctk.CTkFrame(layout, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(6, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.cmd_title_var = tk.StringVar(value="Selecciona un comando")
        self.cmd_desc_var = tk.StringVar(value="")
        self.cmd_shell_var = tk.StringVar(value="")
        info = ctk.CTkFrame(right, fg_color="transparent")
        info.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        ctk.CTkLabel(info, textvariable=self.cmd_title_var, font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(info, textvariable=self.cmd_shell_var, text_color=COLORS["purple"]).pack(anchor="w")
        ctk.CTkLabel(info, textvariable=self.cmd_desc_var, text_color=COLORS["muted"], wraplength=760, justify="left").pack(
            anchor="w", pady=(4, 0)
        )

        self.cmd_params_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.cmd_params_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=4)

        preview = ctk.CTkFrame(right, fg_color=COLORS["surface2"], corner_radius=10)
        preview.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        ctk.CTkLabel(preview, text="Preview", text_color=COLORS["muted"]).pack(anchor="w", padx=12, pady=(8, 0))
        self.cmd_preview_var = tk.StringVar(value="")
        ctk.CTkLabel(preview, textvariable=self.cmd_preview_var, text_color=COLORS["accent2"], wraplength=760, justify="left").pack(
            anchor="w", padx=12, pady=(0, 8)
        )

        tutor = ctk.CTkFrame(right, fg_color=COLORS["surface2"], corner_radius=10)
        tutor.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        ctk.CTkLabel(tutor, text="Command Tutor (?)", text_color=COLORS["muted"], font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=12, pady=(8, 2)
        )
        tutor_row = ctk.CTkFrame(tutor, fg_color="transparent")
        tutor_row.pack(fill="x", padx=12, pady=(0, 8))
        self.command_help_input_var = tk.StringVar(value="ipconfig ?")
        ctk.CTkEntry(tutor_row, textvariable=self.command_help_input_var, placeholder_text="Ej: netsh wlan show ?").pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self._button(tutor_row, "Consultar ?", self._ask_command_tutor, "accent", width=125).pack(side="left")
        self.command_help_text = ctk.CTkTextbox(tutor, height=112, font=ctk.CTkFont(family="Consolas", size=11))
        self.command_help_text.pack(fill="x", padx=12, pady=(0, 10))
        self.command_help_text.configure(state="normal")
        self.command_help_text.insert("1.0", command_tutor_response("ipconfig ?"))
        self.command_help_text.configure(state="disabled")

        buttons = ctk.CTkFrame(right, fg_color="transparent")
        buttons.grid(row=4, column=0, sticky="ew", padx=16, pady=4)
        self._button(buttons, "▶ Ejecutar aquí", self._run_command_inline, "accent2", width=145).pack(side="left", padx=(0, 8))
        self._button(buttons, "🖥 Abrir CMD", lambda: self._run_command_external("cmd"), "warn", width=130).pack(side="left", padx=8)
        self._button(buttons, "💙 PowerShell", lambda: self._run_command_external("powershell"), "purple", width=145).pack(side="left", padx=8)
        self._button(buttons, "Ayuda ?", self._ask_command_tutor, "accent", width=110).pack(side="left", padx=8)
        self._button(buttons, "Limpiar", self._clear_command_output, "surface3", width=120).pack(side="left", padx=8)

        ctk.CTkLabel(right, text="Salida", text_color=COLORS["muted"], font=ctk.CTkFont(weight="bold")).grid(
            row=5, column=0, sticky="w", padx=16, pady=(8, 2)
        )
        output_frame = ctk.CTkFrame(right, fg_color="#020617", corner_radius=10)
        output_frame.grid(row=6, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.command_output = tk.Text(
            output_frame,
            bg="#020617",
            fg="#22c55e",
            insertbackground="#22c55e",
            relief="flat",
            borderwidth=0,
            font=("Consolas", 10),
            wrap="word",
        )
        out_scroll = ttk.Scrollbar(output_frame, orient="vertical", command=self.command_output.yview)
        self.command_output.configure(yscrollcommand=out_scroll.set, state="disabled")
        out_scroll.pack(side="right", fill="y")
        self.command_output.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self.command_output.tag_configure("cmd", foreground=COLORS["muted"])
        self.command_output.tag_configure("out", foreground=COLORS["accent2"])
        self.command_output.tag_configure("err", foreground=COLORS["danger"])
        self.command_output.tag_configure("info", foreground=COLORS["accent"])
        self.command_output.tag_configure("sep", foreground=COLORS["border"])

        self._visible_commands = list(WIN_COMMANDS)
        self._populate_command_list()

    def _populate_command_list(self) -> None:
        if not hasattr(self, "cmd_listbox"):
            return
        self.cmd_listbox.delete(0, "end")
        for cmd in self._visible_commands:
            self.cmd_listbox.insert("end", f"  {cmd['name']}")

    def _filter_commands(self) -> None:
        query = self.cmd_search_var.get().strip().lower() if hasattr(self, "cmd_search_var") else ""
        category = self.cmd_category_var.get() if hasattr(self, "cmd_category_var") else "Todas"
        self._visible_commands = []
        for cmd in WIN_COMMANDS:
            desc = cmd.get("desc", {}).get("es", "")
            haystack = f"{cmd.get('name', '')} {desc} {cmd.get('cat', '')}".lower()
            if category != "Todas" and cmd.get("cat") != category:
                continue
            if query and query not in haystack:
                continue
            self._visible_commands.append(cmd)
        self._populate_command_list()
        self._current_cmd = None
        self.cmd_title_var.set("Selecciona un comando")
        self.cmd_shell_var.set("")
        self.cmd_desc_var.set("")
        self.cmd_preview_var.set("")
        for widget in self.cmd_params_frame.winfo_children():
            widget.destroy()
        self._param_vars.clear()

    def _on_command_selected(self, _event: Any = None) -> None:
        selection = self.cmd_listbox.curselection()
        if not selection:
            return
        self._current_cmd = self._visible_commands[selection[0]]
        self._render_command_detail(self._current_cmd)

    def _render_command_detail(self, cmd: Dict[str, Any]) -> None:
        self.cmd_title_var.set(cmd.get("name", "Comando"))
        shell = cmd.get("shell", "cmd")
        self.cmd_shell_var.set("💙 PowerShell" if shell == "powershell" else "⬛ CMD")
        self.cmd_desc_var.set(cmd.get("desc", {}).get("es", ""))

        for widget in self.cmd_params_frame.winfo_children():
            widget.destroy()
        self._param_vars.clear()

        params = cmd.get("params", [])
        if params:
            ctk.CTkLabel(
                self.cmd_params_frame,
                text="Parámetros editables",
                text_color=COLORS["muted"],
                font=ctk.CTkFont(weight="bold"),
            ).pack(anchor="w", pady=(2, 6))
            for param in params:
                row = ctk.CTkFrame(self.cmd_params_frame, fg_color="transparent")
                row.pack(fill="x", pady=3)
                label = param.get("label", {}).get("es") or param.get("key", "param")
                ctk.CTkLabel(row, text=f"{label}:", width=145, anchor="w").pack(side="left")
                var = tk.StringVar(value=param.get("default", ""))
                var.trace_add("write", lambda *_: self._update_command_preview())
                self._param_vars[param["key"]] = var
                ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=(0, 8))
                hint = param.get("hint", "")
                if hint:
                    ctk.CTkLabel(row, text=hint, text_color=COLORS["muted"], width=210, anchor="w").pack(side="left")
        else:
            ctk.CTkLabel(self.cmd_params_frame, text="Este comando no requiere parámetros.", text_color=COLORS["muted"]).pack(
                anchor="w", pady=6
            )
        self._update_command_preview()
        if hasattr(self, "command_help_input_var"):
            base = (cmd.get("name") or "ipconfig").strip()
            self.command_help_input_var.set(f"{base} ?")
            self._set_command_help_text(command_tutor_response(f"{base} ?"))

    def _set_command_help_text(self, text: str) -> None:
        if not hasattr(self, "command_help_text") or not self.command_help_text.winfo_exists():
            return
        self.command_help_text.configure(state="normal")
        self.command_help_text.delete("1.0", "end")
        self.command_help_text.insert("1.0", text)
        self.command_help_text.configure(state="disabled")

    def _ask_command_tutor(self) -> None:
        query = ""
        if hasattr(self, "command_help_input_var"):
            query = self.command_help_input_var.get().strip()
        if not query:
            built, _shell = self._build_command_string()
            query = (built or "ipconfig") + " ?"
        self._set_command_help_text(command_tutor_response(query))

    def _build_command_string(self) -> Tuple[Optional[str], Optional[str]]:
        if not self._current_cmd:
            return None, None
        try:
            values = {key: var.get() for key, var in self._param_vars.items()}
            built = self._current_cmd["template"].format(**values).strip()
        except Exception:
            built = self._current_cmd.get("template", "").strip()
        return built, self._current_cmd.get("shell", "cmd")

    def _update_command_preview(self) -> None:
        built, _ = self._build_command_string()
        self.cmd_preview_var.set(built or "")

    def _command_is_risky(self, command: str) -> bool:
        low = f" {command.lower()} "
        return any(pattern in low for pattern in RISKY_COMMAND_PATTERNS)

    def _unsafe_param_key(self) -> Optional[str]:
        """Devuelve el nombre del primer parametro con caracteres no permitidos, si hay alguno.

        Los valores de parametro se insertan sin comillas en una plantilla que
        termina ejecutandose via cmd/powershell (o shell=True en Linux/Mac). Sin
        esta validacion, un valor como 'MiRed & del /s /q C:\\Users' se "escapa"
        del parametro e inyecta un segundo comando.
        """
        for key, var in self._param_vars.items():
            value = var.get()
            if any(ch in UNSAFE_PARAM_CHARS for ch in value):
                return key
        return None

    def _confirm_command_if_needed(self, command: str) -> bool:
        if not self._command_is_risky(command):
            return True
        return messagebox.askyesno(
            "Confirmar comando",
            "Este comando puede modificar el sistema o requerir permisos de administrador:\n\n"
            f"{command}\n\n¿Ejecutarlo de todas formas?",
            icon="warning",
        )

    def _block_if_unsafe_params(self) -> bool:
        """Muestra un error y retorna True si algun parametro tiene caracteres inseguros."""
        unsafe_key = self._unsafe_param_key()
        if not unsafe_key:
            return False
        messagebox.showerror(
            "Parámetro no válido",
            f"El parámetro '{unsafe_key}' contiene caracteres no permitidos "
            "(& | ; ` $ < > ^ \" ' % ( ) o saltos de línea) que podrían alterar "
            "el comando que se va a ejecutar.\n\nModifica el valor e inténtalo de nuevo.",
        )
        return True

    def _run_command_inline(self) -> None:
        built, shell = self._build_command_string()
        if not built or not shell:
            return
        if self._block_if_unsafe_params():
            return
        if not self._confirm_command_if_needed(built):
            return
        self._append_command_output("─" * 80 + "\n", "sep")
        self._append_command_output(f"▶ {built}\n", "cmd")
        self.update_status(f"Ejecutando: {built[:70]}")
        threading.Thread(target=self._exec_command_thread, args=(built, shell), daemon=True).start()

    def _exec_command_thread(self, cmd_str: str, shell: str) -> None:
        try:
            if IS_WINDOWS:
                args = ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd_str] if shell == "powershell" else ["cmd", "/c", cmd_str]
                proc = subprocess.Popen(args, **hidden_subprocess_kwargs(capture=True))
            else:
                proc = subprocess.Popen(cmd_str, shell=True, **hidden_subprocess_kwargs(capture=True))
            assert proc.stdout is not None
            assert proc.stderr is not None
            for line in proc.stdout:
                self._append_command_output(line, "out")
            for line in proc.stderr:
                self._append_command_output(line, "err")
            proc.wait()
            self._append_command_output(f"\n✔ Proceso terminado (código {proc.returncode})\n", "info")
            self.update_status(f"Comando terminado con código {proc.returncode}")
        except Exception as exc:
            self._append_command_output(f"Error: {exc}\n", "err")
            self.update_status(f"Error ejecutando comando: {exc}")

    def _run_command_external(self, shell_choice: str) -> None:
        built, _shell = self._build_command_string()
        if not built:
            return
        if not IS_WINDOWS:
            messagebox.showwarning("No disponible", "Abrir CMD/PowerShell externo está implementado para Windows.")
            return
        if self._block_if_unsafe_params():
            return
        if not self._confirm_command_if_needed(built):
            return
        try:
            if shell_choice == "powershell":
                subprocess.Popen(["powershell", "-NoExit", "-Command", built])
            else:
                subprocess.Popen(["cmd", "/k", built])
            self.update_status(f"Abierto en {shell_choice}: {built[:55]}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _append_command_output(self, text: str, tag: str = "out") -> None:
        def _do() -> None:
            if not hasattr(self, "command_output") or not self.command_output.winfo_exists():
                return
            self.command_output.configure(state="normal")
            self.command_output.insert("end", text, tag)
            self.command_output.see("end")
            self.command_output.configure(state="disabled")

        self.after(0, _do)

    def _clear_command_output(self) -> None:
        self.command_output.configure(state="normal")
        self.command_output.delete("1.0", "end")
        self.command_output.configure(state="disabled")


    # ------------------------------------------------------------------
    # Network Doctor
    # ------------------------------------------------------------------
    def show_network_doctor(self) -> None:
        page = self._page(
            "network",
            self.tr("network_title"),
            self.tr("network_subtitle"),
        )
        top = ctk.CTkFrame(page, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        top.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(top, text="Acciones de red", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 16))
        self._button(row, "Diagnosticar", self.start_network_diagnostic, "accent", width=140).pack(side="left", padx=(0, 8))
        self._button(row, "Flush DNS", lambda: self._run_network_repair("ipconfig /flushdns"), "accent2", width=130).pack(side="left", padx=8)
        self._button(row, "Release/Renew IP", lambda: self._run_network_repair("ipconfig /release && ipconfig /renew"), "warn", width=160).pack(side="left", padx=8)
        self._button(row, "Reset Winsock", lambda: self._run_network_repair("netsh winsock reset"), "danger", width=150).pack(side="left", padx=8)

        output_frame = ctk.CTkFrame(page, fg_color="#020617", corner_radius=14, border_width=1, border_color=COLORS["border"])
        output_frame.pack(fill="both", expand=True)
        self.network_output = tk.Text(output_frame, bg="#020617", fg="#e5e7eb", insertbackground="#e5e7eb", relief="flat", borderwidth=0, font=("Consolas", 10), wrap="word")
        scroll = ttk.Scrollbar(output_frame, orient="vertical", command=self.network_output.yview)
        self.network_output.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.network_output.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.network_output.insert("1.0", "Presiona 'Diagnosticar' para generar un reporte de conectividad.\n")

    def start_network_diagnostic(self) -> None:
        if hasattr(self, "network_output"):
            self.network_output.delete("1.0", "end")
            self.network_output.insert("1.0", "Ejecutando diagnostico de red...\n")
        self.update_status("Ejecutando Network Doctor...")
        self.log("Network diagnostic started")
        threading.Thread(target=self._network_diag_thread, daemon=True).start()

    def _network_diag_thread(self) -> None:
        report = NetworkDoctor.run_basic_diagnostic()
        self.after(0, lambda: self._set_plain_text("network_output", report))
        self.update_status("Network Doctor terminado")

    def _run_network_repair(self, command: str) -> None:
        if command.lower().strip() != "ipconfig /flushdns" and not self._requires_advanced():
            return
        if not IS_WINDOWS:
            messagebox.showwarning("No disponible", "Estas reparaciones estan pensadas para Windows.")
            return
        if not messagebox.askyesno("Confirmar reparacion de red", f"Se ejecutara:\n\n{command}\n\nPuede cortar temporalmente la conexion. Continuar?", icon="warning"):
            return
        if hasattr(self, "network_output"):
            self.network_output.insert("end", f"\n> {command}\n")
        threading.Thread(target=self._network_repair_thread, args=(command,), daemon=True).start()

    def _network_repair_thread(self, command: str) -> None:
        code, out = run_capture(["cmd", "/c", command], timeout=180)
        self.after(0, lambda: self._append_plain_text("network_output", f"\nCodigo {code}\n{out}\n"))
        self.log(f"Network repair executed: {command} | code={code}")
        self.update_status(f"Reparacion de red finalizada con codigo {code}")

    # ------------------------------------------------------------------
    # Disk Center
    # ------------------------------------------------------------------
    def show_disk_center(self) -> None:
        page = self._page(
            "disk",
            self.tr("disk_title"),
            self.tr("disk_subtitle"),
        )
        layout = ctk.CTkFrame(page, fg_color="transparent")
        layout.pack(fill="both", expand=True)
        layout.grid_columnconfigure(0, weight=1)
        layout.grid_columnconfigure(1, weight=1)
        layout.grid_rowconfigure(1, weight=1)

        volumes_card = ctk.CTkFrame(layout, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        volumes_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(volumes_card, text="Volumenes detectados", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        self.disk_volumes_frame = ctk.CTkFrame(volumes_card, fg_color="transparent")
        self.disk_volumes_frame.pack(fill="x", padx=16, pady=(0, 12))
        self.refresh_disk_volumes()

        finder = ctk.CTkFrame(layout, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        finder.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(finder, text="Buscar archivos grandes", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        path_row = ctk.CTkFrame(finder, fg_color="transparent")
        path_row.pack(fill="x", padx=16, pady=4)
        self.large_path_var = tk.StringVar(value=str(Path.home()))
        ctk.CTkEntry(path_row, textvariable=self.large_path_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._button(path_row, "Ruta", self._choose_large_file_path, "surface3", width=85).pack(side="left")
        size_row = ctk.CTkFrame(finder, fg_color="transparent")
        size_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(size_row, text="Minimo MB:", width=90, anchor="w").pack(side="left")
        self.large_min_mb_var = tk.StringVar(value="500")
        ctk.CTkEntry(size_row, textvariable=self.large_min_mb_var, width=100).pack(side="left", padx=(0, 8))
        self._button(size_row, "Buscar", self.start_find_large_files, "accent", width=110).pack(side="left")
        self.large_files_text = ctk.CTkTextbox(finder, height=260, font=ctk.CTkFont(family="Consolas", size=11))
        self.large_files_text.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        output = ctk.CTkFrame(layout, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        output.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(output, text="Salida de operaciones", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        self.disk_output = ctk.CTkTextbox(output, height=320, font=ctk.CTkFont(family="Consolas", size=11))
        self.disk_output.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.disk_output.insert("1.0", "Selecciona Analizar, Optimizar o CHKDSK en un volumen.\n")

    def refresh_disk_volumes(self) -> None:
        if not hasattr(self, "disk_volumes_frame"):
            return
        for widget in self.disk_volumes_frame.winfo_children():
            widget.destroy()
        volumes = DiskManager.list_volumes()
        if not volumes:
            ctk.CTkLabel(self.disk_volumes_frame, text="No se detectaron volumenes legibles.", text_color=COLORS["muted"]).pack(anchor="w")
            return
        for volume in volumes:
            row = ctk.CTkFrame(self.disk_volumes_frame, fg_color=COLORS["surface2"], corner_radius=10)
            row.pack(fill="x", pady=5)
            info = f"{volume['device']} | {volume['fstype']} | {volume['media_type']} | {volume['percent']:.0f}% usado | {format_bytes(volume['free'])} libres"
            ctk.CTkLabel(row, text=info, anchor="w").pack(side="left", fill="x", expand=True, padx=12, pady=9)
            progress = ctk.CTkProgressBar(row, width=120)
            progress.pack(side="left", padx=8)
            progress.set(float(volume["percent"]) / 100)
            drive = volume["drive_letter"]
            media = volume["media_type"]
            self._button(row, "Analizar", lambda d=drive: self.start_disk_operation("analyze", d), "accent", width=88).pack(side="left", padx=4)
            self._button(row, "Optimizar", lambda d=drive, m=media: self.start_disk_operation("optimize", d, m), "warn", width=92).pack(side="left", padx=4)
            self._button(row, "CHKDSK", lambda d=drive: self.start_disk_operation("chkdsk", d), "surface3", width=82).pack(side="left", padx=(4, 10))

    def start_disk_operation(self, action: str, drive: str, media_type: str = "Unknown") -> None:
        if action in {"optimize", "chkdsk"} and not self._requires_advanced():
            return
        if action in {"optimize", "chkdsk"}:
            label = "optimizar" if action == "optimize" else "ejecutar CHKDSK solo lectura"
            if not messagebox.askyesno("Confirmar", f"Se va a {label} en la unidad {drive}:\n\nContinuar?", icon="warning"):
                return
        if hasattr(self, "disk_output"):
            self.disk_output.delete("1.0", "end")
            self.disk_output.insert("1.0", f"Ejecutando {action} en {drive}:...\n")
        self.log(f"Disk operation started: {action} {drive}:")
        threading.Thread(target=self._disk_operation_thread, args=(action, drive, media_type), daemon=True).start()

    def _disk_operation_thread(self, action: str, drive: str, media_type: str) -> None:
        if action == "analyze":
            code, out = DiskManager.analyze_volume(drive)
        elif action == "optimize":
            code, out = DiskManager.optimize_volume(drive, media_type)
        else:
            code, out = DiskManager.chkdsk_readonly(drive)
        self.after(0, lambda: self._set_ctk_textbox("disk_output", f"Codigo {code}\n\n{out}"))
        self.log(f"Disk operation finished: {action} {drive}: code={code}")
        self.update_status(f"Disk Center: {action} finalizado con codigo {code}")

    def _choose_large_file_path(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.large_path_var.set(path)

    def start_find_large_files(self) -> None:
        try:
            min_mb = int(self.large_min_mb_var.get())
        except ValueError:
            messagebox.showerror("Valor invalido", "Ingresa un numero valido de MB.")
            return
        path = self.large_path_var.get()
        self._set_ctk_textbox("large_files_text", "Buscando archivos grandes...\n")
        threading.Thread(target=self._find_large_files_thread, args=(path, min_mb), daemon=True).start()

    def _find_large_files_thread(self, path: str, min_mb: int) -> None:
        files, errors = DiskManager.find_large_files(path, min_mb)
        lines = [f"Archivos >= {min_mb} MB en {path}", ""]
        if not files:
            lines.append("No se encontraron archivos que cumplan el criterio.")
        for item in files:
            lines.append(f"{format_bytes(item['size']):>12}  {item['path']}")
        if errors:
            lines.extend(["", "Avisos:"])
            lines.extend(errors[:10])
        self.after(0, lambda: self._set_ctk_textbox("large_files_text", "\n".join(lines)))

    # ------------------------------------------------------------------
    # Memory Inspector
    # ------------------------------------------------------------------
    def show_memory_inspector(self) -> None:
        page = self._page(
            "memory",
            self.tr("memory_title"),
            self.tr("memory_subtitle"),
        )
        warning = ctk.CTkFrame(page, fg_color="#3b2505", corner_radius=12)
        warning.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            warning,
            text="Aviso: liberar working set puede bajar la RAM visible temporalmente, pero algunas apps pueden tardar mas al volver a usarse.",
            text_color="#fbbf24",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=14, pady=10)

        cards = ctk.CTkFrame(page, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 10))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)
        self.memory_labels: Dict[str, ctk.CTkLabel] = {}
        for i, key_title in enumerate([("used", "RAM usada"), ("available", "Disponible"), ("total", "Total"), ("swap", "Swap")]):
            key, title = key_title
            card = ctk.CTkFrame(cards, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
            card.grid(row=0, column=i, padx=7, sticky="nsew")
            ctk.CTkLabel(card, text=title, text_color=COLORS["muted"]).pack(anchor="w", padx=16, pady=(12, 2))
            label = ctk.CTkLabel(card, text="-", font=ctk.CTkFont(size=22, weight="bold"))
            label.pack(anchor="w", padx=16, pady=(0, 12))
            self.memory_labels[key] = label

        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        actions = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        row = ctk.CTkFrame(actions, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=14)
        self._button(row, "Actualizar", self.refresh_memory_inspector, "accent", width=120).pack(side="left", padx=(0, 8))
        self._button(row, "Liberar seleccionado", self.trim_selected_process, "warn", width=165).pack(side="left", padx=8)
        self._button(row, "Liberar no criticos >150MB", self.trim_non_critical_processes, "danger", width=220).pack(side="left", padx=8)

        list_card = ctk.CTkFrame(body, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        list_card.grid(row=1, column=0, sticky="nsew")
        ctk.CTkLabel(list_card, text="Top procesos por RAM", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        list_frame = ctk.CTkFrame(list_card, fg_color="#020617", corner_radius=10)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.memory_process_list = tk.Listbox(list_frame, bg="#020617", fg="#e5e7eb", selectbackground=COLORS["accent"], relief="flat", borderwidth=0, highlightthickness=0, font=("Consolas", 10))
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.memory_process_list.yview)
        self.memory_process_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.memory_process_list.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.memory_process_map: List[Dict[str, Any]] = []
        self.refresh_memory_inspector()

    def refresh_memory_inspector(self) -> None:
        snap = MemoryManager.snapshot(limit=50)
        vm = snap["virtual"]
        swap = snap["swap"]
        if hasattr(self, "memory_labels"):
            self.memory_labels["used"].configure(text=f"{vm.percent:.0f}%")
            self.memory_labels["available"].configure(text=format_bytes(vm.available))
            self.memory_labels["total"].configure(text=format_bytes(vm.total))
            self.memory_labels["swap"].configure(text=f"{swap.percent:.0f}%")
        if hasattr(self, "memory_process_list"):
            self.memory_process_list.delete(0, "end")
            self.memory_process_map = snap["processes"]
            header = f"{'PID':>7}  {'RAM':>10}  {'%':>5}  NAME"
            self.memory_process_list.insert("end", header)
            self.memory_process_list.insert("end", "-" * len(header))
            for proc in self.memory_process_map:
                self.memory_process_list.insert(
                    "end",
                    f"{proc['pid']:>7}  {format_bytes(proc['rss']):>10}  {proc['memory_percent']:>5.1f}  {proc['name']}",
                )
        self.update_status("Memory Inspector actualizado")

    def _selected_memory_process(self) -> Optional[Dict[str, Any]]:
        if not hasattr(self, "memory_process_list"):
            return None
        sel = self.memory_process_list.curselection()
        if not sel:
            return None
        index = sel[0] - 2
        if 0 <= index < len(self.memory_process_map):
            return self.memory_process_map[index]
        return None

    def trim_selected_process(self) -> None:
        if not self._requires_advanced():
            return
        proc = self._selected_memory_process()
        if not proc:
            messagebox.showinfo("Selecciona proceso", "Selecciona un proceso de la lista primero.")
            return
        if proc["pid"] == os.getpid():
            messagebox.showwarning("No recomendado", f"No se liberará la memoria del propio {self.app_name()} para evitar inestabilidad.")
            return
        if not messagebox.askyesno("Confirmar", f"Liberar working set de:\n\n{proc['name']} (PID {proc['pid']})\n\nContinuar?", icon="warning"):
            return
        ok, msg = MemoryManager.empty_working_set(int(proc["pid"]))
        if ok:
            messagebox.showinfo("OK", msg)
        else:
            messagebox.showerror("Error", msg)
        self.refresh_memory_inspector()

    def trim_non_critical_processes(self) -> None:
        if not self._requires_advanced():
            return
        if not messagebox.askyesno(
            "Confirmar liberacion de RAM",
            "Se intentara liberar working set de procesos no criticos con mas de 150 MB de RAM.\n\nPuede causar lentitud momentanea al volver a abrir aplicaciones. Continuar?",
            icon="warning",
        ):
            return
        self.update_status("Liberando working set de procesos no criticos...")
        threading.Thread(target=self._trim_non_critical_thread, daemon=True).start()

    def _trim_non_critical_thread(self) -> None:
        ok_count, fail_count, messages = MemoryManager.trim_non_critical(150)
        msg = f"Procesos liberados: {ok_count}\nFallos: {fail_count}\n\n" + "\n".join(messages[:30])
        self.after(0, lambda: messagebox.showinfo("Resultado Memory Inspector", msg))
        self.after(0, self.refresh_memory_inspector)
        self.log(f"Memory trim finished: {ok_count} OK, {fail_count} failures")
        self.update_status(f"Memory trim terminado: {ok_count} OK, {fail_count} fallos")

    # ------------------------------------------------------------------
    # Text helpers for tool pages
    # ------------------------------------------------------------------
    def _set_ctk_textbox(self, attr: str, text: str, keep_editable: bool = False) -> None:
        box = getattr(self, attr, None)
        if not box:
            return
        try:
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", text)
            if not keep_editable:
                box.configure(state="disabled")
        except Exception:
            pass

    def _on_alert(self, alert_key: str, message: str) -> None:
        """Callback del AlertMonitor; se llama desde hilo daemon."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._alert_history.append((timestamp, alert_key, message))
        # Máximo 100 alertas en memoria
        if len(self._alert_history) > 100:
            self._alert_history = self._alert_history[-100:]

        def _show() -> None:
            label = self.tr(alert_key) if alert_key in (
                I18N.get(resolve_language(self.config_data), I18N["en"])
            ) else f"⚠️ {alert_key}"
            self.update_status(f"{label}: {message}")
            # Si el dashboard está visible, refrescar badge de alertas
            if self.current_page == "dashboard" and hasattr(self, "alert_badge_label"):
                count = len(self._alert_history)
                self.alert_badge_label.configure(
                    text=f"🔔 {count} alerta(s) hoy",
                    text_color=COLORS["warn"],
                )
        try:
            self.after(0, _show)
        except Exception:
            pass

    def _set_plain_text(self, attr: str, text: str) -> None:
        box = getattr(self, attr, None)
        if not box:
            return
        try:
            box.delete("1.0", "end")
            box.insert("1.0", text)
        except Exception:
            pass

    def _append_plain_text(self, attr: str, text: str) -> None:
        box = getattr(self, attr, None)
        if not box:
            return
        try:
            box.insert("end", text)
            box.see("end")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Power Center
    # ------------------------------------------------------------------
    def show_power_center(self) -> None:
        page = self._page(
            "power",
            self.tr("power_title"),
            self.tr("power_subtitle"),
        )

        grid = ctk.CTkFrame(page, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        immediate = ctk.CTkFrame(grid, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        immediate.grid(row=0, column=0, sticky="nsew", padx=(0, 9), pady=5)
        ctk.CTkLabel(immediate, text="Energía inmediata", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 10)
        )
        row = ctk.CTkFrame(immediate, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=6)
        self._button(row, "🔴 Apagar ahora", lambda: self._confirm_system_action("Apagar el equipo ahora", cmd_shutdown()), "danger").pack(
            side="left", fill="x", expand=True, padx=(0, 5)
        )
        self._button(row, "🔄 Reiniciar ahora", lambda: self._confirm_system_action("Reiniciar el equipo ahora", cmd_restart()), "warn").pack(
            side="left", fill="x", expand=True, padx=(5, 0)
        )

        session = ctk.CTkFrame(grid, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        session.grid(row=0, column=1, sticky="nsew", padx=(9, 0), pady=5)
        ctk.CTkLabel(session, text="Sesión", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 10))
        srow = ctk.CTkFrame(session, fg_color="transparent")
        srow.pack(fill="x", padx=16, pady=6)
        self._button(srow, "🔒 Bloquear", lambda: run_cmd(cmd_lock(), self._cmd_error), "accent").pack(
            side="left", fill="x", expand=True, padx=(0, 5)
        )
        self._button(srow, "😴 Suspender", lambda: self._confirm_system_action("Suspender el equipo", cmd_sleep()), "purple").pack(
            side="left", fill="x", expand=True, padx=(5, 0)
        )
        if IS_WINDOWS:
            self._button(session, "🚪 Cerrar sesión", lambda: self._confirm_system_action("Cerrar la sesión de Windows", ["shutdown", "/l"]), "surface3").pack(
                fill="x", padx=16, pady=(8, 16)
            )

        timer = ctk.CTkFrame(grid, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        timer.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(14, 5))
        ctk.CTkLabel(timer, text="Temporizador programado", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 8)
        )

        input_row = ctk.CTkFrame(timer, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(input_row, text="Minutos:").pack(side="left")
        self.minutes_var = tk.StringVar(value="30")
        ctk.CTkEntry(input_row, textvariable=self.minutes_var, width=90).pack(side="left", padx=8)
        for minutes in [5, 15, 30, 60, 120]:
            ctk.CTkButton(input_row, text=f"{minutes}m", width=54, command=lambda m=minutes: self.minutes_var.set(str(m))).pack(
                side="left", padx=3
            )

        action_row = ctk.CTkFrame(timer, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=8)
        self._button(action_row, "⏰ Apagar en X min", self._schedule_shutdown, "danger", width=170).pack(side="left", padx=(0, 8))
        self._button(action_row, "🔄 Reiniciar en X min", self._schedule_restart, "warn", width=185).pack(side="left", padx=8)
        self._button(action_row, "✖ Cancelar temporizador", self._cancel_timer, "surface3", width=205).pack(side="left", padx=8)

        self.countdown_var = tk.StringVar(value="Sin temporizador activo")
        ctk.CTkLabel(timer, textvariable=self.countdown_var, text_color=COLORS["accent2"], font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", padx=16, pady=(6, 2)
        )
        self.countdown_progress = ctk.CTkProgressBar(timer)
        self.countdown_progress.pack(fill="x", padx=16, pady=(0, 16))
        self.countdown_progress.set(0)

        tools = ctk.CTkFrame(grid, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        tools.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ctk.CTkLabel(tools, text="Herramientas rápidas", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 8)
        )
        tool_row = ctk.CTkFrame(tools, fg_color="transparent")
        tool_row.pack(fill="x", padx=16, pady=(0, 16))
        if IS_WINDOWS:
            self._button(tool_row, "📋 Task Manager", lambda: run_cmd(["taskmgr"], self._cmd_error), "accent", width=150).pack(side="left", padx=(0, 8))
            self._button(tool_row, "⚙️ Panel de control", lambda: run_cmd(["control"], self._cmd_error), "purple", width=170).pack(side="left", padx=8)
        elif IS_LINUX:
            self._button(tool_row, "📋 System Monitor", lambda: run_cmd(["gnome-system-monitor"], self._cmd_error), "accent", width=170).pack(side="left", padx=(0, 8))
        elif IS_MAC:
            self._button(tool_row, "📋 Activity Monitor", lambda: run_cmd(["open", "-a", "Activity Monitor"], self._cmd_error), "accent", width=180).pack(side="left", padx=(0, 8))
        self._button(tool_row, "💻 Terminal", self._open_terminal, "surface3", width=150).pack(side="left", padx=8)

        if self.countdown_active:
            self._tick_countdown()

    def _cmd_error(self, msg: str) -> None:
        messagebox.showerror("Error", msg)

    def _confirm_system_action(self, description: str, command: List[str]) -> None:
        if messagebox.askyesno("Confirmar", f"¿Deseas {description}?", icon="warning"):
            run_cmd(command, self._cmd_error, hidden=True)

    def _minutes_value(self) -> Optional[int]:
        try:
            minutes = int(self.minutes_var.get())
            if minutes <= 0:
                raise ValueError
            return minutes
        except Exception:
            messagebox.showerror("Error", "Ingresa un número de minutos válido (> 0).")
            return None

    def _schedule_shutdown(self) -> None:
        minutes = self._minutes_value()
        if minutes:
            self._start_countdown(minutes, "apagado", cmd_shutdown(minutes * 60))

    def _schedule_restart(self) -> None:
        minutes = self._minutes_value()
        if minutes:
            self._start_countdown(minutes, "reinicio", cmd_restart(minutes * 60))

    def _start_countdown(self, minutes: int, action: str, command: List[str]) -> None:
        if self.countdown_active:
            messagebox.showwarning("Aviso", "Ya hay un temporizador activo. Cancélalo primero.")
            return
        if not run_cmd(command, self._cmd_error, hidden=True):
            return
        self.countdown_active = True
        self.countdown_total_seconds = minutes * 60
        self.countdown_end_time = time.time() + self.countdown_total_seconds
        self.update_status(f"{action.capitalize()} programado en {minutes} minutos")
        self._tick_countdown()

    def _tick_countdown(self) -> None:
        if not self.countdown_active:
            return
        remaining = max(0, int(self.countdown_end_time - time.time()))
        minutes, seconds = divmod(remaining, 60)
        hours, minutes = divmod(minutes, 60)
        text = f"Tiempo restante: {hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"Tiempo restante: {minutes:02d}:{seconds:02d}"
        self.countdown_var.set(text)
        if hasattr(self, "countdown_progress") and self.countdown_progress.winfo_exists():
            done = 1 - (remaining / max(1, self.countdown_total_seconds))
            self.countdown_progress.set(max(0, min(1, done)))
        if remaining <= 0:
            self.countdown_active = False
            self.countdown_var.set("Acción ejecutada")
            if hasattr(self, "countdown_progress") and self.countdown_progress.winfo_exists():
                self.countdown_progress.set(1)
            return
        self.after(500, self._tick_countdown)

    def _cancel_timer(self) -> None:
        if not self.countdown_active:
            messagebox.showinfo("Info", "No hay temporizador activo.")
            return
        run_cmd(cmd_cancel_shutdown(), self._cmd_error, hidden=True)
        self.countdown_active = False
        if hasattr(self, "countdown_var"):
            self.countdown_var.set("Temporizador cancelado")
        if hasattr(self, "countdown_progress") and self.countdown_progress.winfo_exists():
            self.countdown_progress.set(0)
        self.update_status("Temporizador cancelado")

    def _open_terminal(self) -> None:
        if IS_WINDOWS:
            run_cmd(["cmd.exe"], self._cmd_error)
        elif IS_MAC:
            run_cmd(["open", "-a", "Terminal"], self._cmd_error)
        else:
            for terminal in ["gnome-terminal", "xterm", "konsole", "xfce4-terminal"]:
                try:
                    subprocess.Popen([terminal])
                    return
                except FileNotFoundError:
                    continue
            messagebox.showerror("Error", "No se encontró un emulador de terminal.")

    # ------------------------------------------------------------------
    # Report Center
    # ------------------------------------------------------------------
    def show_report_center(self) -> None:
        page = self._page("reports", self.tr("reports_title"), self.tr("reports_subtitle"))
        panel = ctk.CTkFrame(page, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        panel.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(panel, text=self.tr("reports_title"), font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 16))
        self._button(row, self.tr("generate_html_report"), self.generate_html_report, "accent", width=190).pack(side="left", padx=(0, 8))
        self._button(row, self.tr("open_reports_folder"), self.open_reports_folder, "surface3", width=190).pack(side="left", padx=8)

        output = ctk.CTkFrame(page, fg_color="#020617", corner_radius=14, border_width=1, border_color=COLORS["border"])
        output.pack(fill="both", expand=True)
        self.report_output = ctk.CTkTextbox(output, font=ctk.CTkFont(family="Consolas", size=11))
        self.report_output.pack(fill="both", expand=True, padx=16, pady=16)
        last = self.config_data.get("last_report_path", "")
        self.report_output.insert("1.0", f"{self.tr('last_report')}: {last if last else '-'}\n")

    def reports_dir(self) -> Path:
        base = Path(self.config_data.get("install_path", str(Path.home() / "StrallozData")))
        path = base / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def open_reports_folder(self) -> None:
        path = self.reports_dir()
        try:
            if IS_WINDOWS:
                os.startfile(path)  # type: ignore[attr-defined]
            elif IS_MAC:
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def generate_html_report(self) -> None:
        self.update_status("Generando reporte técnico...")
        if hasattr(self, "report_output"):
            self.report_output.delete("1.0", "end")
            self.report_output.insert("1.0", "Generando reporte técnico...\n")
        threading.Thread(target=self._generate_html_report_thread, daemon=True).start()

    def _generate_html_report_thread(self) -> None:
        try:
            report_path = self._build_html_report()
            self.config_data["last_report_path"] = str(report_path)
            ConfigManager.save_config(self.config_data)
            self.log(f"Technical report generated: {report_path}")
            msg = f"{self.tr('report_ready')}:\n{report_path}"
            self.after(0, lambda: self._set_ctk_textbox("report_output", msg))
            self.update_status(self.tr("report_ready"))
        except Exception as exc:
            self.after(0, lambda: self._set_ctk_textbox("report_output", f"Error generando reporte: {exc}"))
            self.update_status(f"Error generando reporte: {exc}")

    def _build_html_report(self) -> Path:
        import html
        now = datetime.now()
        report_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", self.app_name()).strip("_") or "Report"
        path = self.reports_dir() / f"{report_slug}_Report_{now.strftime('%Y%m%d_%H%M%S')}.html"
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        cpu_name = platform.processor() or "Unknown"
        rows = []
        rows.append(("Equipo", platform.node()))
        rows.append(("Sistema operativo", f"{platform.system()} {platform.release()} {platform.version()}"))
        rows.append(("CPU", cpu_name))
        rows.append(("Núcleos", str(psutil.cpu_count(logical=True))))
        rows.append(("RAM total", format_bytes(vm.total)))
        rows.append(("RAM usada", f"{vm.percent:.0f}%"))
        rows.append(("Swap usado", f"{swap.percent:.0f}%"))

        disks_html = []
        for vol in DiskManager.list_volumes():
            disks_html.append(
                f"<tr><td>{html.escape(vol['device'])}</td><td>{html.escape(vol['fstype'])}</td>"
                f"<td>{html.escape(str(vol['media_type']))}</td><td>{vol['percent']:.0f}%</td>"
                f"<td>{html.escape(format_bytes(vol['free']))}</td><td>{html.escape(format_bytes(vol['total']))}</td></tr>"
            )
        if not disks_html:
            disks_html.append("<tr><td colspan='6'>No se detectaron volúmenes legibles.</td></tr>")

        processes = MemoryManager.snapshot(limit=15)["processes"]
        proc_html = []
        for proc in processes:
            proc_html.append(
                f"<tr><td>{proc['pid']}</td><td>{html.escape(proc['name'])}</td>"
                f"<td>{html.escape(format_bytes(proc['rss']))}</td><td>{proc['memory_percent']:.1f}%</td></tr>"
            )

        network_report = NetworkDoctor.run_basic_diagnostic()
        issue_rows = []
        for key, label in SCAN_CATEGORIES.items():
            data = self.scan_results.get(key, {})
            issue_rows.append(f"<tr><td>{html.escape(label)}</td><td>{len(data.get('issues', []))}</td><td>{len(data.get('errors', []))}</td></tr>")

        log_excerpt = ""
        try:
            log_dir = Path(self.config_data.get("install_path", str(Path.home() / "StrallozData"))) / "logs"
            today_log = log_dir / f"actions_{now.strftime('%Y-%m-%d')}.log"
            if today_log.exists():
                lines = today_log.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
                log_excerpt = "\n".join(lines)
        except Exception:
            log_excerpt = ""

        def table_rows(items: List[Tuple[str, str]]) -> str:
            return "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in items)

        css = """
body{font-family:Segoe UI,Arial,sans-serif;background:#0b1220;color:#e5e7eb;margin:0;padding:24px}
h1{color:#60a5fa;margin-bottom:4px}.muted{color:#94a3b8}.card{background:#111827;border:1px solid #334155;border-radius:14px;padding:18px;margin:16px 0}
table{width:100%;border-collapse:collapse;margin-top:10px}td,th{border-bottom:1px solid #334155;padding:8px;text-align:left;vertical-align:top}th{color:#bfdbfe;width:240px}pre{white-space:pre-wrap;background:#020617;border:1px solid #334155;border-radius:10px;padding:12px;overflow:auto}.ok{color:#22c55e}.warn{color:#f59e0b}
"""
        content = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>{html.escape(self.app_name())} - Reporte</title><style>{css}</style></head>
<body>
<h1>{html.escape(self.app_name())}</h1>
<div class="muted">Reporte técnico generado: {html.escape(now.strftime('%d/%m/%Y %H:%M:%S'))}</div>
<div class="card"><h2>Resumen del sistema</h2><table>{table_rows(rows)}</table></div>
<div class="card"><h2>Discos</h2><table><tr><th>Unidad</th><th>FS</th><th>Tipo</th><th>Uso</th><th>Libre</th><th>Total</th></tr>{''.join(disks_html)}</table></div>
<div class="card"><h2>Top procesos por RAM</h2><table><tr><th>PID</th><th>Proceso</th><th>RAM</th><th>%</th></tr>{''.join(proc_html)}</table></div>
<div class="card"><h2>Diagnóstico de red</h2><pre>{html.escape(network_report)}</pre></div>
<div class="card"><h2>Issues del último escaneo</h2><table><tr><th>Categoría</th><th>Issues</th><th>Errores</th></tr>{''.join(issue_rows)}</table></div>
<div class="card"><h2>Actividad reciente</h2><pre>{html.escape(log_excerpt or 'Sin actividad registrada hoy.')}</pre></div>
</body></html>"""
        path.write_text(content, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def show_settings(self) -> None:
        page = self._page("settings", self.tr("settings_title"), self.tr("settings_subtitle"))

        panel = ctk.CTkFrame(page, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        panel.pack(fill="x")
        ctk.CTkLabel(panel, text=self.tr("settings_preferences"), font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 10))

        name_frame = ctk.CTkFrame(panel, fg_color="transparent")
        name_frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(name_frame, text="Nombre de la app:", width=180, anchor="w").pack(side="left")
        self.settings_app_name_var = tk.StringVar(value=self.app_name())
        ctk.CTkEntry(name_frame, textvariable=self.settings_app_name_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._button(name_frame, "Guardar", self._save_app_name, "accent", width=100).pack(side="left")

        view_mode_frame = ctk.CTkFrame(panel, fg_color="transparent")
        view_mode_frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(view_mode_frame, text="Vista de la app:", width=180, anchor="w").pack(side="left")
        view_mode_values = ["Básica (limpieza + reportes)", "Completa (todas las herramientas)"]
        self._view_mode_display_to_value = {
            view_mode_values[0]: True,
            view_mode_values[1]: False,
        }
        current_view_display = view_mode_values[0] if self.is_basic_mode() else view_mode_values[1]
        self.settings_view_mode_var = tk.StringVar(value=current_view_display)
        ctk.CTkOptionMenu(
            view_mode_frame, values=view_mode_values, variable=self.settings_view_mode_var,
            command=self._change_view_mode_display,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            view_mode_frame,
            text="Básica oculta Red/Discos/Memoria/Command Center/IA del menú.",
            text_color=COLORS["muted"],
        ).pack(side="left", padx=(8, 0))

        language_frame = ctk.CTkFrame(panel, fg_color="transparent")
        language_frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(language_frame, text=self.tr("language"), width=180, anchor="w").pack(side="left")
        lang_values = ["Auto (OS)", "Español", "English", "Deutsch"]
        lang_map = {"Auto (OS)": "auto", "Español": "es", "English": "en", "Deutsch": "de"}
        rev_lang_map = {v: k for k, v in lang_map.items()}
        current_language_setting = "auto" if bool(self.config_data.get("language_follow_os", False)) else str(self.config_data.get("language", "auto"))
        self.settings_language_var = tk.StringVar(value=rev_lang_map.get(current_language_setting, "Auto (OS)"))
        ctk.CTkOptionMenu(language_frame, values=lang_values, variable=self.settings_language_var, command=lambda v: self._change_language(lang_map.get(v, "auto"))).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(language_frame, text=f"Detectado: {resolve_language(self.config_data).upper()}", text_color=COLORS["muted"]).pack(side="left", padx=(8, 0))

        mode_frame = ctk.CTkFrame(panel, fg_color="transparent")
        mode_frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(mode_frame, text=self.tr("safety_mode"), width=180, anchor="w").pack(side="left")
        mode_values = [self.tr("mode_safe"), self.tr("mode_advanced")]
        self._mode_display_to_value = {self.tr("mode_safe"): "safe", self.tr("mode_advanced"): "advanced"}
        current_mode = "advanced" if self.is_advanced_mode() else "safe"
        current_display = self.tr("mode_advanced") if current_mode == "advanced" else self.tr("mode_safe")
        self.settings_mode_var = tk.StringVar(value=current_display)
        ctk.CTkOptionMenu(mode_frame, values=mode_values, variable=self.settings_mode_var, command=self._change_safety_mode_display).pack(side="left", padx=(0, 8))

        path_frame = ctk.CTkFrame(panel, fg_color="transparent")
        path_frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(path_frame, text="Ruta de datos / backups:", width=180, anchor="w").pack(side="left")
        self.settings_path_var = tk.StringVar(value=self.config_data.get("install_path", str(Path.home() / "StrallozData")))
        ctk.CTkEntry(path_frame, textvariable=self.settings_path_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._button(path_frame, "Buscar", self._browse_data_path, "accent", width=90).pack(side="left")

        theme_frame = ctk.CTkFrame(panel, fg_color="transparent")
        theme_frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(theme_frame, text="Tema:", width=180, anchor="w").pack(side="left")
        self.theme_display_map = {"Seguir Windows": "system", "Oscuro": "dark", "Claro": "light"}
        current_theme = self.config_data.get("theme", "dark")
        current_display = next((k for k, v in self.theme_display_map.items() if v == current_theme), "Oscuro")
        self.settings_theme_var = tk.StringVar(value=current_display)
        ctk.CTkOptionMenu(theme_frame, values=list(self.theme_display_map.keys()), variable=self.settings_theme_var, command=self._change_theme_display).pack(
            side="left", padx=(0, 8)
        )

        behavior_frame = ctk.CTkFrame(panel, fg_color="transparent")
        behavior_frame.pack(fill="x", padx=16, pady=8)
        self.backup_enabled_var = ctk.BooleanVar(value=bool(self.config_data.get("backup_enabled", True)))
        ctk.CTkCheckBox(
            behavior_frame,
            text="Crear backup automático antes de reparar",
            variable=self.backup_enabled_var,
            command=lambda: self._update_setting("backup_enabled", self.backup_enabled_var.get()),
        ).pack(anchor="w", pady=4)

        self.close_to_tray_var = ctk.BooleanVar(value=bool(self.config_data.get("close_to_tray", False)))
        tray_text = "Cerrar a bandeja del sistema" if HAS_TRAY else "Cerrar a bandeja del sistema (requiere pystray)"
        ctk.CTkCheckBox(
            behavior_frame,
            text=tray_text,
            variable=self.close_to_tray_var,
            state="normal" if HAS_TRAY else "disabled",
            command=self._toggle_close_to_tray,
        ).pack(anchor="w", pady=4)

        age_frame = ctk.CTkFrame(panel, fg_color="transparent")
        age_frame.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(age_frame, text="Antigüedad mínima temp:", width=180, anchor="w").pack(side="left")
        self.temp_age_var = tk.StringVar(value=str(self.config_data.get("temp_file_min_age_hours", 24)))
        ctk.CTkEntry(age_frame, textvariable=self.temp_age_var, width=90).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(age_frame, text="horas", text_color=COLORS["muted"]).pack(side="left")
        self._button(age_frame, "Guardar", self._save_temp_age, "accent", width=100).pack(side="left", padx=12)

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(12, 16))
        self._button(buttons, "📁 Abrir carpeta de datos", self._open_data_folder, "surface3", width=190).pack(side="left", padx=(0, 8))
        self._button(buttons, "↩ Reset defaults", self._reset_settings, "danger", width=150).pack(side="left", padx=8)

        # --- Sección Asistente IA en Settings ---
        # Oculta en modo Basico: consistente con que "ai" tampoco aparece en
        # el menu lateral ni en los accesos rapidos del dashboard.
        if not self.is_basic_mode():
            ai_panel = ctk.CTkFrame(page, fg_color=COLORS["surface"], corner_radius=14,
                                    border_width=1, border_color=COLORS["border"])
            ai_panel.pack(fill="x", pady=(12, 0))
            ctk.CTkLabel(ai_panel, text="🤖 Asistente IA",
                         font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
            active_provider = self.ai_assistant.active_provider_name()
            provider = self.ai_assistant.get_provider(active_provider)
            summary = (
                f"Proveedor activo: {active_provider}\n"
                f"Tipo: {provider.get('kind', '-')} · Modelo: {provider.get('model', '-')}\n"
                "Para cambiar API key, endpoint, modelo o agregar DeepSeek/OpenAI/Ollama/custom, abre el Asistente IA."
            )
            ctk.CTkLabel(ai_panel, text=summary, text_color=COLORS["muted"], justify="left").pack(anchor="w", padx=16, pady=(0, 10))
            self._button(ai_panel, "Gestionar proveedores IA", self.show_ai_assistant, "accent", width=220).pack(anchor="w", padx=16, pady=(0, 16))

        notes = ctk.CTkFrame(page, fg_color=COLORS["surface"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        notes.pack(fill="x", pady=16)
        deps = ["customtkinter", "psutil", "pillow"]
        optional = []
        if not HAS_TRAY:
            optional.append("pystray")
        if IS_WINDOWS and not HAS_WINDOWS_AUTOMATION:
            optional.extend(["winshell", "pywin32"])
        msg = "Dependencias base: " + ", ".join(deps)
        if optional:
            msg += "\nOpcionales faltantes para todas las funciones: " + ", ".join(optional)
        ctk.CTkLabel(notes, text=msg, text_color=COLORS["muted"], justify="left").pack(anchor="w", padx=16, pady=14)

    def _change_language(self, lang: str) -> None:
        if lang == "auto":
            self.config_data["language"] = "auto"
            self.config_data["language_follow_os"] = True
            ConfigManager.save_config(self.config_data)
        else:
            if lang not in I18N:
                lang = "en"
            self.config_data["language"] = lang
            self.config_data["language_follow_os"] = False
            ConfigManager.save_config(self.config_data)
        self.update_status(self.tr("status_ready"))
        self._rebuild_shell_keep_page()

    def _change_safety_mode_display(self, display_value: str) -> None:
        mode = getattr(self, "_mode_display_to_value", {}).get(display_value, "safe")
        self._update_setting("safety_mode", mode)
        self.update_status(f"Modo: {display_value}")

    def _change_view_mode_display(self, display_value: str) -> None:
        basic = getattr(self, "_view_mode_display_to_value", {}).get(display_value, False)
        self._update_setting("basic_mode", basic)
        self.update_status(f"Vista: {display_value}")
        self._rebuild_shell_keep_page()

    def _browse_data_path(self) -> None:
        path = filedialog.askdirectory(initialdir=self.settings_path_var.get() or str(Path.home()))
        if not path:
            return
        self.settings_path_var.set(path)
        self._update_setting("install_path", path)
        self.backup_path = Path(path) / "backups"
        self.cleaner.set_backup_path(self.backup_path)
        self.update_status("Ruta de datos actualizada")

    def _change_theme_display(self, display_value: str) -> None:
        theme = self.theme_display_map.get(display_value, "dark")
        self._update_setting("theme", theme)
        SystemTheme.apply_theme(theme)
        self.last_system_theme = SystemTheme.get_windows_theme() if theme == "system" else theme
        self.update_status(f"Tema cambiado a: {display_value}")

    def _toggle_close_to_tray(self) -> None:
        value = bool(self.close_to_tray_var.get())
        self._update_setting("close_to_tray", value)
        if value and not self.tray_icon:
            self._setup_tray()
        elif not value and self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None

    def _save_temp_age(self) -> None:
        try:
            hours = int(self.temp_age_var.get())
            if hours < 0:
                raise ValueError
        except Exception:
            messagebox.showerror("Valor inválido", "Ingresa un número de horas válido, por ejemplo 24.")
            return
        self._update_setting("temp_file_min_age_hours", hours)
        self.cleaner.temp_file_min_age_hours = hours
        self.update_status(f"Antigüedad mínima de temporales: {hours} horas")

    def _save_app_name(self) -> None:
        new_name = self.settings_app_name_var.get().strip()
        if not new_name:
            messagebox.showerror("Nombre inválido", "El nombre de la app no puede quedar vacío.")
            return
        self._update_setting("app_name", new_name)
        self.title(f"{self.app_name()} - {APP_VERSION}")
        # Mejor esfuerzo: actualizar tooltip del icono de bandeja si ya existe.
        if self.tray_icon is not None:
            try:
                self.tray_icon.title = self.app_name()
            except Exception:
                pass
        self._rebuild_shell_keep_page()
        self.update_status(f"Nombre de la app actualizado a: {new_name}")

    def _update_setting(self, key: str, value: Any) -> None:
        self.config_data[key] = value
        ConfigManager.save_config(self.config_data)

    def _open_data_folder(self) -> None:
        path = Path(self.config_data.get("install_path", str(Path.home() / "StrallozData")))
        path.mkdir(parents=True, exist_ok=True)
        try:
            if IS_WINDOWS:
                os.startfile(path)  # type: ignore[attr-defined]
            elif IS_MAC:
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _reset_settings(self) -> None:
        if not messagebox.askyesno("Reset", "¿Restaurar la configuración por defecto?"):
            return
        self.config_data = ConfigManager.default_config()
        self.config_data["first_run"] = False
        ConfigManager.save_config(self.config_data)
        SystemTheme.apply_theme(self.config_data["theme"])
        self.backup_path = Path(self.config_data["install_path"]) / "backups"
        self.cleaner.set_backup_path(self.backup_path)
        self.update_status("Configuración restaurada")
        self.show_settings()

    # ------------------------------------------------------------------
    # Welcome wizard
    # ------------------------------------------------------------------
    def show_welcome_wizard(self) -> None:
        wizard = ctk.CTkToplevel(self)
        wizard.title(f"Bienvenido a {self.app_name()}")
        wizard.geometry("560x390")
        wizard.transient(self)
        wizard.grab_set()
        wizard.configure(fg_color=COLORS["bg"])

        ctk.CTkLabel(wizard, text=f"Bienvenido a {self.app_name()}", font=ctk.CTkFont(size=26, weight="bold")).pack(pady=(28, 6))
        ctk.CTkLabel(
            wizard,
            text="Esta edición fusiona optimización, comandos técnicos y control de energía en una sola app.",
            text_color=COLORS["muted"],
            wraplength=470,
            justify="center",
        ).pack(pady=(0, 18))

        frame = ctk.CTkFrame(wizard, fg_color=COLORS["surface"], corner_radius=14)
        frame.pack(fill="x", padx=28, pady=10)
        ctk.CTkLabel(frame, text="Carpeta para backups y configuración", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(16, 6))
        path_var = tk.StringVar(value=self.config_data.get("install_path", str(Path.home() / "StrallozData")))
        ctk.CTkEntry(frame, textvariable=path_var).pack(fill="x", padx=16, pady=4)

        def browse() -> None:
            selected = filedialog.askdirectory(initialdir=path_var.get() or str(Path.home()))
            if selected:
                path_var.set(selected)

        ctk.CTkButton(frame, text="Buscar carpeta", command=browse).pack(anchor="w", padx=16, pady=(6, 16))

        def complete() -> None:
            self.config_data["install_path"] = path_var.get()
            self.config_data["first_run"] = False
            ConfigManager.save_config(self.config_data)
            self.backup_path = Path(path_var.get()) / "backups"
            self.cleaner.set_backup_path(self.backup_path)
            wizard.destroy()
            self.update_status("Configuración inicial completada")

        ctk.CTkButton(wizard, text="Comenzar", command=complete, fg_color=COLORS["accent2"], width=160).pack(pady=20)


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    single_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        single_instance_socket.bind(("127.0.0.1", 57321))
    except OSError:
        root = tk.Tk()
        root.withdraw()
        app_name = str(ConfigManager.load_config().get("app_name") or DEFAULT_APP_NAME).strip() or DEFAULT_APP_NAME
        messagebox.showwarning("Ya está abierto", f"{app_name} ya se está ejecutando.")
        root.destroy()
        return

    try:
        app = StrallozControlCenter()
        app.mainloop()
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Error",
            f"Ocurrió un error: {exc}\n\nAlgunas operaciones requieren permisos de administrador.",
        )
        root.destroy()
    finally:
        try:
            single_instance_socket.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
