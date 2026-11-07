# Capytacticos Music

Aplicacion de escritorio en Python para consultar contenido de Deezer, visualizar portadas y perfiles de artistas, reproducir previews de canciones y administrar playlists locales.

## Funciones principales

- Pantalla de Inicio con canciones del momento obtenidas desde Deezer.
- Seccion de artistas populares con fotografias de la API.
- Artista de prueba incluido: The Beatles.
- Busqueda de canciones por nombre.
- Busqueda de artistas con perfil y canciones relacionadas.
- Vista de perfil con fotografia del artista y sus canciones populares.
- Portadas de albums y fotografias cargadas desde URLs de Deezer.
- Reproduccion de previews de audio de Deezer.
- Boton para pausar y reanudar el preview.
- Indicador de la cancion que se esta reproduciendo.
- Cola de reproduccion FIFO.
- Creacion de playlists locales.
- Guardado de canciones en una o varias playlists.
- Eliminacion de canciones de playlists.
- Deshacer la ultima accion de guardado.
- Persistencia local mediante SQLite.
- Interfaz grafica oscura con elementos azules.

## Requisitos

- Python 3.10 o superior.
- Conexion a Internet para consultar Deezer, cargar imagenes y reproducir previews.
- Salida de audio disponible para reproducir previews.

## Instalacion

Desde esta carpeta, instala las dependencias:

```powershell
pip install customtkinter pillow requests pygame deezer-python
```

En algunos entornos el paquete de Deezer puede instalarse como `deezer`:

```powershell
pip install deezer
```

## Ejecucion

Abre PowerShell en la carpeta que contiene `ui_deezer.py` y ejecuta:

```powershell
python ui_deezer.py
```

Ruta esperada del proyecto:

```text
Deezer(MVC)/
    backend.py
    deezer_service.py
    ui_deezer.py
    deezer_spotify.db
    README.md
```

## Uso

### Inicio

Al iniciar la aplicacion se consultan los endpoints de ranking de Deezer para cargar:

- Canciones del momento.
- Artistas populares.
- The Beatles como artista de referencia.

Cada tarjeta de cancion muestra su portada, titulo y artista. Cada tarjeta de artista muestra su fotografia y permite abrir su perfil.

### Busqueda

Escribe una cancion o un artista en el buscador y pulsa `Buscar`.

- Si existen canciones, se muestran las canciones encontradas y un resumen del artista coincidente.
- El boton `Ver perfil` abre la vista completa del artista.
- Si no hay canciones pero existe un artista coincidente, se abre directamente su perfil.
- Las filas de canciones incluyen portada, reproduccion, cola y playlist.

### Previews

El boton azul de reproduccion descarga el campo `preview` de Deezer y reproduce un fragmento de audio con `pygame`.

- `Pausar` detiene temporalmente el preview.
- `Reanudar` continua el preview pausado.
- El preview se descarga en segundo plano para evitar bloquear la interfaz.
- Los previews son fragmentos proporcionados por Deezer, no canciones completas.

### Playlists

1. Escribe un nombre en `Nueva Playlist...`.
2. Pulsa `+` para crearla.
3. En una cancion, pulsa `Playlist`.
4. Selecciona una o varias playlists.
5. Confirma con `Guardar en Playlist(s)`.

Las playlists y las canciones guardadas se almacenan en `deezer_spotify.db`.

### Cola de reproduccion

El boton `+ Cola` agrega una cancion a la cola FIFO. `Ver cola` muestra las canciones en el orden en que fueron agregadas y calcula la duracion total.

## Estructura del proyecto

### `ui_deezer.py`

Contiene la interfaz grafica basada en CustomTkinter y la clase principal `SpotifyAppCustom`.

Responsabilidades:

- Crear la ventana, sidebar, buscador, contenido y reproductor.
- Renderizar tarjetas, filas de canciones y perfiles.
- Descargar imagenes sin bloquear la interfaz.
- Coordinar la reproduccion y pausa de previews.
- Administrar playlists y cola de reproduccion.

### `deezer_service.py`

Contiene `DeezerService`, que centraliza la comunicacion con Deezer.

Usa:

- `https://api.deezer.com/chart/0/tracks` para canciones del momento.
- `https://api.deezer.com/chart/0/artists` para artistas populares.
- `https://api.deezer.com/search/artist` para localizar artistas.
- La libreria `deezer` para busquedas y detalles de artistas.

Normaliza los datos de las canciones en diccionarios con estos campos:

```text
id
titulo
 artista
 album
 duracion_seg
 link
 cover_url
 preview
```

### `backend.py`

Contiene la logica local de datos:

- `ColaFIFO`: cola de reproduccion.
- `PilaLIFO`: historial usado para deshacer acciones.
- `BaseDatos`: creacion y operaciones de SQLite.

### `deezer_spotify.db`

Base de datos SQLite creada automaticamente. Guarda:

- Playlists.
- Canciones guardadas.
- Relaciones entre playlists y canciones.
- Portadas de las canciones guardadas.

## Flujo general

```text
Interfaz CustomTkinter
        |
        v
DeezerService ---> API de Deezer
        |
        v
Datos normalizados
        |
        +--> Tarjetas y perfiles
        +--> Imagenes remotas
        +--> Previews con pygame
        +--> Playlists en SQLite
```

## Notas y limitaciones

- Se requiere Internet para el contenido remoto.
- Deezer puede cambiar los resultados del ranking con el tiempo.
- Los previews tienen una duracion limitada y dependen de la disponibilidad de Deezer.
- Las playlists son locales y no se sincronizan con una cuenta de Deezer.
- La aplicacion reproduce previews, no audio completo bajo demanda.
- La base de datos se crea en la carpeta actual desde la que se ejecuta Python.
- El nombre de la clase principal conserva `SpotifyAppCustom` por compatibilidad con el codigo original, aunque la aplicacion usa Deezer.

## Tecnologias

- Python
- CustomTkinter
- Tkinter
- Requests
- Pillow
- Pygame
- Deezer API
- SQLite
