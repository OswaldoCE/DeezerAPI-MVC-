import io
import queue
import threading
import requests
import customtkinter as ctk
import pygame
from PIL import Image, ImageDraw
from tkinter import messagebox

from backend import BaseDatos, ColaFIFO, PilaLIFO
from deezer_service import DeezerService

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class SpotifyAppCustom(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Capytacticos music")
        self.geometry("1200x780")
        self.configure(fg_color="#000000")

        self.deezer_service = DeezerService()
        self.db = BaseDatos()

        self.cola_reproduccion = ColaFIFO()
        self.pila_historial = PilaLIFO()

        self.playlist_actual_id = None
        self.playlist_actual_nombre = None
        self.cancion_seleccionada = None
        self.image_cache = {}
        self.ui_queue = queue.Queue()
        self.audio_disponible = False
        self.preview_cargado = False
        self.preview_pausado = False
        try:
            pygame.mixer.init()
            self.audio_disponible = True
        except pygame.error:
            pass

        self.crear_layout_principal()
        self.cargar_playlists_sidebar()
        self.mostrar_home()
        self.after(50, self.procesar_tareas_ui)

    # ==========================================
    # IMÁGENES Y ASINCRONÍA
    # ==========================================

    def procesar_tareas_ui(self):
        while True:
            try:
                callback, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            try:
                callback(*args)
            except Exception as error:
                print(f"Error actualizando la interfaz: {error}")

        self.after(50, self.procesar_tareas_ui)

    def obtener_imagen_remota(self, url, size=(140, 140), circular=False):
        if not url:
            return None
        cache_key = f"{url}_{size}_{circular}"
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]

        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                img = img.resize(size, Image.Resampling.LANCZOS)

                if circular:
                    mask = Image.new('L', size, 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0) + size, fill=255)
                    output = Image.new('RGBA', size, (0, 0, 0, 0))
                    output.paste(img, (0, 0), mask=mask)
                    img = output

                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
                self.image_cache[cache_key] = ctk_img
                return ctk_img
        except Exception:
            pass
        return None

    def async_load_image(self, url, size, circular, callback):
        def worker():
            if not url:
                return

            cache_key = f"{url}_{size}_{circular}"
            try:
                resp = requests.get(url, timeout=5)
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                img = img.resize(size, Image.Resampling.LANCZOS)

                if circular:
                    mask = Image.new("L", size, 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0) + size, fill=255)
                    output = Image.new("RGBA", size, (0, 0, 0, 0))
                    output.paste(img, (0, 0), mask=mask)
                    img = output

                self.ui_queue.put((self.aplicar_imagen, (img, cache_key, size, callback)))
            except Exception as error:
                print(f"Error cargando imagen: {error}")
        threading.Thread(target=worker, daemon=True).start()

    def aplicar_imagen(self, img, cache_key, size, callback):
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        self.image_cache[cache_key] = ctk_img
        callback(ctk_img)

    def cargar_preview(self, track_dict):
        preview_url = track_dict.get('preview')
        if not preview_url:
            self.ui_queue.put((self.mostrar_error_audio, ("Esta canción no tiene preview disponible.",)))
            return

        try:
            response = requests.get(preview_url, timeout=10)
            response.raise_for_status()
            self.ui_queue.put((self.reproducir_preview, (response.content, track_dict)))
        except requests.RequestException as error:
            self.ui_queue.put((self.mostrar_error_audio, (f"No se pudo cargar el preview: {error}",)))

    def reproducir_preview(self, audio_data, track_dict):
        if not self.audio_disponible:
            self.mostrar_error_audio("No se pudo iniciar el audio en este equipo.")
            return

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(io.BytesIO(audio_data), "mp3")
            pygame.mixer.music.play()
            self.preview_cargado = True
            self.preview_pausado = False
            self.btn_pause_preview.configure(text="⏸ Pausar")
            self.lbl_now_playing.configure(
                text=f"▶ Preview: {track_dict['titulo']} — {track_dict['artista']}"
            )
        except pygame.error as error:
            self.mostrar_error_audio(f"No se pudo reproducir el preview: {error}")

    def mostrar_error_audio(self, mensaje):
        messagebox.showwarning("Preview no disponible", mensaje)

    def alternar_pause_preview(self):
        if not self.audio_disponible or not self.preview_cargado:
            self.mostrar_error_audio("Primero reproduce una canción.")
            return

        if self.preview_pausado:
            pygame.mixer.music.unpause()
            self.preview_pausado = False
            self.btn_pause_preview.configure(text="⏸ Pausar")
            self.lbl_now_playing.configure(text="▶ Preview reproduciéndose")
        elif pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.preview_pausado = True
            self.btn_pause_preview.configure(text="▶ Reanudar")
            self.lbl_now_playing.configure(text="⏸ Preview pausado")
        else:
            self.preview_cargado = False
            self.mostrar_error_audio("El preview ya terminó.")

    # ==========================================
    # LAYOUT
    # ==========================================

    def crear_layout_principal(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=12, fg_color="#121212")
        self.sidebar.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="nsew")
        self.sidebar.grid_rowconfigure(3, weight=1)

        lbl_logo = ctk.CTkLabel(self.sidebar, text="Capytacticoss Music", font=ctk.CTkFont(size=22, weight="bold"), text_color="#29ADDD")
        lbl_logo.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        frame_nueva_pl = ctk.CTkFrame(self.sidebar, fg_color="#181818", corner_radius=8)
        frame_nueva_pl.grid(row=1, column=0, padx=12, pady=10, sticky="ew")

        self.entry_nueva_pl = ctk.CTkEntry(frame_nueva_pl, placeholder_text="Nueva Playlist...", width=150, height=32, fg_color="#282828", border_width=0)
        self.entry_nueva_pl.pack(side="left", padx=8, pady=8, fill="x", expand=True)

        btn_crear_pl = ctk.CTkButton(
            frame_nueva_pl, text="+", width=32, height=32, fg_color="#29ADDD", 
            hover_color="#2cd2da", text_color="#000000", font=ctk.CTkFont(size=18, weight="bold"), 
            command=self.crear_playlist
        )
        btn_crear_pl.pack(side="right", padx=(0, 8), pady=8)

        btn_home = ctk.CTkButton(
            self.sidebar, text="  Inicio", anchor="w", fg_color="#181818", hover_color="#282828",
            text_color="#FFFFFF", font=ctk.CTkFont(size=14, weight="bold"), height=38, command=self.mostrar_home
        )
        btn_home.grid(row=2, column=0, padx=12, pady=(5, 10), sticky="ew")

        lbl_biblio = ctk.CTkLabel(self.sidebar, text=" Tu Biblioteca", font=ctk.CTkFont(size=13, weight="bold"), text_color="#A7A7A7")
        lbl_biblio.grid(row=3, column=0, padx=20, pady=(5, 5), sticky="nw")

        self.scroll_playlists = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.scroll_playlists.grid(row=3, column=0, padx=8, pady=(35, 5), sticky="nsew")

        # Main Content
        self.main_content = ctk.CTkFrame(self, corner_radius=12, fg_color="#121212")
        self.main_content.grid(row=0, column=1, padx=(0, 8), pady=(8, 4), sticky="nsew")
        self.main_content.grid_rowconfigure(2, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        frame_search = ctk.CTkFrame(self.main_content, fg_color="transparent")
        frame_search.grid(row=0, column=0, padx=20, pady=15, sticky="ew")

        self.entry_search = ctk.CTkEntry(
            frame_search, placeholder_text="🔍 ¿Qué quieres escuchar? (Artista o Canción)", 
            width=420, height=38, corner_radius=20, fg_color="#242424", border_width=0
        )
        self.entry_search.pack(side="left", padx=5)
        self.entry_search.bind("<Return>", lambda e: self.ejecutar_busqueda())

        btn_search = ctk.CTkButton(
            frame_search, text="Buscar", width=90, height=38, corner_radius=20, 
            fg_color="#50C3EC", hover_color="#30cad5", text_color="#000000", 
            font=ctk.CTkFont(weight="bold"), command=self.ejecutar_busqueda
        )
        btn_search.pack(side="left", padx=5)

        btn_undo = ctk.CTkButton(
            frame_search, text="↩ Deshacer cambio", width=140, height=38, corner_radius=20, 
            fg_color="#282828", hover_color="#3E3E3E", command=self.deshacer_accion
        )
        btn_undo.pack(side="right", padx=5)

        # Panel de Selección Interactiva
        self.frame_guardado_inline = ctk.CTkFrame(self.main_content, fg_color="#181818", corner_radius=10)
        self.frame_guardado_inline.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.frame_guardado_inline.grid_remove()

        self.scroll_main = ctk.CTkScrollableFrame(self.main_content, fg_color="transparent")
        self.scroll_main.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="nsew")

        # Player Bar
        self.player_bar = ctk.CTkFrame(self, height=75, corner_radius=12, fg_color="#181818")
        self.player_bar.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")

        self.lbl_now_playing = ctk.CTkLabel(
            self.player_bar, text="🎵 Selecciona una canción para reproducir", 
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF"
        )
        self.lbl_now_playing.pack(side="left", padx=20)

        self.btn_pause_preview = ctk.CTkButton(
            self.player_bar, text="⏸ Pausar", width=95, height=28, corner_radius=14,
            fg_color="#29ADDD", hover_color="#2cd2da", text_color="#000000",
            font=ctk.CTkFont(size=11, weight="bold"), command=self.alternar_pause_preview
        )
        self.btn_pause_preview.pack(side="left", padx=5)

        frame_player_right = ctk.CTkFrame(self.player_bar, fg_color="transparent")
        frame_player_right.pack(side="right", padx=20)

        self.lbl_fifo_status = ctk.CTkLabel(
            frame_player_right, text="Cola de reproducción: 0 canciones", 
            font=ctk.CTkFont(size=12), text_color="#A7A7A7"
        )
        self.lbl_fifo_status.pack(side="left", padx=(0, 10))

        btn_ver_cola = ctk.CTkButton(
            frame_player_right, text="≡ Ver cola", width=80, height=28, corner_radius=14,
            fg_color="#282828", hover_color="#3E3E3E", text_color="#FFFFFF",
            font=ctk.CTkFont(size=11, weight="bold"), command=self.abrir_modal_cola
        )
        btn_ver_cola.pack(side="left")

    # ==========================================
    # MODAL: COLA DE REPRODUCCIÓN
    # ==========================================

    def abrir_modal_cola(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Cola de Reproducción")
        modal.geometry("450x520")
        modal.configure(fg_color="#121212")
        modal.transient(self)
        modal.grab_set()

        canciones_encoladas = self.cola_reproduccion.obtener_todas()

        lbl_tit = ctk.CTkLabel(
            modal, text="≡ Cola de Reproducción", 
            font=ctk.CTkFont(size=18, weight="bold"), text_color="#FFFFFF"
        )
        lbl_tit.pack(pady=(15, 2))

        duracion_total_seg = sum(track.get('duracion_seg', 0) for track in canciones_encoladas)
        horas = duracion_total_seg // 3600
        minutos = (duracion_total_seg % 3600) // 60
        segundos = duracion_total_seg % 60

        if horas > 0:
            tiempo_fmt = f"⏱ Duración total: {horas} h {minutos} min ({len(canciones_encoladas)} canciones)"
        else:
            tiempo_fmt = f"⏱ Duración total: {minutos:02d}:{segundos:02d} min ({len(canciones_encoladas)} canciones)"

        lbl_tiempo = ctk.CTkLabel(
            modal, text=tiempo_fmt, 
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#29ADDD"
        )
        lbl_tiempo.pack(pady=(0, 15))

        if not canciones_encoladas:
            lbl_vacia = ctk.CTkLabel(
                modal, text="La cola está vacía.\nAñade canciones haciendo clic en '+ Cola'.", 
                font=ctk.CTkFont(size=13), text_color="#A7A7A7"
            )
            lbl_vacia.pack(expand=True)
            return

        scroll_cola = ctk.CTkScrollableFrame(modal, fg_color="#181818", corner_radius=10)
        scroll_cola.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        for idx, track in enumerate(canciones_encoladas, 1):
            dur_seg = track.get('duracion_seg', 0)
            m = dur_seg // 60
            s = dur_seg % 60
            dur_fmt = f"{m}:{s:02d}"

            item_frame = ctk.CTkFrame(scroll_cola, fg_color="#242424", corner_radius=6, height=45)
            item_frame.pack(fill="x", pady=4, padx=5)

            lbl_num = ctk.CTkLabel(item_frame, text=f"{idx}.", width=25, text_color="#29ADDD", font=ctk.CTkFont(size=12, weight="bold"))
            lbl_num.pack(side="left", padx=(8, 0))

            lbl_info = ctk.CTkLabel(
                item_frame, text=f"{track['titulo']}\n{track['artista']}", 
                font=ctk.CTkFont(size=11), text_color="#FFFFFF", anchor="w", justify="left"
            )
            lbl_info.pack(side="left", padx=10, fill="x", expand=True)

            lbl_dur = ctk.CTkLabel(item_frame, text=dur_fmt, font=ctk.CTkFont(size=11), text_color="#A7A7A7")
            lbl_dur.pack(side="right", padx=10)

    # ==========================================
    # SELECCIÓN Y GUARDADO
    # ==========================================

    def seleccionar_cancion(self, track_dict):
        self.cancion_seleccionada = track_dict
        
        for widget in self.frame_guardado_inline.winfo_children():
            widget.destroy()

        self.frame_guardado_inline.grid()

        lbl_info = ctk.CTkLabel(
            self.frame_guardado_inline, 
            text=f"🎵 Seleccionada: '{track_dict['titulo']}' de {track_dict['artista']}", 
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#29ADDD"
        )
        lbl_info.pack(anchor="w", padx=15, pady=(10, 5))

        playlists = self.db.obtener_playlists()
        if not playlists:
            lbl_sin_pl = ctk.CTkLabel(self.frame_guardado_inline, text="Crea una playlist en el menú izquierdo para guardarla.", text_color="#A7A7A7")
            lbl_sin_pl.pack(anchor="w", padx=15, pady=(0, 10))
            return

        lbl_instruc = ctk.CTkLabel(self.frame_guardado_inline, text="Selecciona la(s) playlist(s) donde deseas agregarla:", font=ctk.CTkFont(size=12), text_color="#FFFFFF")
        lbl_instruc.pack(anchor="w", padx=15, pady=(0, 5))

        frame_checkboxes = ctk.CTkFrame(self.frame_guardado_inline, fg_color="transparent")
        frame_checkboxes.pack(fill="x", padx=15, pady=5)

        self.check_vars = {}
        for pl_id, nombre in playlists:
            var = ctk.BooleanVar()
            chk = ctk.CTkCheckBox(frame_checkboxes, text=nombre, variable=var, fg_color="#29ADDD", hover_color="#2cd2da")
            chk.pack(side="left", padx=10, pady=5)
            self.check_vars[pl_id] = (var, nombre)

        btn_confirmar = ctk.CTkButton(
            self.frame_guardado_inline, text="Guardar en Playlist(s)", fg_color="#29ADDD",
            hover_color="#2cd2da", text_color="#000000", font=ctk.CTkFont(weight="bold"),
            command=self.confirmar_guardado_multiple
        )
        btn_confirmar.pack(anchor="e", padx=15, pady=(5, 10))

    def confirmar_guardado_multiple(self):
        if not self.cancion_seleccionada:
            return

        agregadas = []
        for pl_id, (var, nombre) in self.check_vars.items():
            if var.get():
                relacion_id = self.db.agregar_cancion_a_playlist(pl_id, self.cancion_seleccionada)
                self.pila_historial.apilar({
                    'tipo': 'agregar',
                    'playlist_id': pl_id,
                    'relacion_id': relacion_id,
                    'track': self.cancion_seleccionada,
                })
                agregadas.append(nombre)

        if agregadas:
            messagebox.showinfo("Éxito", f"'{self.cancion_seleccionada['titulo']}' guardada en: {', '.join(agregadas)}.")
            if self.playlist_actual_id in self.check_vars and self.check_vars[self.playlist_actual_id][0].get():
                self.cargar_playlist_seleccionada(self.playlist_actual_id, self.playlist_actual_nombre)
        else:
            messagebox.showwarning("Atención", "Selecciona al menos una playlist.")

        self.frame_guardado_inline.grid_remove()

    # ==========================================
    # VISTAS (PANTALLA DE INICIO )
    # ==========================================

    def limpiar_pantalla_principal(self):
        self.frame_guardado_inline.grid_remove()
        for child in self.scroll_main.winfo_children():
            child.destroy()

    def mostrar_home(self):
        self.limpiar_pantalla_principal()
        self.playlist_actual_id = None

        lbl_sec1 = ctk.CTkLabel(self.scroll_main, text="Canciones del momento", font=ctk.CTkFont(size=22, weight="bold"), text_color="#FFFFFF")
        lbl_sec1.pack(anchor="w", pady=(10, 10))

        scroll_cards = ctk.CTkScrollableFrame(self.scroll_main, orientation="horizontal", height=250, fg_color="transparent")
        scroll_cards.pack(fill="x", pady=(0, 20))

        lbl_sec2 = ctk.CTkLabel(self.scroll_main, text="Artistas populares", font=ctk.CTkFont(size=22, weight="bold"), text_color="#FFFFFF")
        lbl_sec2.pack(anchor="w", pady=(10, 10))

        scroll_artists = ctk.CTkScrollableFrame(self.scroll_main, orientation="horizontal", height=240, fg_color="transparent")
        scroll_artists.pack(fill="x", pady=(0, 10))

        lbl_estado = ctk.CTkLabel(
            self.scroll_main, text="Cargando contenido de Deezer...",
            text_color="#A7A7A7"
        )
        lbl_estado.pack(anchor="w", pady=10)

        try:
            chart_tracks, chart_artists = self.deezer_service.obtener_top_tracks_y_artistas()
            lbl_estado.destroy()
            for td in chart_tracks:
                self.renderizar_tarjeta_cancion(scroll_cards, td)
            for ad in chart_artists:
                self.renderizar_tarjeta_artista(scroll_artists, ad)

            if not chart_tracks and not chart_artists:
                ctk.CTkLabel(
                    self.scroll_main,
                    text="Deezer no devolvió contenido. Revisa la conexión a Internet.",
                    text_color="#E74C3C"
                ).pack(anchor="w", pady=20)
        except Exception as error:
            lbl_estado.destroy()
            ctk.CTkLabel(
                self.scroll_main,
                text=f"No se pudieron cargar los datos de Deezer: {error}",
                text_color="#E74C3C"
            ).pack(anchor="w", pady=20)

    def renderizar_tarjeta_cancion(self, parent, track_dict):
        card = ctk.CTkFrame(parent, width=170, height=230, fg_color="#181818", corner_radius=10)
        card.pack(side="left", padx=8, pady=5)
        card.pack_propagate(False)

        img_label = ctk.CTkLabel(card, text="🎵", width=150, height=130, fg_color="#282828", corner_radius=8)
        img_label.pack(pady=(10, 5), padx=10)

        if track_dict.get('cover_url'):
            self.async_load_image(track_dict['cover_url'], (150, 130), False, lambda img: img_label.configure(image=img, text=""))

        lbl_t = ctk.CTkLabel(card, text=track_dict['titulo'], font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF", anchor="w")
        lbl_t.pack(fill="x", padx=10)

        lbl_a = ctk.CTkLabel(card, text=track_dict['artista'], font=ctk.CTkFont(size=11), text_color="#A7A7A7", anchor="w")
        lbl_a.pack(fill="x", padx=10)

        card.bind("<Button-1>", lambda e: self.seleccionar_cancion(track_dict))
        img_label.bind("<Button-1>", lambda e: self.reproducir_cancion(track_dict))

    def renderizar_tarjeta_artista(self, parent, artist_dict):
        card = ctk.CTkFrame(parent, width=160, height=210, fg_color="#181818", corner_radius=10)
        card.pack(side="left", padx=8, pady=5)
        card.pack_propagate(False)

        img_label = ctk.CTkLabel(card, text="👤", width=130, height=130, fg_color="#282828", corner_radius=10)
        img_label.pack(pady=(10, 5), padx=15)

        if artist_dict.get('picture_url'):
            self.async_load_image(artist_dict['picture_url'], (130, 130), False, lambda img: img_label.configure(image=img, text=""))

        lbl_n = ctk.CTkLabel(card, text=artist_dict['nombre'], font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF", anchor="center")
        lbl_n.pack(fill="x", padx=10, pady=8)

        card.bind("<Button-1>", lambda e: self.cargar_vista_artista(artist_dict['id'], artist_dict['nombre']))
        img_label.bind("<Button-1>", lambda e: self.cargar_vista_artista(artist_dict['id'], artist_dict['nombre']))

    def ejecutar_busqueda(self):
        query = self.entry_search.get().strip()
        if not query:
            return

        self.limpiar_pantalla_principal()
        try:
            res = self.deezer_service.buscar_artista_o_canciones(query)
            if res['tipo'] == 'artista':
                self.cargar_vista_artista(res['id'], res['nombre'])
            elif res['tipo'] == 'mixto':
                self.mostrar_resultados_mixtos(res['artista'], res['items'])
            else:
                for idx, td in enumerate(res['items'], 1):
                    self.renderizar_fila_cancion_spotify(td, numero_index=idx)
        except Exception as e:
            messagebox.showerror("Error API", f"Error al realizar la búsqueda: {str(e)}")

    def mostrar_resultados_mixtos(self, artist_dict, tracks):
        if artist_dict:
            header = ctk.CTkFrame(self.scroll_main, fg_color="#0F3854", corner_radius=12, height=130)
            header.pack(fill="x", pady=(0, 20))
            header.pack_propagate(False)

            image_label = ctk.CTkLabel(header, text="👤", width=100, height=100, fg_color="#181818", corner_radius=10)
            image_label.pack(side="left", padx=20, pady=15)
            if artist_dict.get('picture_url'):
                self.async_load_image(artist_dict['picture_url'], (100, 100), False, lambda img: image_label.configure(image=img, text=""))

            info_frame = ctk.CTkFrame(header, fg_color="transparent")
            info_frame.pack(side="left", fill="y", pady=20)
            ctk.CTkLabel(info_frame, text="Artista encontrado", text_color="#29ADDD").pack(anchor="w")
            ctk.CTkLabel(
                info_frame, text=artist_dict['nombre'],
                font=ctk.CTkFont(size=24, weight="bold"), text_color="#FFFFFF"
            ).pack(anchor="w")
            ctk.CTkButton(
                header, text="Ver perfil", width=90, height=28,
                fg_color="#29ADDD", hover_color="#2cd2da", text_color="#000000",
                command=lambda: self.cargar_vista_artista(artist_dict['id'], artist_dict['nombre'])
            ).pack(side="right", padx=20)

        ctk.CTkLabel(
            self.scroll_main, text="Canciones encontradas",
            font=ctk.CTkFont(size=18, weight="bold"), text_color="#FFFFFF"
        ).pack(anchor="w", pady=(0, 8))
        for idx, track in enumerate(tracks, 1):
            self.renderizar_fila_cancion_spotify(track, numero_index=idx)

    def cargar_vista_artista(self, artist_id, artist_nombre):
        self.limpiar_pantalla_principal()

        header_frame = ctk.CTkFrame(self.scroll_main, fg_color="#0F3854", corner_radius=12, height=130)
        header_frame.pack(fill="x", pady=(0, 20))
        header_frame.pack_propagate(False)

        lbl_art_img = ctk.CTkLabel(header_frame, text="👤", width=100, height=100, fg_color="#181818", corner_radius=50)
        lbl_art_img.pack(side="left", padx=20, pady=15)

        info_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="y", pady=25)

        lbl_verif = ctk.CTkLabel(info_frame, text="✓ Artista verificado", font=ctk.CTkFont(size=11), text_color="#29ADDD")
        lbl_verif.pack(anchor="w")

        lbl_nombre = ctk.CTkLabel(info_frame, text=artist_nombre, font=ctk.CTkFont(size=28, weight="bold"), text_color="#FFFFFF")
        lbl_nombre.pack(anchor="w")

        lbl_pop = ctk.CTkLabel(self.scroll_main, text="Popular", font=ctk.CTkFont(size=18, weight="bold"), text_color="#FFFFFF")
        lbl_pop.pack(anchor="w", pady=(0, 10))

        try:
            picture_url, top_tracks = self.deezer_service.obtener_detalle_artista(artist_id)
            if picture_url:
                self.async_load_image(picture_url, (100, 100), True, lambda img: lbl_art_img.configure(image=img, text=""))

            top_5 = top_tracks[:5]
            resto = top_tracks[5:]

            for idx, td in enumerate(top_5, 1):
                self.renderizar_fila_cancion_spotify(td, numero_index=idx)

            if resto:
                frame_resto = ctk.CTkFrame(self.scroll_main, fg_color="transparent")

                def mostrar_resto():
                    btn_ver_mas.destroy()
                    for idx, td in enumerate(resto, 6):
                        self.renderizar_fila_cancion_spotify(td, parent=frame_resto, numero_index=idx)

                btn_ver_mas = ctk.CTkButton(
                    self.scroll_main, text="Mostrar más", fg_color="transparent", hover_color="#282828",
                    text_color="#A7A7A7", font=ctk.CTkFont(weight="bold"), command=mostrar_resto
                )
                btn_ver_mas.pack(anchor="w", pady=10)
                frame_resto.pack(fill="x")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron obtener las canciones: {str(e)}")

    def renderizar_fila_cancion_spotify(self, track_dict, parent=None, numero_index=None, es_playlist=False, pc_id=None):
        target_parent = parent if parent else self.scroll_main

        minutos = track_dict['duracion_seg'] // 60
        segundos = track_dict['duracion_seg'] % 60
        dur_fmt = f"{minutos}:{segundos:02d}"

        card = ctk.CTkFrame(target_parent, fg_color="#181818", corner_radius=6, height=52)
        card.pack(fill="x", pady=3)

        if numero_index:
            lbl_num = ctk.CTkLabel(card, text=str(numero_index), width=30, text_color="#A7A7A7", font=ctk.CTkFont(size=13))
            lbl_num.pack(side="left", padx=(5, 0))

        lbl_thumb = ctk.CTkLabel(card, text="🎵", width=40, height=40, fg_color="#282828", corner_radius=4)
        lbl_thumb.pack(side="left", padx=10, pady=6)

        if track_dict.get('cover_url'):
            self.async_load_image(track_dict['cover_url'], (40, 40), False, lambda img: lbl_thumb.configure(image=img, text=""))

        btn_play = ctk.CTkButton(
            card, text="▶", width=28, height=28, corner_radius=14, fg_color="#29ADDD",
            hover_color="#2cd2da", text_color="#000000", command=lambda: self.reproducir_cancion(track_dict)
        )
        btn_play.pack(side="left", padx=5)

        lbl_info = ctk.CTkLabel(
            card, text=f"{track_dict['titulo']}  •  {track_dict['artista']}", 
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#FFFFFF", anchor="w"
        )
        lbl_info.pack(side="left", padx=10, fill="x", expand=True)

        lbl_album = ctk.CTkLabel(card, text=track_dict['album'], font=ctk.CTkFont(size=12), text_color="#A7A7A7", width=140, anchor="w")
        lbl_album.pack(side="left", padx=10)

        lbl_time = ctk.CTkLabel(card, text=dur_fmt, font=ctk.CTkFont(size=12), text_color="#A7A7A7", width=45)
        lbl_time.pack(side="left", padx=10)

        btn_fifo = ctk.CTkButton(
            card, text="+ Cola", width=65, height=26, fg_color="#282828", hover_color="#3E3E3E",
            font=ctk.CTkFont(size=11), command=lambda: self.encolar_cancion(track_dict)
        )
        btn_fifo.pack(side="left", padx=5)

        if not es_playlist:
            btn_add = ctk.CTkButton(
                card, text="➕ Playlist", width=75, height=26, fg_color="#29ADDD", hover_color="#2cd2da", text_color="#000000",
                font=ctk.CTkFont(size=11, weight="bold"), command=lambda: self.seleccionar_cancion(track_dict)
            )
            btn_add.pack(side="left", padx=(5, 10))
        else:
            btn_del = ctk.CTkButton(
                card, text="❌", width=32, height=26, fg_color="#E74C3C", hover_color="#C0392B",
                command=lambda: self.eliminar_cancion_playlist(pc_id)
            )
            btn_del.pack(side="left", padx=(5, 10))

    # ==========================================
    # LÓGICA DE PLAYLISTS & CONTROLES
    # ==========================================

    def cargar_playlists_sidebar(self):
        for child in self.scroll_playlists.winfo_children():
            child.destroy()

        playlists = self.db.obtener_playlists()
        for pl_id, nombre in playlists:
            btn = ctk.CTkButton(
                self.scroll_playlists, text=f"📄  {nombre}", anchor="w", fg_color="transparent",
                hover_color="#282828", text_color="#B3B3B3", font=ctk.CTkFont(size=13), height=36,
                command=lambda pid=pl_id, pnom=nombre: self.cargar_playlist_seleccionada(pid, pnom)
            )
            btn.pack(fill="x", pady=2)

    def crear_playlist(self):
        nombre = self.entry_nueva_pl.get().strip()
        if not nombre:
            messagebox.showwarning("Atención", "Escribe un nombre para la playlist.")
            return

        pid = self.db.crear_playlist(nombre)
        if pid:
            self.entry_nueva_pl.delete(0, 'end')
            self.cargar_playlists_sidebar()
            self.cargar_playlist_seleccionada(pid, nombre)
        else:
            messagebox.showerror("Error", f"La playlist '{nombre}' ya existe.")

    def cargar_playlist_seleccionada(self, playlist_id, playlist_nombre):
        self.playlist_actual_id = playlist_id
        self.playlist_actual_nombre = playlist_nombre

        self.limpiar_pantalla_principal()

        header_pl = ctk.CTkFrame(self.scroll_main, fg_color="#181818", corner_radius=10, height=80)
        header_pl.pack(fill="x", pady=(0, 15))

        lbl_tit = ctk.CTkLabel(header_pl, text=f"📂 Playlist: {playlist_nombre}", font=ctk.CTkFont(size=18, weight="bold"), text_color="#FFFFFF")
        lbl_tit.pack(side="left", padx=20, pady=15)

        lbl_dur = ctk.CTkLabel(header_pl, text="⏱ Calculando...", font=ctk.CTkFont(size=13, weight="bold"), text_color="#29ADDD")
        lbl_dur.pack(side="right", padx=20, pady=15)

        canciones = self.db.obtener_canciones_playlist(playlist_id)
        duracion_total = 0

        for id_deezer, titulo, artista, album, duracion_seg, link, pc_id, cover_url in canciones:
            duracion_total += duracion_seg
            track_dict = {
                'id': id_deezer, 'titulo': titulo, 'artista': artista,
                'album': album, 'duracion_seg': duracion_seg, 'link': link, 'cover_url': cover_url
            }
            self.renderizar_fila_cancion_spotify(track_dict, es_playlist=True, pc_id=pc_id)

        horas = duracion_total // 3600
        minutos = (duracion_total % 3600) // 60
        segundos = duracion_total % 60
        lbl_dur.configure(text=f"⏱ Duración Total: {horas:02d}:{minutos:02d}:{segundos:02d} ({len(canciones)} temas)")

    def eliminar_cancion_playlist(self, relacion_id):
        canciones = self.db.obtener_canciones_playlist(self.playlist_actual_id)
        cancion = next((fila for fila in canciones if fila[6] == relacion_id), None)
        if cancion is None:
            return

        track = {
            'id': cancion[0],
            'titulo': cancion[1],
            'artista': cancion[2],
            'album': cancion[3],
            'duracion_seg': cancion[4],
            'link': cancion[5],
            'cover_url': cancion[7],
        }
        self.db.eliminar_cancion_de_playlist(relacion_id)
        self.pila_historial.apilar({
            'tipo': 'eliminar',
            'playlist_id': self.playlist_actual_id,
            'relacion_id': relacion_id,
            'track': track,
        })
        self.cargar_playlist_seleccionada(self.playlist_actual_id, self.playlist_actual_nombre)

    def deshacer_accion(self):
        ultima_accion = self.pila_historial.ver_tope()
        if ultima_accion is None:
            messagebox.showinfo("Información", "No hay acciones recientes para deshacer.")
            return

        track = ultima_accion['track']
        pl_id = ultima_accion['playlist_id']

        if ultima_accion['tipo'] == 'agregar':
            self.db.eliminar_cancion_de_playlist(ultima_accion['relacion_id'])
            mensaje = f"Se quitó '{track['titulo']}' de la playlist."
        elif ultima_accion['tipo'] == 'eliminar':
            self.db.restaurar_cancion_en_playlist(
                pl_id, track, ultima_accion['relacion_id']
            )
            mensaje = f"Se restauró '{track['titulo']}' en la playlist."
        else:
            messagebox.showerror("Error", "No se reconoce la acción que se quiere deshacer.")
            return

        self.pila_historial.desapilar()

        if self.playlist_actual_id == pl_id:
            self.cargar_playlist_seleccionada(pl_id, self.playlist_actual_nombre)

        messagebox.showinfo("Deshecho", mensaje)

    def encolar_cancion(self, track_dict):
        self.cola_reproduccion.encolar(track_dict)
        self.lbl_fifo_status.configure(text=f"Cola de reproducción: {self.cola_reproduccion.tamano()} canciones")

    def reproducir_cancion(self, track_dict):
        threading.Thread(target=self.cargar_preview, args=(track_dict,), daemon=True).start()


if __name__ == "__main__":
    app = SpotifyAppCustom()
    app.mainloop()