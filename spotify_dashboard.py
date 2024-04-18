import streamlit as st
import plotly.express as px
import pandas as pd
import requests
from collections import Counter

@st.cache_data
def get_access_token(client_id: str, client_secret: str) -> str|None:
    """ Obtiene el token de acceso a partir del ID de cliente y su clave secreta
        para obtener acceso a la funcionalidad "no de usuario" de Spotify
    
    Argumentos:
        client_id: String con el ID de cliente
        client_secret: String con el secreto de cliente
    Devuelve:
        String con el token de acceso, o None si el servidor no lo proporciona
    """

    # Endpoint: https://accounts.spotify.com/api/token
    response = requests.post(url='https://accounts.spotify.com/api/token', 
                             headers={'Content-Type':'application/x-www-form-urlencoded'},
                             data=dict(grant_type='client_credentials', 
                                       client_id=client_id, 
                                       client_secret=client_secret))
    access_token = response.json().get('access_token', None)
    
    return access_token

def load_history_file(file) -> pd.DataFrame:
    """ Carga y preprocesa el JSON de historial de reproducciones de Spotify
    
    Argumentos:
        file: Fichero o ruta del fichero JSON que contiene los datos
    Devuelve:
        Dataframe con los datos preprocesados
    """
    print(type(file))
    print(file)
    # Carga del fichero en un dataframe
    rep_data = pd.read_json(file)
    # Se eliminan registros duplicados: canciones que figuran dos veces, terminando a la vez,
    # pero con duraciones de reproducción diferentes.
    # Identificamos todos los registros duplicados
    min_duracion = rep_data[rep_data.duplicated(subset=['endTime', 'artistName', 'trackName'], keep=False)]
    # Para cada duplicado, obtenemos el índice del de menor duración
    min_duracion = min_duracion.groupby(['artistName', 'trackName', 'endTime']).idxmin()
    # Descartamos los registros cuyo índice es uno de los registros en min_duracion
    rep_data = rep_data[~rep_data.msPlayed.isin(min_duracion.msPlayed)]
    rep_data = rep_data.reset_index(drop=True)

    # Agregamos una columna con la fecha de reproducción
    rep_data['playDate'] = pd.to_datetime(rep_data.endTime, format='ISO8601').values
    # Agregamos una columna con el tiempo de reproducción, en minutos
    rep_data['minPlayed'] = rep_data.msPlayed//60000

    return rep_data

@st.cache_data
def search_artist(artist_name: str) -> dict:
    """ Obtiene el ID de un artista a partir de su nombre

    Como el endpoint de búsqueda devuelve una lista de resultados relevantes,
    es necesario revisar los resultados para seleccionar el artista adecuado
    
    Argumentos:
        artist_name: Nombre del artista
    Devuelve:
        Diccionario con la respuesta en JSON del servidor
    """
    params = dict(q=f'artist:{artist_name}', 
                  type=['artist'],
                  market='ES',
                  limit=50)
    response = requests.get(url='https://api.spotify.com/v1/search', 
                            headers=header, 
                            params=params)
    # Recorremos la lista de artistas devueltos por la API
    for art in response.json()['artists']['items']:
        # Su nombre debe coincidir con el recibido como parámetro
        if art['name'] == artist_name:
            return art
    else: # Si no se encuentra, se devuelve un diccionario vacío
        return {}

client_id = None
client_secret = None
access_token = None

# st.set_page_config(layout="wide")

# Sidebar
with st.sidebar:
    with st.form(key='credentials'):
        st.markdown('Introduce tus credenciales de la API de Spotify para poder ejecutar consultas')
        client_id_input = st.text_input(label='Client ID', key='client_id', type='password')
        client_secret_input = st.text_input(label='Client Secret', key='client_secret', type='password')
        st.form_submit_button(label='Enviar')
    with st.container(border=1):
        st.markdown('Sube tu historial de reproducciones')
        file_uploader = st.file_uploader(label='Historial de reproducciones', type='json', key='history_file', 
                                        help='El fichero debería llamarse StreamingHistory_music_0.json')

client_id = client_id_input
client_secret = client_secret_input

