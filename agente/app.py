"""Estudio: ventana pequeña para iniciar/parar la escucha y abrir el panel "Mis clases".

Opciones (las usa el instalador):
  --asistente       abre el asistente de configuración
  --inicio          arranque con la sesión: escucha en automático y se queda junto al reloj
  --mcp             arranca el servidor MCP por stdio (lo usa la app de Claude con el AppImage)
  --integrar        (Linux) crea el lanzador del menú y el arranque con la sesión
  --quitar-integracion  (Linux) los borra
  --registrar-mcp   conecta el agente con la app de escritorio de Claude
  --quitar-mcp      lo desconecta (al desinstalar)
  --descargar-modelo  descarga el modelo de voz que toca para este ordenador
  --al-arrancar     novedades tras actualizar y aviso si hay versión nueva (lo lanza la app)
  --buscar-actualizacion [--forzar]  aviso de versión nueva (--forzar: aunque se saltara)
"""
import os
import subprocess
import sys

# En el .exe sin consola no hay stdout/stderr: cualquier print() fallaría
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nucleo import almacen, horario, resumen  # noqa: E402
from nucleo.config import CONGELADA, RUTA_DATOS, cargar, existe, guardar, nombre_asignatura, resumen_en_pc  # noqa: E402
from nucleo.motor import microfonos  # noqa: E402
from bootstrap import build_motor, build_repository  # noqa: E402
import tema  # noqa: E402
from version import VERSION  # noqa: E402

if sys.platform.startswith("linux") and CONGELADA:
    # PortAudio travels inside the bundle and ctypes cannot find it by name
    _portaudio = os.path.join(getattr(sys, "_MEIPASS", ""), "libportaudio.so.2")
    if os.path.exists(_portaudio):
        import ctypes.util
        _find_library = ctypes.util.find_library
        ctypes.util.find_library = lambda n: _portaudio if n == "portaudio" else _find_library(n)
    # The bundle now carries PyGObject (for the web windows), which makes pystray try AppIndicator and fail:
    # keep the X11 backend it always used here
    os.environ.setdefault("PYSTRAY_BACKEND", "xorg")

os.makedirs(RUTA_DATOS, exist_ok=True)
RUTA_LOG = os.path.join(RUTA_DATOS, "agente.log")


def _comando(*args):
    return ([sys.executable] if CONGELADA else [sys.executable, os.path.abspath(__file__)]) + list(args)


def lanzar_asistente():
    """Abre el asistente en otro proceso (pywebview y Tk no conviven bien) y espera."""
    cmd = [sys.executable] if CONGELADA else [sys.executable, os.path.abspath(__file__)]
    try:
        subprocess.run(cmd + ["--asistente"], check=False)
    except Exception:
        pass


