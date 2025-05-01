
import requests
import pandas as pd
import traceback
import time
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Configuration
YOUTUBE_API_KEY = 'api_key'
YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'
YOUTUBE_VIDEO_URL = 'https://www.googleapis.com/youtube/v3/videos'

# Search YouTube for videos matching song and artist
def search_youtube_videos(session, song_title, artist_name=None):
    try:
        query = f"{song_title}"
        if artist_name and not pd.isna(artist_name) and str(artist_name).strip() != '':
            query += f" {artist_name}"

        logging.info(f"Querying YouTube: {query}")
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': 50,
            'key': YOUTUBE_API_KEY,
            'regionCode': 'ID'  # Filter to Indonesia if needed
        }
        response = session.get(YOUTUBE_SEARCH_URL, params=params)
        logging.debug(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            logging.error(f"YouTube API request failed: {response.text}")
            return []

        data = response.json()
        items = data.get('items', [])
        if not items:
            logging.warning("No YouTube results found.")
            return []

        results = []
        video_ids = [item['id']['videoId'] for item in items if 'id' in item and 'videoId' in item['id']]

        if not video_ids:
            return results

        # Get detailed metadata
        details_params = {
            'part': 'snippet',
            'id': ','.join(video_ids),
            'key': YOUTUBE_API_KEY
        }
        details_response = session.get(YOUTUBE_VIDEO_URL, params=details_params)
        if details_response.status_code != 200:
            logging.error(f"Failed to fetch video details: {details_response.text}")
            return results

        details_data = details_response.json()
        for video in details_data.get('items', []):
            video_info = {
                'Video ID': video.get('id', ''),
                'Channel ID': video.get('snippet', {}).get('channelId', ''),
                'Song Title': song_title,
                'Artist': artist_name if artist_name else '',
                'Video Title': video.get('snippet', {}).get('title', '')
            }
            logging.info(f"Extracted Video Info: {video_info}")
            results.append(video_info)
            
        time.sleep(2)

        return results
    except Exception as e:
        logging.error(f"Exception during YouTube search: {e}")
        traceback.print_exc()
        return []

# Main: Search YouTube videos from CSV and save formatted output
def search_youtube_from_csv(csv_file, output_file):
    logging.info(f"Reading CSV: {csv_file}")
    try:
        df = pd.read_csv(csv_file)
        logging.info(f"Loaded {len(df)} rows from CSV.")
    except Exception as e:
        logging.error("Failed to read CSV:", e)
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

            logging.info(f"Searching YouTube Row {idx}: {song_title} by {artist_name if not pd.isna(artist_name) and str(artist_name).strip() != '' else 'No artist provided'}")
            video_results = search_youtube_videos(session, song_title, artist_name)
            for video_info in video_results:
                video_info['Row'] = idx
                video_info['CODE'] = code_value
                results.append(video_info)

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
    search_youtube_from_csv('[DE TS] Song Catalog Data - Data.csv', 'youtube_video_results.parquet')
