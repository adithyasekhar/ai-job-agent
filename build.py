"""Build AI Job Agent.exe and install it for the current user.

Run with the build environment's Python:
  %LOCALAPPDATA%\\AIJobAgent-build\\venv\\Scripts\\python.exe build.py
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(os.environ["LOCALAPPDATA"], "AIJobAgent-build")
INSTALL = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "AI Job Agent")
ICON = os.path.join(HERE, "jobagent", "assets", "icon.ico")


def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True)


def shortcut(path, target):
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{path}');"
          f"$s.TargetPath='{target}';$s.WorkingDirectory='{os.path.dirname(target)}';"
          f"$s.IconLocation='{target},0';$s.Description='AI Job Agent';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def main():
    sep = ";"
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
         "--name", "AI Job Agent", "--icon", ICON,
         "--distpath", os.path.join(BUILD, "dist"), "--workpath", os.path.join(BUILD, "work"),
         "--specpath", BUILD,
         "--add-data", f"{os.path.join(HERE, 'jobagent', 'ui')}{sep}ui",
         "--add-data", f"{os.path.join(HERE, 'jobagent', 'assets')}{sep}assets",
         "--hidden-import", "keyring.backends.Windows",
         "--hidden-import", "pystray._win32",
         "--collect-submodules", "webview",
         os.path.join(HERE, "main.py")])

    # Stop a running copy before replacing files.
    subprocess.run(["taskkill", "/IM", "AI Job Agent.exe", "/F"], capture_output=True)
    if os.path.isdir(INSTALL):
        shutil.rmtree(INSTALL, ignore_errors=True)
    shutil.copytree(os.path.join(BUILD, "dist", "AI Job Agent"), INSTALL)
    exe = os.path.join(INSTALL, "AI Job Agent.exe")

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    od = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    if os.path.isdir(od):
        desktop = od
    start_menu = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
    shortcut(os.path.join(desktop, "AI Job Agent.lnk"), exe)
    shortcut(os.path.join(start_menu, "AI Job Agent.lnk"), exe)
    print("Installed:", exe)


if __name__ == "__main__":
    main()
