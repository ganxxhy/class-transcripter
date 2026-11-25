"""Agente de clases: ventana pequeña para iniciar/parar la escucha y abrir el hub.

Opciones (las usa el instalador):
  --asistente       abre el asistente de configuración
  --inicio          arranque con Windows: escucha en automático y se queda junto al reloj
  --registrar-mcp   conecta el agente con la app de escritorio de Claude
  --quitar-mcp      lo desconecta (al desinstalar)
  --descargar-modelo  descarga el modelo de voz que toca para este ordenador
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
from nucleo.config import CONGELADA, RUTA_DATOS, api_key, cargar, existe, guardar, nombre_asignatura  # noqa: E402
from nucleo.motor import Motor, microfonos  # noqa: E402

os.makedirs(RUTA_DATOS, exist_ok=True)
RUTA_LOG = os.path.join(RUTA_DATOS, "agente.log")


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
        self.motor = Motor(log=self.log)
        self.url_hub = self.cfg["ajustes"].get("url_hub") or "https://claude.ai/code/artifacts"
        self.icono = None
        self._construir()
        self._recuperar()
        self.motor.precargar()
        self.motor.guardar_estado()
        self._tick()
        if inicio and self.cfg["horario"]:
            self.root.after(500, self._inicio_automatico)

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
        for cid in almacen.clases_abiertas_huerfanas():
            almacen.cerrar(cid)
            self.log(f"Recuperada clase sin cerrar: {cid}")
        if api_key(self.cfg):
            for cid in resumen.pendientes():
                resumen.en_segundo_plano(cid, self.log)

    # ---------- interfaz ----------
    def _construir(self):
        r = self.root
        r.title("Agente de clases")
        r.geometry("520x560")
        r.minsize(440, 460)
        st = ttk.Style()
        try:
            st.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            pass
        st.configure("Estado.TLabel", font=("Segoe UI", 13, "bold"))
        st.configure("Sub.TLabel", foreground="#5d6676")

        f = ttk.Frame(r, padding=14)
        f.pack(fill="both", expand=True)
        self.lbl_estado = ttk.Label(f, text="Parado", style="Estado.TLabel", wraplength=480)
        self.lbl_estado.pack(anchor="w")
        self.lbl_sub = ttk.Label(f, text="", style="Sub.TLabel", wraplength=480)
        self.lbl_sub.pack(anchor="w", pady=(2, 10))

        fila = ttk.Frame(f)
        fila.pack(fill="x")
        self.btn_ini = ttk.Button(fila, text="▶  Iniciar", command=self.iniciar)
        self.btn_ini.pack(side="left")
        self.btn_parar = ttk.Button(fila, text="■  Parar", command=self.parar, state="disabled")
        self.btn_parar.pack(side="left", padx=6)
        self.btn_cambiar = ttk.Button(fila, text="Cambiar asignatura", command=self.cambiar, state="disabled")
        self.btn_cambiar.pack(side="left")
        ttk.Button(fila, text="Abrir hub", command=lambda: webbrowser.open(self.url_hub)).pack(side="right")

        mic = ttk.Frame(f)
        mic.pack(fill="x", pady=(12, 4))
        ttk.Label(mic, text="Entrada de audio").pack(side="left")
        self.mics = []
        self.var_mic = tk.StringVar()
        self.cmb_mic = ttk.Combobox(mic, textvariable=self.var_mic, state="readonly")
        self.cmb_mic.pack(side="left", fill="x", expand=True, padx=8)
        self.cmb_mic.bind("<<ComboboxSelected>>", self._mic_cambiado)
        ttk.Button(mic, text="↻", width=3, command=lambda: self._cargar_mics(True)).pack(side="left")
        self._cargar_mics(False)
        self.barra = ttk.Progressbar(f, maximum=100)
        self.barra.pack(fill="x", pady=(2, 10))

        ttk.Label(f, text="Lo último que he oído", style="Sub.TLabel").pack(anchor="w")
        self.txt = tk.Text(f, height=10, wrap="word", relief="flat", font=("Segoe UI", 10),
                           background="#f6f7f9", padx=8, pady=6)
        self.txt.pack(fill="both", expand=True, pady=(2, 8))
        self.txt.configure(state="disabled")

        pie = ttk.Frame(f)
        pie.pack(fill="x")
        self.lbl_pie = ttk.Label(pie, text="", style="Sub.TLabel")
        self.lbl_pie.pack(side="left")
        ttk.Button(pie, text="Ajustes", command=self.ajustes).pack(side="right")
        ttk.Button(pie, text="Asignaturas y horario", command=self.reconfigurar).pack(side="right", padx=(6, 0))
        ttk.Button(pie, text="Registro", command=self.ver_log).pack(side="right", padx=6)

        r.protocol("WM_DELETE_WINDOW", self.al_cerrar)

    POR_DEFECTO = "Predeterminado de Windows"

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
            self.lbl_estado.configure(text=m.estado_texto)
        elif m.transcribiendo():
            self.lbl_estado.configure(text=f"Terminando de transcribir… ({m.pendientes()} fragmentos)")
        else:
            self.lbl_estado.configure(text="Parado")
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
        self.lbl_sub.configure(text=" · ".join(sub))
        self.barra["value"] = m.nivel * 100
        lineas = "\n".join(m.ultimas_lineas[-12:])
        if self.txt.get("1.0", "end").strip() != lineas.strip():
            self.txt.configure(state="normal")
            self.txt.delete("1.0", "end")
            self.txt.insert("end", lineas)
            self.txt.see("end")
            self.txt.configure(state="disabled")
        self.lbl_pie.configure(text="Resúmenes: " + ("aquí, con tu clave" if api_key(cargar()) else "desde el hub"))
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
        DialogoAjustes(self.root)

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
        t = tk.Text(w, wrap="word", font=("Consolas", 9))
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
            from PIL import Image, ImageDraw
        except Exception:
            return False
        if self.icono is None:
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            dr = ImageDraw.Draw(img)
            dr.ellipse((4, 4, 60, 60), fill=(47, 91, 211))
            dr.rounded_rectangle((24, 14, 40, 38), radius=8, fill="white")
            dr.rectangle((30, 40, 34, 50), fill="white")
            menu = pystray.Menu(
                pystray.MenuItem("Mostrar", lambda: self.root.after(0, self._mostrar), default=True),
                pystray.MenuItem("Abrir hub", lambda: webbrowser.open(self.url_hub)),
                pystray.MenuItem("Parar y salir", lambda: self.root.after(0, self._parar_y_salir)),
            )
            self.icono = pystray.Icon("agente_clases", img, "Agente de clases", menu)
            self.icono.run_detached()
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
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        fr, prox = horario.asignatura_actual(cfg, datetime.now())
        if not solo_manual:
            if fr:
                ahora = f"Ahora toca {nombre_asignatura(cfg, fr['asignatura'])} (hasta las {fr['fin']})."
            elif prox:
                ahora = f"Ahora no hay clase. La próxima es {nombre_asignatura(cfg, prox['asignatura'])} a las {prox['inicio']}."
            else:
                ahora = "Hoy no quedan clases en tu horario."
            ttk.Label(f, text="Automático", font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ttk.Label(f, text="Uso tu horario y la hora para guardar cada clase en su asignatura, "
                              "y cambio solo cuando empieza la siguiente. " + ahora,
                      wraplength=380).pack(anchor="w", pady=(2, 6))
            ttk.Button(f, text="Empezar en automático", command=self._auto).pack(anchor="w", pady=(0, 14))
            ttk.Separator(f).pack(fill="x", pady=(0, 10))
            ttk.Label(f, text="Manual", font=("Segoe UI", 11, "bold")).pack(anchor="w")
            ttk.Label(f, text="Elige tú la asignatura. Todo lo que oiga irá ahí hasta que pares o la cambies.",
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

    def __init__(self, padre):
        super().__init__(padre)
        self.title("Ajustes")
        self.transient(padre)
        self.resizable(False, False)
        self.cfg = cargar()
        aj = self.cfg["ajustes"]
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Clave de la API de Claude (opcional)").pack(anchor="w")
        self.var_clave = tk.StringVar(value=aj.get("anthropic_api_key", ""))
        ttk.Entry(f, textvariable=self.var_clave, show="•", width=52).pack(anchor="w", pady=(2, 2))
        ttk.Label(f, text="Sin clave, los resúmenes se hacen desde el hub con tu cuenta de Claude. Con clave, se hacen aquí solos al acabar cada clase. Se guarda solo en config.json.",
                  foreground="#5d6676", wraplength=380).pack(anchor="w", pady=(0, 10))
        ttk.Label(f, text="Modelo de voz (auto = el mejor que aguante tu ordenador)").pack(anchor="w")
        self.var_mod = tk.StringVar(value=aj.get("modelo_whisper", "auto"))
        ttk.Combobox(f, textvariable=self.var_mod, values=self.MODELOS, state="readonly").pack(anchor="w", pady=(2, 10))
        self.var_audio = tk.BooleanVar(value=bool(aj.get("guardar_audio")))
        ttk.Checkbutton(f, text="Guardar también el audio (unos 115 MB por hora)", variable=self.var_audio).pack(anchor="w")
        ttk.Label(f, text="El horario y los márgenes se cambian en config.json.",
                  foreground="#5d6676").pack(anchor="w", pady=(10, 0))
        fila = ttk.Frame(f)
        fila.pack(fill="x", pady=(12, 0))
        ttk.Button(fila, text="Guardar", command=self._guardar).pack(side="right")
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
            messagebox.showinfo("Ajustes", "El nuevo modelo de voz se usará al volver a abrir el agente.")
        if aj["anthropic_api_key"]:
            for cid in resumen.pendientes():
                resumen.en_segundo_plano(cid)
        self.destroy()


def main():
    args = sys.argv[1:]
    if "--asistente" in args:
        from asistente.asistente import ejecutar
        ejecutar()
        return
    if "--registrar-mcp" in args or "--quitar-mcp" in args:
        import registrar_mcp
        registrar_mcp.registrar(quitar="--quitar-mcp" in args)
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
    root = tk.Tk()
    App(root, inicio="--inicio" in args)
    root.mainloop()


if __name__ == "__main__":
    main()
