import requests
import pandas as pd
import traceback
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Configuration
SPOTIFY_CLIENT_ID = 'client_id'
SPOTIFY_CLIENT_SECRET = 'secret_key' #secret key
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_SEARCH_URL = 'https://api.spotify.com/v1/search'
# Get Spotify Access Token
def get_spotify_token():
    logging.info("Requesting Spotify access token...")
    try:
        response = requests.post(
            SPOTIFY_TOKEN_URL,
            data={'grant_type': 'client_credentials'},
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        )
        response.raise_for_status()
        token = response.json()['access_token']
        logging.info("Access token retrieved successfully.")
        return token
    except Exception as e:
        logging.error(f"Failed to get access token: {e}")
        traceback.print_exc()
        return None

# Build search query based on availability of artist
def build_query(artist_name, song_title):
    if artist_name and not pd.isna(artist_name) and str(artist_name).strip() != '':
        query = f'artist:{artist_name} track:{song_title}'
    else:
        query = f'track:{song_title}'
    return query

def search_by_song(session, access_token, song_title, artist_name=None):
    try:
        query = build_query(artist_name, song_title)
        logging.info(f"Querying: {query}")
        params = {
            'q': query,
            'type': 'track',
            'market': 'ID',
            'limit': 50
        }
        headers = {'Authorization': f'Bearer {access_token}'}
        results = []
        seen_ids = set()
        next_url = SPOTIFY_SEARCH_URL

        while next_url:
            response = session.get(next_url, headers=headers, params=params if next_url == SPOTIFY_SEARCH_URL else None)
            logging.debug(f"Status Code: {response.status_code}")
            if response.status_code != 200:
                logging.error(f"API request failed: {response.text}")
                break

            data = response.json()
            tracks_data = data.get('tracks')
            if not isinstance(tracks_data, dict):
                logging.error("Unexpected data format: 'tracks' is missing or not a dict.")
                break

            total_found = tracks_data.get('total', 0)
            logging.info(f"Total results found: {total_found}")

            items = tracks_data.get('items', [])
            if not items:
                logging.warning("No track results in this page.")

            for track in items:
                try:
                    spotify_id = track.get('id', '')
                    isrc = track.get('external_ids', {}).get('isrc', '')
                    unique_key = spotify_id or isrc
                    if unique_key in seen_ids:
                        logging.info(f"Skipping duplicate track with ID/ISRC: {unique_key}")
                        continue
                    seen_ids.add(unique_key)

                    track_info = {
                        'track_name': track.get('name', ''),
                        'spotify_id': spotify_id,
                        'artist': track.get('artists', [{}])[0].get('name', ''),
                        'album': track.get('album', {}).get('name', ''),
                        'isrc': isrc,
                        'album_release_date': track.get('album', {}).get('release_date', '')
                    }
                    logging.info(f"Extracted Track Info: {track_info}")
                    results.append(track_info)
                except Exception as inner_e:
                    logging.error(f"Error parsing track item: {inner_e}")
                    traceback.print_exc()

            next_url = tracks_data.get('next')

        return results
    except Exception as e:
        logging.error(f"Exception during search: {e}")
        traceback.print_exc()
        return []

# Main: Search all songs from CSV and save formatted output
def search_songs_from_csv(csv_file, output_file):
    logging.info(f"Reading CSV: {csv_file}")
    try:
        df = pd.read_csv(csv_file)
        logging.info(f"Loaded {len(df)} rows from CSV.")
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        return

    token = get_spotify_token()
    if not token:
        logging.error("Cannot proceed without access token.")
        return

    results = []
    with requests.Session() as session:
        for idx, row in df.iterrows():
            song_title = row.get('SONG TITLE')
            artist_name = row.get('ORIGINAL ARTIST')
            code_value = row.get('CODE')
            if pd.isna(song_title):
                logging.warning(f"Row {idx} missing song title, skipping.")
                continue
            logging.info(f"Searching Row {idx}: {song_title} by {artist_name if not pd.isna(artist_name) and str(artist_name).strip() != '' else 'No artist provided'}")
            track_results = search_by_song(session, token, song_title, artist_name)
            for track_info in track_results:
                track_info['row'] = idx
                track_info['code'] = code_value
                results.append(track_info)

    if results:
        out_df = pd.DataFrame(results)
        logging.info(f"Saving {len(results)} results to Parquet: {output_file}")
        out_df.columns = [col.replace(' ', '_').lower() for col in out_df.columns]
        try:
            out_df.to_parquet(output_file, index=False, engine='pyarrow')
            logging.info("Saved successfully.")
        except Exception as e:
            logging.error(f"Failed to save Parquet file: {e}. Ensure 'pyarrow' or 'fastparquet' is installed.")
    else:
        logging.warning("No results to save.")

if __name__ == '__main__':
    search_songs_from_csv('[DE TS] Song Catalog Data - Data.csv', 'spotify_track_results.parquet')

