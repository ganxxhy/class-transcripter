; Instalador de Estudio (antes "Agente de clases"), con Inno Setup 6
; Lo compila GitHub Actions: iscc /DVersion=1.0.0 packaging\instalador.iss
; Espera el programa en dist\AgenteClases\ y las imágenes en packaging\build\

#ifndef Version
  #define Version "0.0.0"
#endif
#define Nombre "Estudio"
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
DisableReadyPage=no
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nombre}
OutputDir=..\dist
OutputBaseFilename=Estudio-{#Version}-instalador
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
CloseApplications=no
RestartApplications=no

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
es.WelcomeLabel1=Te damos la bienvenida al instalador
es.WelcomeLabel2=Estudio graba tus clases, las transcribe en tu ordenador y te prepara un resumen de cada una, con exámenes y entregas aparte.%n%n✓  No necesitas instalar nada más%n✓  El audio nunca sale de tu ordenador%n✓  Descarga el modelo de voz (de 0,5 a 1,6 GB según tu ordenador)%n%nPulsa Siguiente para continuar.
es.FinishedHeadingLabel=Todo listo
es.FinishedLabelNoIcons=Estudio está instalado. La primera vez que lo abras te ayudará a poner tus asignaturas y tu horario en un par de minutos.%n%nSi tienes la app de Claude abierta, ciérrala y vuelve a abrirla para que vea tus clases.
es.FinishedLabel=Estudio está instalado. La primera vez que lo abras te ayudará a poner tus asignaturas y tu horario en un par de minutos.%n%nSi tienes la app de Claude abierta, ciérrala y vuelve a abrirla para que vea tus clases.
es.ClickFinish=
es.WizardInstalling=Instalando
es.InstallingLabel=Esto tarda un par de minutos.

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"
Name: "inicio"; Description: "Iniciar con Windows (para que grabe solo según tu horario)"

[Files]
Source: "..\dist\AgenteClases\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

Source: "{#Img}hub.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\\Estudio Hub"; Filename: "{app}\\{#Exe}"; Parameters: "--hub"; IconFilename: "{app}\\hub.ico"
Name: "{userdesktop}\\Estudio Hub"; Filename: "{app}\\{#Exe}"; Parameters: "--hub"; IconFilename: "{app}\\hub.ico"; Tasks: escritorio
Name: "{userprograms}\{#Nombre}"; Filename: "{app}\{#Exe}"
Name: "{userdesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AgenteClases"; ValueData: """{app}\{#Exe}"" --inicio"; Flags: uninsdeletevalue; Tasks: inicio

[Run]
Filename: "{app}\{#Exe}"; Parameters: "--registrar-mcp"; StatusMsg: "Conectando con la app de Claude…"; Flags: runhidden waituntilterminated
Filename: "{app}\{#Exe}"; Parameters: "--descargar-modelo"; StatusMsg: "Descargando el modelo de voz (hasta 1,6 GB la primera vez, puede tardar unos minutos)…"; Flags: runhidden waituntilterminated; BeforeInstall: BarraEnMovimiento
Filename: "{app}\{#Exe}"; Description: "Abrir Estudio ahora"; Flags: postinstall nowait skipifsilent
; Al actualizar desde la propia app (instalación silenciosa), vuelve a abrirla sola
Filename: "{app}\{#Exe}"; Flags: nowait; Check: WizardSilent

[UninstallRun]
Filename: "{app}\{#Exe}"; Parameters: "--quitar-mcp"; Flags: runhidden waituntilterminated; RunOnceId: "QuitarMCP"

[Code]
// Mientras corre el paso largo (descarga del modelo) la barra se mueve sola
procedure BarraEnMovimiento();
begin
  WizardForm.ProgressGauge.Style := npbstMarquee;
end;

// ---------- Actualizar una instalación que ya existe ----------
// Si el programa ya está instalado, el asistente se salta la bienvenida, la carpeta y las
// opciones (usa las de la vez anterior) y solo pregunta "¿Actualizar?". Las clases, el horario
// y los ajustes están en Documentos\AgenteClases y no se tocan.
const
  CLAVE_DESINSTALAR = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E1C3A52-7B9D-4F0E-9C1A-AC1A5E5C1A55}_is1';

var
  VersionInstalada: String;

function EsActualizacion(): Boolean;
begin
  Result := RegKeyExists(HKCU, CLAVE_DESINSTALAR);
end;

function InitializeSetup(): Boolean;
begin
  VersionInstalada := '';
  if EsActualizacion() then
    RegQueryStringValue(HKCU, CLAVE_DESINSTALAR, 'DisplayVersion', VersionInstalada);
  Result := True;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if EsActualizacion() then
    Result := (PageID = wpWelcome) or (PageID = wpSelectDir) or (PageID = wpSelectTasks)
  else
    Result := (PageID = wpReady);
end;

procedure CurPageChanged(CurPageID: Integer);
var
  Desde: String;
begin
  if (CurPageID = wpReady) and EsActualizacion() then
  begin
    Desde := '';
    if VersionInstalada <> '' then
      Desde := ' (tienes la ' + VersionInstalada + ')';
    WizardForm.PageNameLabel.Caption := 'Actualizar Estudio';
    WizardForm.PageDescriptionLabel.Caption := 'Ya lo tienes instalado' + Desde + '.';
    WizardForm.ReadyLabel.Caption := 'Se instalará la versión {#Version} encima de la que tienes.' + #13#10 + #13#10 +
      'Tus clases, tu horario y tus ajustes se quedan como están.' + #13#10 +
      'Si Estudio está abierto, se cerrará para actualizarlo.';
    WizardForm.ReadyMemo.Visible := False;
    WizardForm.NextButton.Caption := 'Actualizar';
  end;
end;

// Antes de copiar archivos, cierra el agente y su servidor del panel si están abiertos
// (el agente se esconde junto al reloj en vez de cerrarse, así que hay que pararlo a la fuerza;
// lo ya transcrito está guardado).
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM AgenteClases.exe', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM agente-mcp.exe', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;
