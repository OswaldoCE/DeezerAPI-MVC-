import sqlite3

# ==========================================
# ESTRUCTURAS DE DATOS (FIFO Y LIFO)
# ==========================================

class ColaFIFO:
    """Cola de reproducción (First-In, First-Out)"""
    def __init__(self):
        self._items = []

    def encolar(self, item):
        self._items.append(item)

    def desencolar(self):
        return self._items.pop(0) if not self.esta_vacia() else None

    def esta_vacia(self):
        return len(self._items) == 0

    def tamano(self):
        return len(self._items)

    def obtener_todas(self):
        """Retorna una copia de la lista de canciones en cola"""
        return list(self._items)


class PilaLIFO:
    """Pila de historial/deshacer (Last-In, First-Out)"""
    def __init__(self):
        self._items = []

    def apilar(self, item):
        self._items.append(item)

    def desapilar(self):
        return self._items.pop() if not self.esta_vacia() else None

    def ver_tope(self):
        return self._items[-1] if not self.esta_vacia() else None

    def esta_vacia(self):
        return len(self._items) == 0


# ==========================================
# GESTOR DE BASE DE DATOS (SQLITE)
# ==========================================

class BaseDatos:
    def __init__(self, db_name="deezer_spotify.db"):
        self.db_name = db_name
        self.crear_tablas()

    def obtener_conexion(self):
        return sqlite3.connect(self.db_name)

    def crear_tablas(self):
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL UNIQUE,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS canciones (
                    id_deezer INTEGER PRIMARY KEY,
                    titulo TEXT NOT NULL,
                    artista TEXT NOT NULL,
                    album TEXT NOT NULL,
                    duracion_seg INTEGER NOT NULL,
                    link TEXT,
                    cover_url TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlist_canciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    cancion_id_deezer INTEGER NOT NULL,
                    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
                    FOREIGN KEY (cancion_id_deezer) REFERENCES canciones (id_deezer)
                )
            """)
            conn.commit()

    def crear_playlist(self, nombre):
        try:
            with self.obtener_conexion() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO playlists (nombre) VALUES (?)", (nombre,))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def obtener_playlists(self):
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre FROM playlists ORDER BY nombre ASC")
            return cursor.fetchall()

    def guardar_cancion(self, track_dict):
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO canciones (id_deezer, titulo, artista, album, duracion_seg, link, cover_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                track_dict['id'],
                track_dict['titulo'],
                track_dict['artista'],
                track_dict['album'],
                track_dict['duracion_seg'],
                track_dict['link'],
                track_dict.get('cover_url', '')
            ))
            conn.commit()

    def agregar_cancion_a_playlist(self, playlist_id, track_dict):
        self.guardar_cancion(track_dict)
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO playlist_canciones (playlist_id, cancion_id_deezer)
                VALUES (?, ?)
            """, (playlist_id, track_dict['id']))
            conn.commit()
            return cursor.lastrowid

    def restaurar_cancion_en_playlist(self, playlist_id, track_dict, relacion_id):
        self.guardar_cancion(track_dict)
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO playlist_canciones (id, playlist_id, cancion_id_deezer)
                VALUES (?, ?, ?)
            """, (relacion_id, playlist_id, track_dict['id']))
            conn.commit()

    def obtener_canciones_playlist(self, playlist_id):
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id_deezer, c.titulo, c.artista, c.album, c.duracion_seg, c.link, pc.id, c.cover_url
                FROM playlist_canciones pc
                JOIN canciones c ON pc.cancion_id_deezer = c.id_deezer
                WHERE pc.playlist_id = ?
                ORDER BY pc.id ASC
            """, (playlist_id,))
            return cursor.fetchall()

    def eliminar_cancion_de_playlist(self, relacion_id):
        with self.obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playlist_canciones WHERE id = ?", (relacion_id,))
            conn.commit()