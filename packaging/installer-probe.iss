; Isolated installer fixture for the packaged updater smoke test.
[Setup]
AppName=Estudio Installer Probe
AppVersion=1.0
AppId=EstudioInstallerProbe
DefaultDirName={#ProbeDir}\installed
OutputBaseFilename=installer-probe
PrivilegesRequired=lowest
Uninstallable=no
CreateUninstallRegKey=no
DisableDirPage=yes
DisableProgramGroupPage=yes
[Files]
Source: "{#ProbeDir}\probe.txt"; DestDir: "{app}"
