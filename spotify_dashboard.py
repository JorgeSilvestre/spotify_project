import streamlit as st
import plotly.express as px
import pandas as pd
import requests
from collections import Counter

@st.cache_data
def get_access_token(client_id, client_secret):
    # Get access token
    response = requests.post(url='https://accounts.spotify.com/api/token', 
                            headers={'Content-Type':'application/x-www-form-urlencoded'},
                            data=dict(grant_type='client_credentials', 
                                      client_id=client_id, 
                                      client_secret=client_secret))
    access_token = response.json().get('access_token', None)
    
    return access_token

def load_history_file(file):
    rep_data = pd.read_json(file)
    min_duracion = rep_data[rep_data.duplicated(subset=['endTime', 'artistName', 'trackName'], keep=False)]\
                    .groupby(['artistName', 'trackName', 'endTime']).idxmin()
    rep_data = rep_data[~rep_data.msPlayed.isin(min_duracion.msPlayed)]
    rep_data = rep_data.reset_index(drop=True)

    rep_data['play_date'] = pd.to_datetime(rep_data.endTime, format='ISO8601').values
    rep_data['minPlayed'] = rep_data.msPlayed//60000

    return rep_data

@st.cache_data
def search_artist(artista: str):
    # Ojo, devuelve varios resultados. Seleccionamos siempre el primero por simplificar
    params = dict(q=f'artist:{artista}', 
                  type=['artist'],
                  market='ES',
                  limit=50)
    response = requests.get(url='https://api.spotify.com/v1/search', 
                            headers=header, 
                            params=params)
    # st.write(response.json())
    for art in response.json()['artists']['items']:
        if art['name'] == artista:
            return art
    else:
        return {}

    try:
        return response.json()['artists']['items'][0]
    except IndexError:
        return {}
    except KeyError:
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
            st.metric(label='Período', value=f"{data.play_date.min().date()} > {data.play_date.max().date()}")
            cols = st.columns([1,1,1,2])
            cols[0].metric(label='Canciones escuchadas', value=data.drop_duplicates(subset=['trackName', 'artistName']).shape[0])
            cols[1].metric(label='Artistas escuchados',  value=data.drop_duplicates(subset=['artistName']).shape[0])
            cols[2].metric(label='Horas escuchadas',  value=f'{data.minPlayed.sum()/60:.1f}h')
            st.markdown('# Canciones')

            st.markdown('## Top 10 canciones')
            top_songs = data.groupby(['artistName','trackName']).count().sort_values('msPlayed', ascending=True).tail(10).reset_index()
            top_songs['nombre_completo'] = top_songs['trackName'] + ' - ' + top_songs['artistName']
            st.plotly_chart(px.bar(top_songs, y='nombre_completo', x='msPlayed', orientation='h'))

            st.markdown('# Artistas')

            st.markdown('## Top 10 artistas (veces reproducido)')
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
                            cols[1].markdown(f'### {idx+1}. {art["name"]}')
                            cols[1].markdown(f"{row.trackName} veces reproducido")
            
            st.markdown('---')
            st.markdown('## Top 10 artistas (tiempo de reproducción)')
            top_artists = data.drop('play_date', axis=1).groupby(['artistName']).sum().sort_values('msPlayed', ascending=False).head(10).reset_index()
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
                        cols[1].markdown(f'### {idx+1}. {art["name"]}')
                        cols[1].markdown(f"{row.msPlayed/60000:.0f} minutos de escucha")

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

            graph = px.histogram(data, x='play_date')
            graph.update_traces(xbins_size="D1")
            graph.update_xaxes(showgrid=True, ticklabelmode="period", dtick="M1", tickformat="%b %Y")
            st.plotly_chart(graph)

            st.markdown('# Estadísticas de uso (tiempo)')
            
            graph = px.histogram(data, x='play_date', y='minPlayed')
            graph.update_traces(xbins_size="D1")
            graph.update_xaxes(showgrid=True, ticklabelmode="period", dtick="M1", tickformat="%b %Y")
            st.plotly_chart(graph)

        else:
            st.info('Sube el fichero de historial.', icon="ℹ️")
    else:
        st.warning('Credenciales incorrectas.', icon="ℹ️")
else:
    st.info('Introduce tus credenciales', icon="ℹ️")