class App:
    def __init__(self, root, inicio=False):
        self.root = root
        self.cfg = cargar()
        self.logs = []
        self.repository = build_repository()
        self.motor = build_motor(log=self.log, repository=self.repository)
        self.url_hub = self.cfg["ajustes"].get("url_hub") or "https://claude.ai/code/artifacts"
        self.icono = None
        self._construir()
        self._recuperar()
        self.motor.precargar()
        self.motor.guardar_estado()
        self._tick()
        if inicio and self.cfg["horario"]:
            self.root.after(500, self._inicio_automatico)
        # Novedades (si se acaba de actualizar) y aviso de versión nueva, al arrancar y cada día
        self.root.after(4000, self._revisar_actualizaciones)

    def _revisar_actualizaciones(self):
        if CONGELADA:
            try:
                subprocess.Popen(_comando("--al-arrancar"))
            except Exception as e:
                self.log(f"No he podido buscar actualizaciones: {e}")
        self.root.after(24 * 3600 * 1000, self._revisar_actualizaciones)

    def buscar_actualizacion(self):
        """Botón de Ajustes: busca ya, y si no hay nada lo dice."""
        import actualizacion

        def hilo():
            info = actualizacion.buscar(forzar=True)
            actualizacion.revisar_panel(info)
            def responder():
                if info and actualizacion.es_mas_nueva(info["version"]):
                    subprocess.Popen(_comando("--buscar-actualizacion", "--forzar"))
                elif info is None:
                    messagebox.showinfo("Actualizaciones", actualizacion.ultimo_error or "No he podido comprobar las actualizaciones.")
                else:
                    messagebox.showinfo("Actualizaciones", f"Ya tienes la última versión ({VERSION}).")
            self.root.after(0, responder)
        threading.Thread(target=hilo, daemon=True).start()

    def _inicio_automatico(self):
        try:
            self.motor.iniciar("auto", None)
        except Exception as e:
            self.log(f"No he podido empezar en automático: {e}")
            return
        self.btn_ini.configure(state="disabled")
        self.btn_parar.configure(state="normal")
        self.btn_cambiar.configure(state="normal")
        if not self._a_bandeja():
            self.root.iconify()

    # ---------- utilidades ----------
    def log(self, msg):
        linea = f"{datetime.now():%H:%M:%S}  {msg}"
        self.logs = (self.logs + [linea])[-200:]
        try:
            with open(RUTA_LOG, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d} {linea}\n")
        except Exception:
            pass

    def _recuperar(self):
        """Cierra clases que quedaron abiertas si el agente se cortó y resume lo pendiente."""
        for cid in self.repository.clases_abiertas_huerfanas():
            self.repository.cerrar(cid)
            self.log(f"Recuperada clase sin cerrar: {cid}")
        if resumen_en_pc(self.cfg):
            for cid in resumen.pendientes(repositorio=self.repository):
                resumen.en_segundo_plano(cid, self.log, repositorio=self.repository)

    # ---------- interfaz ----------
    def _construir(self):
        r = self.root
        r.title("Estudio")
        r.geometry("540x620")
        r.minsize(460, 520)
        self.f = tema.aplicar(r)
        try:
            from PIL import ImageTk
            self._ico = ImageTk.PhotoImage(tema.icono(64))
            r.iconphoto(True, self._ico)
        except Exception:
            pass

        self.cab = tema.Cabecera(r, self.f)
        self.cab.pack(fill="x")
        f = ttk.Frame(r, padding=(14, 12, 14, 10))
        f.pack(fill="both", expand=True)

        c = tema.tarjeta(f, fill="x")
        fila = ttk.Frame(c, style="Card.TFrame")
        fila.pack(fill="x")
        self.btn_ini = ttk.Button(fila, text="Iniciar", style="Pri.TButton", command=self.iniciar)
        self.btn_ini.pack(side="left")
        self.btn_parar = ttk.Button(fila, text="Parar", command=self.parar, state="disabled")
        self.btn_parar.pack(side="left", padx=6)
        self.btn_cambiar = ttk.Button(fila, text="Cambiar asignatura", command=self.cambiar, state="disabled")
        self.btn_cambiar.pack(side="left")
        ttk.Button(fila, text="Abrir Mis clases", command=lambda: webbrowser.open(self.url_hub)).pack(side="right")

        c = tema.tarjeta(f, fill="x", pady=(10, 0))
        ttk.Label(c, text="Micrófono", style="Seccion.TLabel").pack(anchor="w")
        mic = ttk.Frame(c, style="Card.TFrame")
        mic.pack(fill="x", pady=(6, 0))
        self.mics = []
        self.var_mic = tk.StringVar()
        self.cmb_mic = ttk.Combobox(mic, textvariable=self.var_mic, state="readonly")
        self.cmb_mic.pack(side="left", fill="x", expand=True)
        self.cmb_mic.bind("<<ComboboxSelected>>", self._mic_cambiado)
        ttk.Button(mic, text="Buscar", command=lambda: self._cargar_mics(True)).pack(side="left", padx=(8, 0))
        self._cargar_mics(False)
        self.barra = ttk.Progressbar(c, maximum=100, style="Nivel.Horizontal.TProgressbar")
        self.barra.pack(fill="x", pady=(10, 2))

        c = tema.tarjeta(f, fill="both", expand=True, pady=(10, 0))
        ttk.Label(c, text="Lo último que he oído", style="Seccion.TLabel").pack(anchor="w")
        self.txt = tk.Text(c, height=8, wrap="word", relief="flat", font=self.f.texto, background=tema.PAPER,
                           foreground=tema.INK, padx=10, pady=8, highlightthickness=0, bd=0,
                           selectbackground="#FFD2A8", selectforeground=tema.INK)
        self.txt.pack(fill="both", expand=True, pady=(6, 0))
        self.txt.configure(state="disabled")

        pie = ttk.Frame(f)
        pie.pack(fill="x", pady=(8, 0))
        self.lbl_pie = ttk.Label(pie, text="", style="Sub.TLabel")
        self.lbl_pie.pack(side="left")
        ttk.Button(pie, text="Ajustes", style="Link.TButton", command=self.ajustes).pack(side="right")
        ttk.Button(pie, text="Asignaturas y horario", style="Link.TButton", command=self.reconfigurar).pack(side="right")
        ttk.Button(pie, text="Registro", style="Link.TButton", command=self.ver_log).pack(side="right")

        r.protocol("WM_DELETE_WINDOW", self.al_cerrar)

    POR_DEFECTO = "Predeterminado de Windows" if sys.platform == "win32" else "Predeterminado del sistema"

    def _cargar_mics(self, refrescar):
        """Rellena la lista de entradas. ↻ vuelve a buscar micros conectados después de abrir la app."""
        if refrescar and self.motor.activo:
            messagebox.showinfo("Entrada de audio", "Para buscar micros nuevos, para primero la escucha.")
            return
        try:
            self.mics = microfonos(refrescar)
        except Exception as e:
            self.mics = []
            self.log(f"No se pudieron listar las entradas de audio: {e}")
        nombres = [self.POR_DEFECTO] + [m["nombre"] for m in self.mics]
        self.cmb_mic["values"] = nombres
        guardado = cargar()["ajustes"].get("microfono")
        if isinstance(guardado, int):  # versión anterior guardaba el índice
            guardado = next((m["nombre"] for m in self.mics if m["indice"] == guardado), None)
        self.var_mic.set(guardado if guardado in nombres else self.POR_DEFECTO)
        if guardado and guardado not in nombres:
            self.log(f"La entrada «{guardado}» no está conectada; uso la predeterminada.")

    def _mic_cambiado(self, _e=None):
        nombre = self.var_mic.get()
        eleccion = None if nombre == self.POR_DEFECTO else nombre
        self.cfg = cargar()
        self.cfg["ajustes"]["microfono"] = eleccion
        guardar(self.cfg)
        if self.motor.activo:
            try:
                self.motor.cambiar_microfono(eleccion)
            except Exception as e:
                messagebox.showerror("Entrada de audio", f"No he podido usar esa entrada, sigo con la anterior.\n\n{e}")

    def _tick(self):
        m = self.motor
        if m.activo:
            estado = m.estado_texto
        elif m.transcribiendo():
            estado = f"Terminando de transcribir… ({m.pendientes()} fragmentos)"
        else:
            estado = "En pausa"
            self.btn_ini.configure(state="normal")
        sub = []
        if m.cargando_modelo:
            sub.append("Cargando el modelo de voz…")
        elif m.transcriptor.modelo is not None:
            sub.append(f"Voz: {m.transcriptor.descripcion}")
        if m.activo and m.microfono_actual:
            sub.append(f"Oyendo por: {m.microfono_actual}")
        if m.activo and m.pendientes() > 3:
            sub.append(f"{m.pendientes()} fragmentos en cola")
        self.cab.poner(estado, " · ".join(sub), grabando=bool(m.activo and getattr(m, "clase_id", None)))
        self.barra["value"] = m.nivel * 100
        lineas = "\n".join(m.ultimas_lineas[-12:])
        if self.txt.get("1.0", "end").strip() != lineas.strip():
            self.txt.configure(state="normal")
            self.txt.delete("1.0", "end")
            self.txt.insert("end", lineas)
            self.txt.see("end")
            self.txt.configure(state="disabled")
        self.lbl_pie.configure(text="Resúmenes: " + ("al acabar cada clase" if resumen_en_pc(cargar()) else "desde Mis clases"))
        self.root.after(500, self._tick)

    # ---------- acciones ----------
    def iniciar(self):
        self.cfg = cargar()
        if not self.cfg["asignaturas"]:
            if messagebox.askyesno("Faltan tus asignaturas", "Todavía no has puesto tus asignaturas. ¿Las añadimos ahora?"):
                self.reconfigurar()
            return
        d = DialogoModo(self.root, self.cfg)
        if not d.resultado:
            return
        modo, asig = d.resultado
        try:
            self.motor.iniciar(modo, asig)
        except Exception as e:
            messagebox.showerror("No he podido empezar", str(e))
            return
        self.btn_ini.configure(state="disabled")
        self.btn_parar.configure(state="normal")
        self.btn_cambiar.configure(state="normal")

    def parar(self):
        self.motor.parar()
        self.btn_parar.configure(state="disabled")
        self.btn_cambiar.configure(state="disabled")

    def cambiar(self):
        d = DialogoModo(self.root, cargar(), solo_manual=True)
        if d.resultado:
            self.motor.cambiar_asignatura(d.resultado[1])

    def ajustes(self):
        DialogoAjustes(self.root, self.buscar_actualizacion)

    def reconfigurar(self):
        if self.motor.activo:
            messagebox.showinfo("Asignaturas y horario", "Para la escucha antes de cambiar el horario.")
            return
        self.root.withdraw()
        lanzar_asistente()
        self.cfg = cargar()
        self.motor.cfg = self.cfg
        self.url_hub = self.cfg["ajustes"].get("url_hub") or self.url_hub
        self._mostrar()

    def ver_log(self):
        w = tk.Toplevel(self.root)
        w.title("Registro")
        w.geometry("640x360")
        t = tk.Text(w, wrap="word", font=self.f.mono, background=tema.CARD, foreground=tema.INK, padx=10, pady=8,
                    relief="flat", highlightthickness=0)
        t.pack(fill="both", expand=True)
        t.insert("end", "\n".join(self.logs))
        t.see("end")

    def al_cerrar(self):
        if self.motor.activo or self.motor.transcribiendo():
            if self._a_bandeja():
                return
            if not messagebox.askyesno("Salir", "Estoy escuchando o transcribiendo. ¿Parar y salir?"):
                return
            self.motor.parar()
        self.salir()

    def _a_bandeja(self):
        """Oculta la ventana y deja un icono junto al reloj (si pystray está instalado)."""
        try:
            import pystray
            import PIL  # noqa: F401
        except Exception:
            return False
        if self.icono is None:
            img = tema.icono(64)
            menu = pystray.Menu(
                pystray.MenuItem("Mostrar", lambda: self.root.after(0, self._mostrar), default=True),
                pystray.MenuItem("Abrir Mis clases", lambda: webbrowser.open(self.url_hub)),
                pystray.MenuItem("Parar y salir", lambda: self.root.after(0, self._parar_y_salir)),
            )
            self.icono = pystray.Icon("agente_clases", img, "Estudio", menu)
            self.icono.run_detached()
        if sys.platform.startswith("linux"):
            # The tray icon may not show (Wayland, GNOME without AppIndicator): keep the window in the taskbar
            self.root.iconify()
        else:
            self.root.withdraw()
        return True

    def _mostrar(self):
        self.root.deiconify()
        self.root.lift()

    def _parar_y_salir(self):
        self.motor.parar()
        self.salir()

    def salir(self):
        self.motor.activo = False
        self.motor.guardar_estado()
        if self.motor.transcribiendo():
            # Deja terminar la cola en segundo plano unos segundos como máximo
            self.motor._hilo_trans.join(timeout=60)
        if self.icono:
            self.icono.stop()
        self.root.destroy()


