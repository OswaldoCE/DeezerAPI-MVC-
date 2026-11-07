import deezer
import requests

class DeezerService:
    def __init__(self):
        self.client = deezer.Client()

    def formatear_track(self, track):
        """Convierte un objeto Track de Deezer a un diccionario normalizado"""
        try:
            art = track.artist.name if hasattr(track, 'artist') and track.artist else "Desconocido"
            alb = track.album.title if hasattr(track, 'album') and track.album else "Single"
            cover = track.album.cover_medium if hasattr(track, 'album') and track.album else ""
            return {
                'id': getattr(track, 'id', 0),
                'titulo': getattr(track, 'title', 'Desconocido'),
                'artista': art,
                'album': alb,
                'duracion_seg': getattr(track, 'duration', 0),
                'link': getattr(track, 'link', ''),
                'cover_url': cover,
                'preview': getattr(track, 'preview', '')
            }
        except Exception:
            return None

    def obtener_top_tracks_y_artistas(self, limit=10):
        response_tracks = requests.get(
            "https://api.deezer.com/chart/0/tracks",
            params={"limit": limit},
            timeout=10
        )
        response_tracks.raise_for_status()

        response_artists = requests.get(
            "https://api.deezer.com/chart/0/artists",
            params={"limit": limit},
            timeout=10
        )
        response_artists.raise_for_status()

        chart_tracks = []
        for track in response_tracks.json().get("data", []):
            album = track.get("album") or {}
            artist = track.get("artist") or {}
            chart_tracks.append({
                'id': track.get('id', 0),
                'titulo': track.get('title', 'Desconocido'),
                'artista': artist.get('name', 'Desconocido'),
                'album': album.get('title', 'Single'),
                'duracion_seg': track.get('duration', 0),
                'link': track.get('link', ''),
                'cover_url': album.get('cover_medium', ''),
                'preview': track.get('preview', '')
            })

        chart_artists = []
        for artist in response_artists.json().get("data", []):
            chart_artists.append({
                'id': artist.get('id', 0),
                'nombre': artist.get('name', 'Desconocido'),
                'picture_url': artist.get('picture_medium', '')
            })

        beatles_response = requests.get(
            "https://api.deezer.com/search/artist",
            params={"q": "The Beatles", "limit": 1},
            timeout=10
        )
        beatles_response.raise_for_status()
        beatles = beatles_response.json().get("data", [])
        if beatles:
            beatles_artist = beatles[0]
            chart_artists.append({
                'id': beatles_artist.get('id', 0),
                'nombre': beatles_artist.get('name', 'The Beatles'),
                'picture_url': beatles_artist.get('picture_medium', '')
            })

        return chart_tracks, chart_artists

    def buscar_artista_o_canciones(self, query):
        tracks_raw = self.client.search(query)
        items = []
        for idx, t in enumerate(tracks_raw):
            if idx >= 20:
                break
            formatted = self.formatear_track(t)
            if formatted:
                items.append(formatted)

        artistas = self.client.search_artists(query)
        artista = None
        if artistas and len(artistas) > 0:
            artista_obj = artistas[0]
            artista = {
                'id': getattr(artista_obj, 'id', 0),
                'nombre': getattr(artista_obj, 'name', query),
                'picture_url': getattr(artista_obj, 'picture_medium', '')
            }

        if items:
            return {'tipo': 'mixto', 'items': items, 'artista': artista}

        if artista:
            return {'tipo': 'artista', **artista}

        return {'tipo': 'canciones', 'items': []}

    def obtener_detalle_artista(self, artist_id):
        artist_obj = self.client.get_artist(artist_id)
        top_tracks_raw = artist_obj.get_top()
        top_tracks = []
        for idx, t in enumerate(top_tracks_raw):
            if idx >= 15:
                break
            formatted = self.formatear_track(t)
            if formatted:
                top_tracks.append(formatted)
        picture_url = getattr(artist_obj, 'picture_medium', '')
        return picture_url, top_tracks