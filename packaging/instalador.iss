; Instalador de Agente de clases (Inno Setup 6)
; Lo compila GitHub Actions: iscc /DVersion=1.0.0 packaging\instalador.iss
; Espera el programa en dist\AgenteClases\ y las imágenes en packaging\build\

#ifndef Version
  #define Version "0.0.0"
#endif
#define Nombre "Agente de clases"
#define Exe "AgenteClases.exe"
#define Img "build\"

[Setup]
AppId={{6E1C3A52-7B9D-4F0E-9C1A-AC1A5E5C1A55}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher=ganxxhy
AppPublisherURL=https://github.com/ganxxhy/class-transcripter
AppSupportURL=https://github.com/ganxxhy/class-transcripter/issues
; Instalación para el usuario: no pide permisos de administrador
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\AgenteClases
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=yes
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nombre}
OutputDir=..\dist
OutputBaseFilename=AgenteClases-{#Version}-instalador
SetupIconFile={#Img}icono.ico
WizardStyle=modern
WizardSizePercent=110
WizardImageFile={#Img}asistente-100.bmp,{#Img}asistente-125.bmp,{#Img}asistente-150.bmp,{#Img}asistente-175.bmp,{#Img}asistente-200.bmp,{#Img}asistente-225.bmp,{#Img}asistente-250.bmp
WizardSmallImageFile={#Img}logo-100.bmp,{#Img}logo-125.bmp,{#Img}logo-150.bmp,{#Img}logo-175.bmp,{#Img}logo-200.bmp,{#Img}logo-225.bmp,{#Img}logo-250.bmp
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
es.WelcomeLabel1=Te damos la bienvenida al instalador
es.WelcomeLabel2=Agente de clases graba tus clases, las transcribe en tu ordenador y te prepara un resumen de cada una, con exámenes y entregas aparte.%n%n✓  No necesitas instalar nada más%n✓  El audio nunca sale de tu ordenador%n✓  Ocupa unos 600 MB con el modelo de voz%n%nPulsa Siguiente para continuar.
es.FinishedHeadingLabel=Todo listo
es.FinishedLabelNoIcons=Agente de clases está instalado. La primera vez que lo abras te ayudará a poner tus asignaturas y tu horario en un par de minutos.%n%nSi tienes la app de Claude abierta, ciérrala y vuelve a abrirla para que vea tus clases.
es.FinishedLabel=Agente de clases está instalado. La primera vez que lo abras te ayudará a poner tus asignaturas y tu horario en un par de minutos.%n%nSi tienes la app de Claude abierta, ciérrala y vuelve a abrirla para que vea tus clases.
es.ClickFinish=
es.WizardInstalling=Instalando
es.InstallingLabel=Esto tarda un par de minutos.

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"
Name: "inicio"; Description: "Iniciar con Windows (para que grabe solo según tu horario)"

[Files]
Source: "..\dist\AgenteClases\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#Nombre}"; Filename: "{app}\{#Exe}"
Name: "{userdesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AgenteClases"; ValueData: """{app}\{#Exe}"" --inicio"; Flags: uninsdeletevalue; Tasks: inicio

[Run]
Filename: "{app}\{#Exe}"; Parameters: "--registrar-mcp"; StatusMsg: "Conectando con la app de Claude…"; Flags: runhidden waituntilterminated
Filename: "{app}\{#Exe}"; Parameters: "--descargar-modelo"; StatusMsg: "Descargando el modelo de voz (unos 500 MB, puede tardar unos minutos)…"; Flags: runhidden waituntilterminated; BeforeInstall: BarraEnMovimiento
Filename: "{app}\{#Exe}"; Description: "Abrir Agente de clases ahora"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\{#Exe}"; Parameters: "--quitar-mcp"; Flags: runhidden waituntilterminated; RunOnceId: "QuitarMCP"

[Code]
// Mientras corre el paso largo (descarga del modelo) la barra se mueve sola
procedure BarraEnMovimiento();
begin
  WizardForm.ProgressGauge.Style := npbstMarquee;
end;