class DialogoModo(tk.Toplevel):
    def __init__(self, padre, cfg, solo_manual=False):
        super().__init__(padre)
        self.resultado = None
        self.cfg = cfg
        self.title("¿Cómo quieres que funcione?" if not solo_manual else "Cambiar asignatura")
        self.transient(padre)
        self.resizable(False, False)
        self.configure(background=tema.CARD)
        fu = tema.Fuentes(self)
        f = ttk.Frame(self, style="Card.TFrame", padding=20)
        f.pack(fill="both", expand=True)
        fr, prox = horario.asignatura_actual(cfg, datetime.now())
        if not solo_manual:
            if fr:
                ahora = f"Ahora toca {nombre_asignatura(cfg, fr['asignatura'])} (hasta las {fr['fin']})."
            elif prox:
                ahora = f"Ahora no hay clase. La próxima es {nombre_asignatura(cfg, prox['asignatura'])} a las {prox['inicio']}."
            else:
                ahora = "Hoy no quedan clases en tu horario."
            ttk.Label(f, text="Automático", style="Seccion.TLabel").pack(anchor="w")
            ttk.Label(f, style="CardSub.TLabel", font=fu.texto, text="Uso tu horario y la hora para guardar cada clase en su asignatura, "
                              "y cambio solo cuando empieza la siguiente. " + ahora,
                      wraplength=380).pack(anchor="w", pady=(2, 6))
            ttk.Button(f, text="Empezar en automático", style="Pri.TButton", command=self._auto).pack(anchor="w", pady=(0, 14))
            ttk.Separator(f).pack(fill="x", pady=(0, 10))
            ttk.Label(f, text="Manual", style="Seccion.TLabel").pack(anchor="w")
            ttk.Label(f, style="CardSub.TLabel", font=fu.texto, text="Elige tú la asignatura. Todo lo que oiga irá ahí hasta que pares o la cambies.",
                      wraplength=380).pack(anchor="w", pady=(2, 6))
        self.var = tk.StringVar(value=(fr or {}).get("asignatura") or cfg["asignaturas"][0]["id"])
        for a in cfg["asignaturas"]:
            ttk.Radiobutton(f, text=a["nombre"], value=a["id"], variable=self.var).pack(anchor="w")
        ttk.Button(f, text="Empezar con esta asignatura" if not solo_manual else "Cambiar",
                   command=self._manual).pack(anchor="w", pady=(10, 0))
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window()

    def _auto(self):
        self.resultado = ("auto", None)
        self.destroy()

    def _manual(self):
        self.resultado = ("manual", self.var.get())
        self.destroy()


