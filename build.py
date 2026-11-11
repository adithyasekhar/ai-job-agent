"""Build CareerPilot AI.exe and install it for the current user.

Run with the build environment's Python:
  %LOCALAPPDATA%\\AIJobAgent-build\\venv\\Scripts\\python.exe build.py [--zip] [--no-install]
  --zip         also write CareerPilot-AI-v<version>-windows.zip for a GitHub release
  --no-install  build only; don't replace the installed copy
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(os.environ["LOCALAPPDATA"], "AIJobAgent-build")
NAME = "CareerPilot AI"
INSTALL = os.path.join(os.environ["LOCALAPPDATA"], "Programs", NAME)
OLD_INSTALL = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "AI Job Agent")  # v1.x
ICON = os.path.join(HERE, "jobagent", "assets", "icon.ico")


def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True)


def shortcut(path, target):
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{path}');"
          f"$s.TargetPath='{target}';$s.WorkingDirectory='{os.path.dirname(target)}';"
          f"$s.IconLocation='{target},0';$s.Description='{NAME}';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def main():
    sep = ";"
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
         "--name", NAME, "--icon", ICON,
         "--distpath", os.path.join(BUILD, "dist"), "--workpath", os.path.join(BUILD, "work"),
         "--specpath", BUILD,
         "--add-data", f"{os.path.join(HERE, 'jobagent', 'ui')}{sep}ui",
         "--add-data", f"{os.path.join(HERE, 'jobagent', 'assets')}{sep}assets",
         "--hidden-import", "keyring.backends.Windows",
         "--hidden-import", "pystray._win32",
         "--hidden-import", "qrcode.image.pil",
         "--collect-submodules", "webview",
         os.path.join(HERE, "main.py")])

    if "--zip" in sys.argv:
        sys.path.insert(0, HERE)
        from jobagent.settings import APP_VERSION
        base = os.path.join(BUILD, f"CareerPilot-AI-v{APP_VERSION}-windows")
        shutil.make_archive(base, "zip", os.path.join(BUILD, "dist"), NAME)
        print("Release zip:", base + ".zip")
    if "--no-install" in sys.argv:
        return

    # Stop running copies (new and v1.x names) before replacing files.
    for exe_name in (f"{NAME}.exe", "AI Job Agent.exe"):
        subprocess.run(["taskkill", "/IM", exe_name, "/F"], capture_output=True)
    for folder in (INSTALL, OLD_INSTALL):
        if os.path.isdir(folder):
            shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(os.path.join(BUILD, "dist", NAME), INSTALL)
    exe = os.path.join(INSTALL, f"{NAME}.exe")

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    od = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    if os.path.isdir(od):
        desktop = od
    start_menu = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
    startup = os.path.join(start_menu, "Startup")
    for folder in (desktop, start_menu, startup):  # remove v1.x shortcuts
        old = os.path.join(folder, "AI Job Agent.lnk")
        if os.path.exists(old):
            os.remove(old)
    shortcut(os.path.join(desktop, f"{NAME}.lnk"), exe)
    shortcut(os.path.join(start_menu, f"{NAME}.lnk"), exe)
    print("Installed:", exe)


if __name__ == "__main__":
    main()