if client_id and client_secret:
    access_token = get_access_token(client_id, client_secret)
    if access_token:
        header = {'Content-Type':'application/json',
                  'Authorization': 'Bearer '+ access_token}
        if file_uploader:
            data = load_history_file(file_uploader)

            # Metrics
            st.metric(label='Período', value=f"{data.playDate.min().date()} > {data.playDate.max().date()}")
            cols = st.columns([1,1,1,2])
            cols[0].metric(label='Canciones escuchadas', value=data.drop_duplicates(subset=['trackName', 'artistName']).shape[0])
            cols[1].metric(label='Artistas escuchados',  value=data.drop_duplicates(subset=['artistName']).shape[0])
            cols[2].metric(label='Horas escuchadas',  value=f'{data.minPlayed.sum()/60:.1f}h')
            st.markdown('# Canciones')

            st.markdown('## Top 10 canciones')
            top_songs = data.groupby(['artistName','trackName']).count().sort_values('msPlayed', ascending=True).tail(10).reset_index()
            top_songs['nombre_completo'] = top_songs['trackName'] + ' - ' + top_songs['artistName']
            st.plotly_chart(px.bar(top_songs, y='nombre_completo', x='msPlayed', orientation='h'))

            st.markdown('# Top 10 Artistas')

            st.markdown('## Por veces reproducido')
            top_artists = data.groupby(['artistName']).count().sort_values('msPlayed', ascending=False).head(10).reset_index()
            columns = st.columns(2)
            with st.spinner():
                for idx, row in top_artists.iterrows():    
                    with columns[idx//5]:
                        art = search_artist(row.artistName)
                        with st.container():
                            cols = st.columns([0.4,1])
                            try:
                                cols[0].image(art["images"][0]["url"])
                            except IndexError:
                                pass 
                            except KeyError: 
                                pass
                            cols[1].markdown(f'#### {idx+1}. {art["name"]}')
                            cols[1].markdown(f"{row.trackName} veces reproducido")
            
            st.markdown('---')
            st.markdown('## Por tiempo de reproducción')
            top_artists = data.drop('playDate', axis=1).groupby(['artistName']).sum().sort_values('msPlayed', ascending=False).head(10).reset_index()
            columns = st.columns(2)
            for idx, row in top_artists.iterrows():      
                with columns[idx//5]:          
                    art = search_artist(row.artistName)
                    with st.container():
                        cols = st.columns([0.4,1])
                        try:
                            cols[0].image(art["images"][0]["url"])
                        except IndexError:
                            pass 
                        except KeyError: 
                            pass
                        cols[1].markdown(f'#### {idx+1}. {art["name"]}')
                        cols[1].markdown(f"{row.msPlayed/60000:.0f} minutos de escucha")

            st.markdown('---')
            st.markdown('## Por canciones diferentes escuchadas')
            top_artists = data.drop('playDate', axis=1).drop_duplicates(subset=['trackName','artistName'])\
                              .groupby(['artistName']).count().sort_values('msPlayed', ascending=False).head(10).reset_index()
            columns = st.columns(2)
            for idx, row in top_artists.iterrows():      
                with columns[idx//5]:          
                    art = search_artist(row.artistName)
                    with st.container():
                        cols = st.columns([0.4,1])
                        try:
                            cols[0].image(art["images"][0]["url"])
                        except IndexError:
                            pass 
                        except KeyError: 
                            pass
                        cols[1].markdown(f'#### {idx+1}. {art["name"]}')
                        cols[1].markdown(f"{row.msPlayed:.0f} canciones distintas")

            st.markdown('---')
            st.markdown('## Géneros preferidos')
            st.markdown('De acuerdo a tus artistas preferidos, los géneros que más escuchas son:')
            generos = []
            for idx, row in top_artists.iterrows():
                art = search_artist(row.artistName)
                generos.extend(art['genres'])
            for k, v in Counter(generos).most_common(5):
                st.markdown(f'- {k} ({v})')

            st.markdown('# Estadísticas de uso (canciones)')

            graph = px.histogram(data, x='playDate')
            graph.update_traces(xbins_size=48*3600*1000)
            # graph.update_xaxes(showgrid=True, ticklabelmode="period", dtick="M1", tickformat="%b %Y")
            st.plotly_chart(graph)

            st.markdown('# Estadísticas de uso (tiempo)')
            
            graph = px.histogram(data, x='playDate', y='minPlayed')
            graph.update_traces(xbins_size=48*3600*1000)
            # graph.update_xaxes(showgrid=True, ticklabelmode="period", dtick="D1", tickformat="%b %Y")
            st.plotly_chart(graph)

        else:
            st.info('Sube el fichero de historial.', icon="ℹ️")
    else:
        st.warning('Credenciales incorrectas.', icon="ℹ️")
else:
    st.info('Introduce tus credenciales', icon="ℹ️")