class DialogoAjustes(tk.Toplevel):
    MODELOS = ["auto", "small", "medium", "large-v3-turbo", "large-v3"]

    def __init__(self, padre, buscar_actualizacion=None):
        super().__init__(padre)
        self.title("Ajustes")
        self.transient(padre)
        self.resizable(False, False)
        self.configure(background=tema.CARD)
        self.cfg = cargar()
        aj = self.cfg["ajustes"]
        f = ttk.Frame(self, style="Card.TFrame", padding=20)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Clave de la API de Claude (opcional)", style="Card.TLabel").pack(anchor="w")
        self.var_clave = tk.StringVar(value=aj.get("anthropic_api_key", ""))
        ttk.Entry(f, textvariable=self.var_clave, show="•", width=52).pack(anchor="w", pady=(2, 2))
        ttk.Label(f, text="Sin clave, los resúmenes se hacen desde tu panel Mis clases con tu cuenta de Claude. Con clave, se hacen aquí solos al acabar cada clase. Se guarda solo en config.json.",
                  style="CardSub.TLabel", wraplength=380).pack(anchor="w", pady=(0, 10))
        ttk.Label(f, text="Modelo de voz (auto = el mejor que aguante tu ordenador)", style="Card.TLabel").pack(anchor="w")
        self.var_mod = tk.StringVar(value=aj.get("modelo_whisper", "auto"))
        ttk.Combobox(f, textvariable=self.var_mod, values=self.MODELOS, state="readonly").pack(anchor="w", pady=(2, 10))
        self.var_audio = tk.BooleanVar(value=bool(aj.get("guardar_audio")))
        ttk.Checkbutton(f, text="Guardar también el audio (unos 115 MB por hora)", variable=self.var_audio).pack(anchor="w")
        ttk.Label(f, text="Las asignaturas y el horario se cambian con «Asignaturas y horario» en la ventana principal.",
                  style="CardSub.TLabel", wraplength=380).pack(anchor="w", pady=(10, 0))
        ver = ttk.Frame(f, style="Card.TFrame")
        ver.pack(fill="x", pady=(12, 0))
        ttk.Label(ver, text=f"Versión {VERSION}", style="CardSub.TLabel").pack(side="left")
        if buscar_actualizacion:
            ttk.Button(ver, text="Buscar actualizaciones", command=buscar_actualizacion).pack(side="right")
        fila = ttk.Frame(f, style="Card.TFrame")
        fila.pack(fill="x", pady=(14, 0))
        ttk.Button(fila, text="Guardar", style="Pri.TButton", command=self._guardar).pack(side="right")
        ttk.Button(fila, text="Cancelar", command=self.destroy).pack(side="right", padx=6)
        self.grab_set()

    def _guardar(self):
        aj = self.cfg["ajustes"]
        cambio_modelo = aj.get("modelo_whisper") != self.var_mod.get()
        aj["anthropic_api_key"] = self.var_clave.get().strip()
        aj["modelo_whisper"] = self.var_mod.get()
        aj["guardar_audio"] = self.var_audio.get()
        guardar(self.cfg)
        if cambio_modelo:
            messagebox.showinfo("Ajustes", "El nuevo modelo de voz se usará al volver a abrir Estudio.")
        if resumen_en_pc(self.cfg):
            repository = build_repository()
            for cid in resumen.pendientes(repositorio=repository):
                resumen.en_segundo_plano(cid, repositorio=repository)
        self.destroy()


def main():
    args = sys.argv[1:]
    if "--test-installer-launch" in args:
        if sys.platform != "win32" or os.environ.get("ESTUDIO_INSTALLER_TEST") != "1":
            raise RuntimeError("Installer test mode is disabled")
        from actualizacion import launch_windows_installer
        from pathlib import Path
        directory = Path(os.environ["ESTUDIO_INSTALLER_TEST_DIR"]).resolve()
        process = launch_windows_installer(
            str(directory / "installer-probe.exe"), str(directory / "install.log"))
        if process.wait(timeout=60) != 0:
            raise RuntimeError("Installer probe failed")
        if not (directory / "installed" / "probe.txt").is_file():
            raise RuntimeError("Installer probe did not install its marker")
        (directory / "launch.ok").write_text("ok", encoding="utf-8")
        return
    if "--migrate-sqlite" in args:
        from infrastructure.storage_activation import activate_sqlite
        from nucleo.config import RUTA_DATOS
        root = tk.Tk()
        root.withdraw()
        try:
            if messagebox.askyesno("Migrar a SQLite",
                "Cierra todas las otras instancias de Estudio, Claude y el servidor MCP. "
                "Actualiza el Hub a una versión compatible con SQLite antes de continuar. "
                "Los archivos JSON originales se conservarán. ¿Confirmas que todo está preparado?",
                parent=root):
                try:
                    database = activate_sqlite(RUTA_DATOS, offline_confirmed=True)
                    messagebox.showinfo("Migrar a SQLite", f"Migración verificada: {database}", parent=root)
                except Exception as error:
                    messagebox.showerror("Migrar a SQLite", str(error), parent=root)
                    raise
        finally:
            root.destroy()
        return
    if "--mcp" in args:
        import mcp_servidor
        mcp_servidor.main()
        return
    if "--integrar" in args or "--quitar-integracion" in args:
        import linux_desktop
        (linux_desktop.uninstall if "--quitar-integracion" in args else linux_desktop.install)()
        return
    if "--comprobar" in args:
        import comprobar
        comprobar.main()
        return
    if "--asistente" in args:
        from asistente.asistente import ejecutar
        ejecutar()
        return
    if "--registrar-mcp" in args or "--quitar-mcp" in args:
        import registrar_mcp
        registrar_mcp.registrar(quitar="--quitar-mcp" in args)
        return
    if "--al-arrancar" in args or "--buscar-actualizacion" in args:
        import actualizacion
        if "--al-arrancar" in args:
            actualizacion.novedades_si_toca()
        actualizacion.comprobar_y_avisar(forzar="--forzar" in args)
        return
    if "--descargar-modelo" in args:
        from nucleo.transcripcion import Transcriptor
        try:
            Transcriptor(cargar()["ajustes"]).cargar()
        except Exception:
            pass  # se volverá a intentar al abrir el agente
        return
    if not existe():
        lanzar_asistente()
        if not existe():
            return  # cerró el asistente sin terminar
    from nucleo.config import escribir_puntero
    escribir_puntero()
    if sys.platform.startswith("linux"):
        import linux_desktop
        linux_desktop.refresh_if_stale()
    root = tk.Tk()
    App(root, inicio="--inicio" in args)
    root.mainloop()


def _registrar_error():
    """En el .exe no hay consola: si algo revienta, que quede escrito en error.log."""
    import traceback
    from nucleo.config import RAIZ
    try:
        os.makedirs(RAIZ, exist_ok=True)
        with open(os.path.join(RAIZ, "error.log"), "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] {' '.join(sys.argv[1:])}\n")
            traceback.print_exc(file=f)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _registrar_error()
        raise
