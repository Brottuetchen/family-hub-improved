#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Weekly Media Newsletter Generator
Fetches trending and recent movies/TV shows from TMDB, uses Ollama AI for recommendations,
and generates HTML newsletter email
Enhanced version with direct TMDB API integration, Ollama AI, Plex statistics, and Trilium integration
"""
import requests
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# Configure logging (will be initialized after LOG_DIR is created)
logger = logging.getLogger(__name__)

# API Configuration
TMDB_API_KEY = "256a4fc4dad333995b66da5d11cc2a55"
TMDB_BEARER_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyNTZhNGZjNGRhZDMzMzk5NWI2NmRhNWQxMWNjMmE1NSIsIm5iZiI6MTc2MDE0NjA2MS40NzgwMDAyLCJzdWIiOiI2OGU5YjI4ZDM4Y2JmMDE3Y2I3ODY2OTMiLCJzY29wZXMiOlsiYXBpX3JlYWQiXSwidmVyc2lvbiI6MX0.924dQJGBH6bFgTDpBvGDlDWY2_do5G01SSgVQ65AygQ"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

OLLAMA_URL = "http://192.168.188.199:11434/api/generate"
OLLAMA_MODEL = "qwen3-coder:30b"

# Overseerr Configuration
OVERSEERR_URL = "http://192.168.188.79:5055"
OVERSEERR_API_KEY = "MTc1ODU1NDgxMzY0NGE3MWZjZDY4LWJhMzItNGI5NC1hNDNiLWEyZWViODE4MmE2OQ=="

# Plex Configuration
PLEX_URL = "http://192.168.188.7:32400"
PLEX_TOKEN = "oe1a9iRoLZktgJEAXFvo"

# Trilium Configuration
TRILIUM_URL = "http://192.168.188.62:8080"
TRILIUM_TOKEN = "y5fYTYpJ8pIX_RQ4/8i5F4dZSbe7/N2zEkSeu1CQBHMLpO4zgDby8WHA="

# NAS Storage configuration
REPORT_DIR = Path('/opt/newsletter-output')
LOG_DIR = Path('/opt/newsletter-output/logs')

# Request timeout
REQUEST_TIMEOUT = 30


def setup_logging():
    """Setup logging with NAS log directory"""
    try:
        # Create log directory if it doesn't exist
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Configure logging with NAS path
        log_file = LOG_DIR / "weekly_newsletter.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(str(log_file), encoding='utf-8')
            ],
            force=True  # Force reconfiguration if already configured
        )
        logger.info(f"Logging initialized. Log file: {log_file}")
    except Exception as e:
        # Fallback to local logging if NAS is not accessible
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('weekly_newsletter.log', encoding='utf-8')
            ],
            force=True
        )
        logger.warning(f"Could not setup NAS logging, using local file: {e}")


@dataclass
class MediaItem:
    """Data class for media items from TMDB"""
    title: str
    tmdb_id: int
    rating: float
    overview: str
    release_date: str
    poster_url: Optional[str]
    trailer_url: Optional[str]
    genres: List[str]
    vote_count: int
    media_type: str  # 'movie' or 'tv'
    overseerr_status: str = "not_available"  # "available", "requested", "not_available"
    overseerr_url: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'title': self.title,
            'tmdb_id': self.tmdb_id,
            'rating': self.rating,
            'overview': self.overview,
            'release_date': self.release_date,
            'poster_url': self.poster_url,
            'trailer_url': self.trailer_url,
            'genres': self.genres,
            'vote_count': self.vote_count,
            'media_type': self.media_type,
            'overseerr_status': self.overseerr_status,
            'overseerr_url': self.overseerr_url
        }


def get_tmdb_headers() -> Dict:
    """Get TMDB API headers"""
    return {
        "Authorization": f"Bearer {TMDB_BEARER_TOKEN}",
        "accept": "application/json"
    }


def check_overseerr_availability(tmdb_id: int, media_type: str) -> Dict:
    """
    Check if movie/TV show is available or requested in Overseerr

    Args:
        tmdb_id: TMDB ID of the media
        media_type: 'movie' or 'tv'

    Returns:
        Dict with keys: available (bool), requested (bool), status (str)
    """
    headers = {
        "X-Api-Key": OVERSEERR_API_KEY,
        "accept": "application/json"
    }

    endpoint = "movie" if media_type == "movie" else "tv"
    url = f"{OVERSEERR_URL}/api/v1/{endpoint}/{tmdb_id}"

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        # If 404, media is not in Overseerr at all
        if response.status_code == 404:
            return {
                "available": False,
                "requested": False,
                "status": "not_available"
            }

        response.raise_for_status()
        data = response.json()

        # Check media info from Overseerr
        # mediaInfo exists and has status field
        media_info = data.get('mediaInfo', {})

        # Status codes: 1=Unknown, 2=Pending, 3=Processing, 4=Partially Available, 5=Available
        status_code = media_info.get('status', 1)

        # Check if available (status 5)
        available = status_code == 5

        # Check if requested (status 2, 3, or 4)
        requested = status_code in [2, 3, 4]

        if available:
            return {
                "available": True,
                "requested": False,
                "status": "available"
            }
        elif requested:
            return {
                "available": False,
                "requested": True,
                "status": "requested"
            }
        else:
            return {
                "available": False,
                "requested": False,
                "status": "not_available"
            }

    except requests.exceptions.RequestException as e:
        logger.warning(f"Error checking Overseerr availability for {media_type} ID {tmdb_id}: {e}")
        # Default to not_available on error
        return {
            "available": False,
            "requested": False,
            "status": "not_available"
        }
    except Exception as e:
        logger.error(f"Unexpected error checking Overseerr for {media_type} ID {tmdb_id}: {e}")
        return {
            "available": False,
            "requested": False,
            "status": "not_available"
        }


def get_plex_watch_stats() -> Dict:
    """
    Fetch Plex watch history from last 7 days

    Returns:
        Dict with keys: movies_watched, episodes_watched, total_hours, success
    """
    default_stats = {
        "movies_watched": 0,
        "episodes_watched": 0,
        "total_hours": 0.0,
        "success": False
    }

    try:
        logger.info("Fetching Plex watch statistics from last 7 days...")

        # Calculate timestamp for 7 days ago (Unix timestamp)
        seven_days_ago = int((datetime.now() - timedelta(days=7)).timestamp())
        logger.info(f"Seven days ago timestamp: {seven_days_ago} ({datetime.fromtimestamp(seven_days_ago)})")

        # Plex API endpoint for watch history
        url = f"{PLEX_URL}/status/sessions/history/all"

        headers = {
            "Accept": "application/json"
        }

        params = {
            "X-Plex-Token": PLEX_TOKEN
        }

        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        data = response.json()

        # Parse the response
        metadata = data.get('MediaContainer', {}).get('Metadata', [])

        logger.info(f"Total items in Plex history: {len(metadata)}")

        movies_count = 0
        episodes_count = 0
        total_duration_ms = 0
        filtered_out_count = 0

        # Log first 3 items with ALL fields to debug structure
        for idx, item in enumerate(metadata[:3]):
            logger.info(f"DEBUG - Sample item {idx+1} ALL FIELDS: {json.dumps(item, indent=2, default=str)}")

        for idx, item in enumerate(metadata):
            # Extract all relevant fields
            viewed_at = item.get('viewedAt', 0)
            last_viewed_at = item.get('lastViewedAt', 0)
            media_type = item.get('type', '')
            title = item.get('title', 'Unknown')
            duration = item.get('duration', 0)  # Duration in milliseconds (often 0 in history)
            view_offset = item.get('viewOffset', 0)
            rating_key = item.get('ratingKey', '')

            # Log EVERY item (first 10 in detail, then just counts)
            if idx < 10:
                logger.info(f"Item {idx+1}: type='{media_type}', title='{title}', "
                           f"viewedAt={viewed_at}, lastViewedAt={last_viewed_at}, "
                           f"duration={duration}ms, ratingKey={rating_key}")

            # Filter: only include items viewed AFTER seven_days_ago (more recent)
            # Try both viewedAt and lastViewedAt
            actual_viewed_at = max(viewed_at, last_viewed_at)

            if actual_viewed_at < seven_days_ago:
                filtered_out_count += 1
                if idx < 10:
                    logger.info(f"  -> FILTERED OUT (viewed_at {actual_viewed_at} < {seven_days_ago})")
                continue

            if idx < 10:
                logger.info(f"  -> INCLUDED (viewed_at {actual_viewed_at} >= {seven_days_ago})")

            # Fetch full metadata to get accurate duration
            # The history endpoint often returns duration=0, so we need to fetch from metadata API
            if rating_key:
                try:
                    metadata_url = f"{PLEX_URL}/library/metadata/{rating_key}"
                    metadata_params = {"X-Plex-Token": PLEX_TOKEN}
                    metadata_headers = {"Accept": "application/json"}

                    if idx < 3:
                        logger.info(f"  -> Fetching metadata from: {metadata_url}")

                    metadata_response = requests.get(
                        metadata_url,
                        params=metadata_params,
                        headers=metadata_headers,
                        timeout=REQUEST_TIMEOUT
                    )

                    if metadata_response.ok:
                        metadata_json = metadata_response.json()
                        metadata_item = metadata_json.get('MediaContainer', {}).get('Metadata', [{}])[0]
                        duration = metadata_item.get('duration', 0)

                        if idx < 3:
                            logger.info(f"  -> Metadata fetched: duration={duration}ms ({duration/1000/60:.1f} min)")
                    else:
                        logger.warning(f"Failed to fetch metadata for ratingKey {rating_key}: HTTP {metadata_response.status_code}")
                        duration = 0

                except Exception as e:
                    logger.warning(f"Error fetching metadata for '{title}' (ratingKey={rating_key}): {e}")
                    duration = 0
            else:
                logger.warning(f"No ratingKey for item '{title}', cannot fetch metadata")
                duration = 0

            if media_type == 'movie':
                movies_count += 1
                total_duration_ms += duration
                logger.info(f"  -> Movie counted: '{title}' - duration: {duration}ms ({duration/1000/60:.1f} min)")
            elif media_type == 'episode':
                episodes_count += 1
                total_duration_ms += duration
                logger.info(f"  -> Episode counted: '{title}' - duration: {duration}ms ({duration/1000/60:.1f} min)")
            else:
                logger.debug(f"  -> Unknown type '{media_type}' ignored")

        # Convert milliseconds to hours
        total_hours = total_duration_ms / (1000 * 60 * 60)

        stats = {
            "movies_watched": movies_count,
            "episodes_watched": episodes_count,
            "total_hours": round(total_hours, 1),
            "success": True
        }

        logger.info(f"FINAL Plex stats: {movies_count} movies, {episodes_count} episodes")
        logger.info(f"FINAL Duration: {total_duration_ms}ms = {total_duration_ms/1000:.0f}s = {total_duration_ms/1000/60:.1f}min = {total_hours:.1f} hours")
        logger.info(f"Items filtered out (too old): {filtered_out_count}")
        return stats

    except requests.exceptions.RequestException as e:
        logger.warning(f"Error fetching Plex statistics (server may be down): {e}")
        return default_stats
    except Exception as e:
        logger.error(f"Unexpected error fetching Plex statistics: {e}")
        logger.exception("Full traceback:")
        return default_stats


def update_trilium_knowledge_base(newsletter_data: Dict) -> bool:
    """
    Update Trilium knowledge base with newsletter summary

    Args:
        newsletter_data: Dict containing newsletter information
            - selected_movies: List of movie recommendations
            - selected_shows: List of show recommendations
            - plex_stats: Dict with Plex statistics
            - html_filepath: Path to generated HTML file
            - date: Newsletter date

    Returns:
        bool: Success status
    """
    try:
        logger.info("Updating Trilium knowledge base...")

        headers = {
            "Authorization": TRILIUM_TOKEN,
            "Content-Type": "application/json"
        }

        # Step 1: Find or create "Weekly Media Newsletter Archive" note
        archive_note_title = "Weekly Media Newsletter Archive"
        search_url = f"{TRILIUM_URL}/etapi/notes"

        # Search for existing archive note
        search_params = {"search": archive_note_title}
        response = requests.get(search_url, headers=headers, params=search_params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        search_results = response.json()

        # Check if archive note exists
        archive_note_id = None
        for note in search_results.get('results', []):
            if note.get('title') == archive_note_title:
                archive_note_id = note.get('noteId')
                logger.info(f"Found existing archive note: {archive_note_id}")
                break

        # If not found, create archive note
        if not archive_note_id:
            logger.info("Creating new archive note...")
            create_url = f"{TRILIUM_URL}/etapi/create-note"

            archive_payload = {
                "parentNoteId": "root",
                "title": archive_note_title,
                "type": "text",
                "content": "<p>Archiv aller wöchentlichen Media Newsletter</p>"
            }

            response = requests.post(create_url, headers=headers, json=archive_payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            archive_result = response.json()
            archive_note_id = archive_result.get('note', {}).get('noteId')
            logger.info(f"Created archive note: {archive_note_id}")

        if not archive_note_id:
            logger.error("Failed to get or create archive note")
            return False

        # Step 2: Create child note with newsletter summary
        date_str = newsletter_data.get('date', datetime.now().strftime("%Y-%m-%d"))
        note_title = f"Newsletter - {date_str}"

        # Build HTML content for the note
        content_parts = [
            f"<h1>Weekly Media Newsletter - {date_str}</h1>",
            "<h2>Top 5 Filme</h2>",
            "<ul>"
        ]

        for movie in newsletter_data.get('selected_movies', [])[:5]:
            title = movie.get('title', 'Unknown')
            reason = movie.get('reason', '')
            # Find movie details from all_movies
            movie_rating = 'N/A'
            for m in newsletter_data.get('all_movies', []):
                if m.title == title:
                    movie_rating = f"{m.rating:.1f}/10"
                    break
            content_parts.append(f"<li><strong>{title}</strong> ({movie_rating}) - {reason}</li>")

        content_parts.extend([
            "</ul>",
            "<h2>Top 5 Serien</h2>",
            "<ul>"
        ])

        for show in newsletter_data.get('selected_shows', [])[:5]:
            title = show.get('title', 'Unknown')
            reason = show.get('reason', '')
            # Find show details from all_shows
            show_rating = 'N/A'
            for s in newsletter_data.get('all_shows', []):
                if s.title == title:
                    show_rating = f"{s.rating:.1f}/10"
                    break
            content_parts.append(f"<li><strong>{title}</strong> ({show_rating}) - {reason}</li>")

        content_parts.append("</ul>")

        # Add Plex statistics if available
        plex_stats = newsletter_data.get('plex_stats', {})
        if plex_stats.get('success', False):
            content_parts.extend([
                "<h2>Plex Statistiken (letzte 7 Tage)</h2>",
                "<ul>",
                f"<li>Filme geschaut: {plex_stats.get('movies_watched', 0)}</li>",
                f"<li>Episoden geschaut: {plex_stats.get('episodes_watched', 0)}</li>",
                f"<li>Stunden gestreamt: {plex_stats.get('total_hours', 0)}</li>",
                "</ul>"
            ])

        # Add link to HTML file
        html_filepath = newsletter_data.get('html_filepath', '')
        if html_filepath:
            content_parts.append(f"<p><strong>HTML Report:</strong> <code>{html_filepath}</code></p>")

        note_content = "\n".join(content_parts)

        # Create the child note
        create_url = f"{TRILIUM_URL}/etapi/create-note"

        note_payload = {
            "parentNoteId": archive_note_id,
            "title": note_title,
            "type": "text",
            "content": note_content
        }

        response = requests.post(create_url, headers=headers, json=note_payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        result = response.json()
        new_note_id = result.get('note', {}).get('noteId')

        logger.info(f"Created newsletter note in Trilium: {new_note_id}")
        return True

    except requests.exceptions.RequestException as e:
        logger.warning(f"Error updating Trilium knowledge base (server may be down): {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error updating Trilium: {e}")
        return False


def get_tmdb_recent_movies() -> List[Dict]:
    """Fetch recent movies from TMDB (last 7 days with high ratings)"""
    headers = get_tmdb_headers()

    # Calculate date range (last 7 days)
    today = datetime.now().strftime('%Y-%m-%d')
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    url = f"{TMDB_BASE_URL}/discover/movie"

    params = {
        'primary_release_date.gte': seven_days_ago,
        'primary_release_date.lte': today,
        'sort_by': 'vote_average.desc',
        'vote_count.gte': 50,
        'language': 'de-DE',
        'include_adult': False,
        'page': 1
    }

    try:
        logger.info(f"Fetching recent movies from TMDB ({seven_days_ago} to {today})")
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        movies = data.get('results', [])
        logger.info(f"Found {len(movies)} recent movies from TMDB")
        return movies
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching recent movies from TMDB: {e}")
        return []


def get_tmdb_popular_movies() -> List[Dict]:
    """Fetch popular movies from TMDB as backup"""
    headers = get_tmdb_headers()

    url = f"{TMDB_BASE_URL}/movie/popular"

    params = {
        'language': 'de-DE',
        'page': 1
    }

    try:
        logger.info("Fetching popular movies from TMDB")
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        movies = data.get('results', [])
        logger.info(f"Found {len(movies)} popular movies from TMDB")
        return movies
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching popular movies from TMDB: {e}")
        return []


def get_tmdb_recent_tv_shows() -> List[Dict]:
    """Fetch recent TV shows from TMDB (last 7 days with high ratings)"""
    headers = get_tmdb_headers()

    # Calculate date range (last 7 days)
    today = datetime.now().strftime('%Y-%m-%d')
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    url = f"{TMDB_BASE_URL}/discover/tv"

    params = {
        'first_air_date.gte': seven_days_ago,
        'first_air_date.lte': today,
        'sort_by': 'vote_average.desc',
        'vote_count.gte': 50,
        'language': 'de-DE',
        'include_adult': False,
        'page': 1
    }

    try:
        logger.info(f"Fetching recent TV shows from TMDB ({seven_days_ago} to {today})")
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        shows = data.get('results', [])
        logger.info(f"Found {len(shows)} recent TV shows from TMDB")
        return shows
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching recent TV shows from TMDB: {e}")
        return []


def get_tmdb_popular_tv_shows() -> List[Dict]:
    """Fetch popular TV shows from TMDB as backup"""
    headers = get_tmdb_headers()

    url = f"{TMDB_BASE_URL}/tv/popular"

    params = {
        'language': 'de-DE',
        'page': 1
    }

    try:
        logger.info("Fetching popular TV shows from TMDB")
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        shows = data.get('results', [])
        logger.info(f"Found {len(shows)} popular TV shows from TMDB")
        return shows
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching popular TV shows from TMDB: {e}")
        return []


def get_tmdb_trailer(tmdb_id: int, media_type: str) -> Optional[str]:
    """Get trailer URL for a movie or TV show (prefer German, fallback to English)"""
    headers = get_tmdb_headers()

    endpoint = "movie" if media_type == "movie" else "tv"
    url = f"{TMDB_BASE_URL}/{endpoint}/{tmdb_id}/videos"

    params = {'language': 'de-DE'}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        videos = data.get('results', [])

        # Try German trailer first
        for video in videos:
            if video.get('type') == 'Trailer' and video.get('site') == 'YouTube' and video.get('iso_639_1') == 'de':
                return f"https://www.youtube.com/watch?v={video['key']}"

        # Fallback to English trailer
        params = {'language': 'en-US'}
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        videos = data.get('results', [])

        for video in videos:
            if video.get('type') == 'Trailer' and video.get('site') == 'YouTube' and video.get('iso_639_1') == 'en':
                return f"https://www.youtube.com/watch?v={video['key']}"

        # Fallback to any trailer
        for video in videos:
            if video.get('type') == 'Trailer' and video.get('site') == 'YouTube':
                return f"https://www.youtube.com/watch?v={video['key']}"

        return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching trailer for {media_type} ID {tmdb_id}: {e}")
        return None


def get_tmdb_genres(tmdb_id: int, media_type: str) -> List[str]:
    """Get genre names for a movie or TV show"""
    headers = get_tmdb_headers()

    endpoint = "movie" if media_type == "movie" else "tv"
    url = f"{TMDB_BASE_URL}/{endpoint}/{tmdb_id}"

    params = {'language': 'de-DE'}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        genres = [g['name'] for g in data.get('genres', [])]
        return genres

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching genres for {media_type} ID {tmdb_id}: {e}")
        return []


def convert_tmdb_to_media_item(tmdb_data: Dict, media_type: str) -> Optional[MediaItem]:
    """Convert TMDB API response to MediaItem"""
    try:
        tmdb_id = tmdb_data.get('id')
        if not tmdb_id:
            return None

        # Get title (different field names for movies vs TV)
        if media_type == 'movie':
            title = tmdb_data.get('title', 'Unknown')
            release_date = tmdb_data.get('release_date', 'N/A')
        else:  # tv
            title = tmdb_data.get('name', 'Unknown')
            release_date = tmdb_data.get('first_air_date', 'N/A')

        # Get poster URL
        poster_url = None
        if tmdb_data.get('poster_path'):
            poster_url = f"{TMDB_IMAGE_BASE_URL}{tmdb_data['poster_path']}"

        # Get genres (from genre_ids if available, otherwise fetch)
        genres = []
        if 'genres' in tmdb_data and isinstance(tmdb_data['genres'], list):
            # Full genre objects with names
            genres = [g['name'] for g in tmdb_data['genres'] if 'name' in g]
        elif 'genre_ids' in tmdb_data:
            # Just IDs, would need to map - skip for now
            genres = []

        # Get trailer
        trailer_url = get_tmdb_trailer(tmdb_id, media_type)

        # If genres not in response, fetch them
        if not genres:
            genres = get_tmdb_genres(tmdb_id, media_type)

        # Check Overseerr availability
        overseerr_data = check_overseerr_availability(tmdb_id, media_type)
        overseerr_status = overseerr_data['status']

        # Build Overseerr URL
        overseerr_url = f"{OVERSEERR_URL}/{media_type}/{tmdb_id}"

        return MediaItem(
            title=title,
            tmdb_id=tmdb_id,
            rating=tmdb_data.get('vote_average', 0.0),
            overview=tmdb_data.get('overview', 'No description available'),
            release_date=release_date,
            poster_url=poster_url,
            trailer_url=trailer_url,
            genres=genres,
            vote_count=tmdb_data.get('vote_count', 0),
            media_type=media_type,
            overseerr_status=overseerr_status,
            overseerr_url=overseerr_url
        )

    except Exception as e:
        logger.error(f"Error converting TMDB data to MediaItem: {e}")
        return None


def get_ollama_recommendations(movies: List[MediaItem], shows: List[MediaItem]) -> Tuple[List[Dict], List[Dict]]:
    """Use Ollama to select top 5 movies and top 5 TV shows"""

    # Prepare data for Ollama
    movies_data = [
        {
            'title': m.title,
            'rating': m.rating,
            'vote_count': m.vote_count,
            'genres': m.genres,
            'overview': m.overview[:200]  # Truncate for context size
        }
        for m in movies
    ]

    shows_data = [
        {
            'title': s.title,
            'rating': s.rating,
            'vote_count': s.vote_count,
            'genres': s.genres,
            'overview': s.overview[:200]
        }
        for s in shows
    ]

    prompt = f"""Analyze these items and select the TOP 5 movies and TOP 5 TV shows based on ratings, vote counts, and relevance.
Provide a brief reason for each selection (max 50 words).

Movies: {json.dumps(movies_data, ensure_ascii=False)}

TV Shows: {json.dumps(shows_data, ensure_ascii=False)}

Return ONLY valid JSON in this exact format (no other text):
{{"movies": [{{"title": "Movie Title", "reason": "Brief reason"}}], "shows": [{{"title": "Show Title", "reason": "Brief reason"}}]}}"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    try:
        logger.info("Requesting recommendations from Ollama...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)  # 5 min timeout for AI
        response.raise_for_status()

        result = response.json()
        response_text = result.get('response', '{}')

        # Parse the JSON response
        recommendations = json.loads(response_text)

        selected_movies = recommendations.get('movies', [])[:5]
        selected_shows = recommendations.get('shows', [])[:5]

        logger.info(f"Ollama selected {len(selected_movies)} movies and {len(selected_shows)} shows")

        return selected_movies, selected_shows

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API: {e}")
        # Fallback: return top rated items
        logger.info("Falling back to rating-based selection")
        return fallback_selection(movies, shows)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Ollama response: {e}")
        logger.info("Falling back to rating-based selection")
        return fallback_selection(movies, shows)


def fallback_selection(movies: List[MediaItem], shows: List[MediaItem]) -> Tuple[List[Dict], List[Dict]]:
    """Fallback selection based on ratings if Ollama fails"""
    # Sort by rating and vote count
    sorted_movies = sorted(movies, key=lambda x: (x.rating, x.vote_count), reverse=True)[:5]
    sorted_shows = sorted(shows, key=lambda x: (x.rating, x.vote_count), reverse=True)[:5]

    selected_movies = [
        {'title': m.title, 'reason': f'Highly rated with {m.vote_count} votes'}
        for m in sorted_movies
    ]

    selected_shows = [
        {'title': s.title, 'reason': f'Highly rated with {s.vote_count} votes'}
        for s in sorted_shows
    ]

    return selected_movies, selected_shows


def generate_html_email(selected_movies: List[Dict], selected_shows: List[Dict],
                       all_movies: List[MediaItem], all_shows: List[MediaItem],
                       plex_stats: Dict) -> str:
    """Generate HTML email newsletter with Plex statistics"""

    # Create lookup dictionaries
    movies_dict = {m.title: m for m in all_movies}
    shows_dict = {s.title: s for s in all_shows}

    current_date = datetime.now().strftime("%d. %B %Y")

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Media Newsletter</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f4f4f4;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 800px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .content {{
            padding: 40px 20px;
        }}

        .section {{
            margin-bottom: 50px;
        }}

        .section h2 {{
            font-size: 2em;
            color: #333;
            margin-bottom: 30px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}

        .media-item {{
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
            padding: 20px;
            background-color: #f9f9f9;
            border-radius: 8px;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .media-item:hover {{
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }}

        .poster {{
            flex-shrink: 0;
            width: 150px;
            height: 225px;
            border-radius: 5px;
            overflow: hidden;
            background-color: #ddd;
        }}

        .poster img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .poster-placeholder {{
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 3em;
        }}

        .details {{
            flex: 1;
        }}

        .details h3 {{
            font-size: 1.5em;
            color: #333;
            margin-bottom: 10px;
        }}

        .meta {{
            display: flex;
            gap: 15px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}

        .rating {{
            background-color: #ffd700;
            color: #333;
            padding: 5px 10px;
            border-radius: 5px;
            font-weight: bold;
        }}

        .genres {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 10px;
        }}

        .genre {{
            background-color: #667eea;
            color: white;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.85em;
        }}

        .overview {{
            color: #666;
            margin-bottom: 15px;
            line-height: 1.5;
        }}

        .ai-reason {{
            background-color: #e8f4f8;
            border-left: 4px solid #667eea;
            padding: 10px 15px;
            margin-bottom: 15px;
            font-style: italic;
            color: #555;
        }}

        .trailer-btn {{
            display: inline-block;
            background-color: #ff0000;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            transition: background-color 0.2s;
            margin-right: 10px;
        }}

        .trailer-btn:hover {{
            background-color: #cc0000;
        }}

        .request-btn {{
            display: inline-block;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            transition: background-color 0.2s;
        }}

        .request-btn.available {{
            background-color: #28a745;
            cursor: default;
        }}

        .request-btn.requested {{
            background-color: #fd7e14;
            cursor: default;
        }}

        .request-btn.not-available {{
            background-color: #007bff;
        }}

        .request-btn.not-available:hover {{
            background-color: #0056b3;
        }}

        .stats-section {{
            background-color: #f9f9f9;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}

        .stats-section h2 {{
            font-size: 1.8em;
            color: #333;
            margin-bottom: 20px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}

        .stat-item {{
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}

        .stat-icon {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}

        .stat-label {{
            color: #666;
            font-size: 0.95em;
        }}

        .footer {{
            background-color: #333;
            color: white;
            text-align: center;
            padding: 20px;
            font-size: 0.9em;
        }}

        @media (max-width: 600px) {{
            .media-item {{
                flex-direction: column;
            }}

            .poster {{
                width: 100%;
                height: 300px;
            }}

            .header h1 {{
                font-size: 1.8em;
            }}

            .section h2 {{
                font-size: 1.5em;
            }}

            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 Weekly Media Newsletter</h1>
            <p>{current_date}</p>
            <p>Deine persönlichen Top 5 Filme & Serien der Woche</p>
        </div>

        <div class="content">
"""

    # Movies section
    if selected_movies:
        html += """
            <div class="section">
                <h2>🎥 Top 5 Filme</h2>
"""

        for item in selected_movies:
            movie = movies_dict.get(item['title'])
            if not movie:
                continue

            poster_html = f'<img src="{movie.poster_url}" alt="{movie.title}">' if movie.poster_url else '<div class="poster-placeholder">🎬</div>'

            genres_html = ''.join([f'<span class="genre">{g}</span>' for g in movie.genres])

            trailer_html = f'<a href="{movie.trailer_url}" class="trailer-btn" target="_blank">▶ Trailer ansehen</a>' if movie.trailer_url else ''

            # Generate Overseerr button based on status
            if movie.overseerr_status == "available":
                overseerr_html = '<span class="request-btn available">✓ Verfügbar</span>'
            elif movie.overseerr_status == "requested":
                overseerr_html = '<span class="request-btn requested">⏳ Angefragt</span>'
            else:  # not_available
                overseerr_html = f'<a href="{movie.overseerr_url}" class="request-btn not-available" target="_blank">➕ In Overseerr anfordern</a>'

            html += f"""
                <div class="media-item">
                    <div class="poster">
                        {poster_html}
                    </div>
                    <div class="details">
                        <h3>{movie.title}</h3>
                        <div class="meta">
                            <span class="rating">⭐ {movie.rating:.1f}/10</span>
                            <span>📅 {movie.release_date}</span>
                            <span>👥 {movie.vote_count} Bewertungen</span>
                        </div>
                        <div class="genres">
                            {genres_html}
                        </div>
                        <div class="ai-reason">
                            <strong>💡 Empfehlung:</strong> {item.get('reason', 'Hochbewertet')}
                        </div>
                        <p class="overview">{movie.overview}</p>
                        {trailer_html}
                        {overseerr_html}
                    </div>
                </div>
"""

        html += "            </div>\n"

    # TV Shows section
    if selected_shows:
        html += """
            <div class="section">
                <h2>📺 Top 5 Serien</h2>
"""

        for item in selected_shows:
            show = shows_dict.get(item['title'])
            if not show:
                continue

            poster_html = f'<img src="{show.poster_url}" alt="{show.title}">' if show.poster_url else '<div class="poster-placeholder">📺</div>'

            genres_html = ''.join([f'<span class="genre">{g}</span>' for g in show.genres])

            trailer_html = f'<a href="{show.trailer_url}" class="trailer-btn" target="_blank">▶ Trailer ansehen</a>' if show.trailer_url else ''

            # Generate Overseerr button based on status
            if show.overseerr_status == "available":
                overseerr_html = '<span class="request-btn available">✓ Verfügbar</span>'
            elif show.overseerr_status == "requested":
                overseerr_html = '<span class="request-btn requested">⏳ Angefragt</span>'
            else:  # not_available
                overseerr_html = f'<a href="{show.overseerr_url}" class="request-btn not-available" target="_blank">➕ In Overseerr anfordern</a>'

            html += f"""
                <div class="media-item">
                    <div class="poster">
                        {poster_html}
                    </div>
                    <div class="details">
                        <h3>{show.title}</h3>
                        <div class="meta">
                            <span class="rating">⭐ {show.rating:.1f}/10</span>
                            <span>📅 {show.release_date}</span>
                            <span>👥 {show.vote_count} Bewertungen</span>
                        </div>
                        <div class="genres">
                            {genres_html}
                        </div>
                        <div class="ai-reason">
                            <strong>💡 Empfehlung:</strong> {item.get('reason', 'Hochbewertet')}
                        </div>
                        <p class="overview">{show.overview}</p>
                        {trailer_html}
                        {overseerr_html}
                    </div>
                </div>
"""

        html += "            </div>\n"

    # Plex Statistics section (if available)
    if plex_stats.get('success', False):
        html += f"""
            <div class="stats-section">
                <h2>📊 Deine Woche in Zahlen</h2>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-icon">🎬</div>
                        <div class="stat-value">{plex_stats.get('movies_watched', 0)}</div>
                        <div class="stat-label">Filme geschaut</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-icon">📺</div>
                        <div class="stat-value">{plex_stats.get('episodes_watched', 0)}</div>
                        <div class="stat-label">Episoden geschaut</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-icon">⏱️</div>
                        <div class="stat-value">{plex_stats.get('total_hours', 0)}</div>
                        <div class="stat-label">Stunden gestreamt</div>
                    </div>
                </div>
            </div>
"""

    html += """
        </div>

        <div class="footer">
            <p>Generiert von weekly_newsletter.py</p>
            <p>Powered by TMDB & Ollama AI</p>
        </div>
    </div>
</body>
</html>
"""

    return html


def extract_ai_reason(item: MediaItem) -> str:
    """
    Extrahiert die AI-Empfehlung aus dem MediaItem
    Falls nicht vorhanden, generiere eine kurze Beschreibung
    """
    reason = item.overview[:150] if item.overview else "Empfohlen aufgrund hoher Bewertung"
    return reason.strip() + ('...' if len(item.overview) > 150 else '')


def generate_json_index(selected_movies: List[Dict], selected_shows: List[Dict],
                       all_movies: List[MediaItem], all_shows: List[MediaItem],
                       filepath: str) -> bool:
    """
    Erstellt/aktualisiert newsletters/index.json für Family Hub

    Format:
    [
      {
        "date": "2025-10-11",
        "title": "Weekly Media Newsletter",
        "path": "weekly_newsletter_2025-10-11.html",
        "movies": [
          {"title": "Movie Title", "rating": 8.5, "reason": "AI Empfehlung..."},
          ...
        ],
        "shows": [
          {"title": "Show Title", "rating": 8.3, "reason": "AI Empfehlung..."},
          ...
        ]
      },
      ... (weitere Newsletter, max 50)
    ]
    """
    try:
        # Pfad zum index.json
        index_path = REPORT_DIR / 'index.json'

        # Lese existierendes Index (falls vorhanden)
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                try:
                    newsletters = json.load(f)
                except json.JSONDecodeError:
                    newsletters = []
        else:
            newsletters = []

        # Erstelle neuen Newsletter-Eintrag
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = os.path.basename(filepath)

        # Create movie lookup dict
        movies_dict = {m.title: m for m in all_movies}
        shows_dict = {s.title: s for s in all_shows}

        new_entry = {
            "date": current_date,
            "title": f"Weekly Media Newsletter - KW {datetime.now().isocalendar()[1]}",
            "path": filename,
            "movies": [
                {
                    "title": movie.get('title', ''),
                    "rating": movies_dict.get(movie.get('title', ''), MediaItem(
                        title='', tmdb_id=0, rating=0.0, overview='',
                        release_date='', poster_url=None, trailer_url=None,
                        genres=[], vote_count=0, media_type='movie'
                    )).rating,
                    "reason": movie.get('reason', '')
                }
                for movie in selected_movies
            ],
            "shows": [
                {
                    "title": show.get('title', ''),
                    "rating": shows_dict.get(show.get('title', ''), MediaItem(
                        title='', tmdb_id=0, rating=0.0, overview='',
                        release_date='', poster_url=None, trailer_url=None,
                        genres=[], vote_count=0, media_type='tv'
                    )).rating,
                    "reason": show.get('reason', '')
                }
                for show in selected_shows
            ]
        }

        # Füge neuen Eintrag hinzu (an den Anfang)
        newsletters.insert(0, new_entry)

        # Behalte nur letzte 50 Newsletter
        newsletters = newsletters[:50]

        # Schreibe zurück
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(newsletters, f, ensure_ascii=False, indent=2)

        logger.info(f"Newsletter index updated: {index_path}")
        return True

    except Exception as e:
        logger.error(f"Error updating newsletter index: {e}")
        return False


def send_push_notification(newsletter_title: str) -> bool:
    """
    Sendet Push Notification an Family Hub Backend
    """
    try:
        FAMILY_HUB_URL = "http://192.168.188.123:8000"

        payload = {
            "title": "📰 Neuer Newsletter verfügbar!",
            "body": f"{newsletter_title} - Jetzt in der Family Hub App ansehen!",
            "url": "/index.html#newsletter"
        }

        response = requests.post(
            f"{FAMILY_HUB_URL}/api/push/notify",
            json=payload,
            timeout=10
        )

        if response.ok:
            result = response.json()
            logger.info(f"Push notification sent: {result}")
            return True
        else:
            logger.warning(f"Push notification failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error sending push notification: {e}")
        return False


def save_report(html_content: str) -> Tuple[bool, str]:
    """Save HTML report to NAS storage (no Git operations)"""
    # Create reports directory if needed
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate filename
    current_date = datetime.now().strftime("%Y-%m-%d")
    filename = f"weekly_newsletter_{current_date}.html"
    filepath = REPORT_DIR / filename

    # Write report
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Report saved to: {filepath}")
        return True, str(filepath)
    except Exception as e:
        logger.error(f"Error saving report: {e}")
        return False, ""


def main():
    """Main execution"""
    # Initialize logging first
    setup_logging()

    logger.info("=" * 60)
    logger.info("Weekly Media Newsletter Generator (TMDB Edition)")
    logger.info("=" * 60)

    # Fetch Plex watch statistics
    logger.info("Fetching Plex watch statistics...")
    plex_stats = get_plex_watch_stats()
    if plex_stats.get('success'):
        logger.info(f"Plex stats retrieved: {plex_stats['movies_watched']} movies, "
                   f"{plex_stats['episodes_watched']} episodes, {plex_stats['total_hours']} hours")
    else:
        logger.warning("Plex statistics unavailable (continuing without stats)")

    # Fetch recent movies (last 7 days)
    recent_movies = get_tmdb_recent_movies()

    # If not enough recent movies, fetch popular movies as backup
    if len(recent_movies) < 10:
        logger.info(f"Only {len(recent_movies)} recent movies found, fetching popular movies...")
        popular_movies = get_tmdb_popular_movies()
        # Combine recent and popular, but prioritize recent
        all_movies_data = recent_movies + [m for m in popular_movies if m not in recent_movies]
    else:
        all_movies_data = recent_movies

    # Fetch recent TV shows (last 7 days)
    recent_shows = get_tmdb_recent_tv_shows()

    # If not enough recent shows, fetch popular shows as backup
    if len(recent_shows) < 10:
        logger.info(f"Only {len(recent_shows)} recent TV shows found, fetching popular shows...")
        popular_shows = get_tmdb_popular_tv_shows()
        # Combine recent and popular, but prioritize recent
        all_shows_data = recent_shows + [s for s in popular_shows if s not in recent_shows]
    else:
        all_shows_data = recent_shows

    if not all_movies_data and not all_shows_data:
        logger.warning("No content found from TMDB")
        return

    # Convert TMDB data to MediaItem objects
    logger.info("Converting movies to MediaItem objects...")
    enriched_movies: List[MediaItem] = []
    for movie_data in all_movies_data[:20]:  # Limit to 20 to avoid too many API calls
        media_item = convert_tmdb_to_media_item(movie_data, 'movie')
        if media_item:
            enriched_movies.append(media_item)

    logger.info("Converting TV shows to MediaItem objects...")
    enriched_shows: List[MediaItem] = []
    for show_data in all_shows_data[:20]:  # Limit to 20 to avoid too many API calls
        media_item = convert_tmdb_to_media_item(show_data, 'tv')
        if media_item:
            enriched_shows.append(media_item)

    logger.info(f"Processed {len(enriched_movies)} movies and {len(enriched_shows)} TV shows")

    if not enriched_movies and not enriched_shows:
        logger.warning("No enriched content available")
        return

    # Get AI recommendations
    logger.info("Getting AI recommendations from Ollama...")
    selected_movies, selected_shows = get_ollama_recommendations(enriched_movies, enriched_shows)

    # Generate HTML email
    logger.info("Generating HTML email...")
    html_content = generate_html_email(selected_movies, selected_shows, enriched_movies, enriched_shows, plex_stats)

    # Save report (no Git operations)
    logger.info("Saving report to NAS...")
    success, filepath = save_report(html_content)

    # Generate JSON Index for Family Hub
    if success:
        logger.info("Generating JSON index for Family Hub...")
        index_success = generate_json_index(selected_movies, selected_shows, enriched_movies, enriched_shows, filepath)

        if index_success:
            logger.info("JSON index created successfully!")
        else:
            logger.warning("Failed to create JSON index (continuing anyway)")

    # Update Trilium knowledge base
    if success:
        logger.info("Updating Trilium knowledge base...")
        newsletter_data = {
            'selected_movies': selected_movies,
            'selected_shows': selected_shows,
            'all_movies': enriched_movies,
            'all_shows': enriched_shows,
            'plex_stats': plex_stats,
            'html_filepath': filepath,
            'date': datetime.now().strftime("%Y-%m-%d")
        }
        trilium_success = update_trilium_knowledge_base(newsletter_data)
        if trilium_success:
            logger.info("Trilium knowledge base updated successfully!")
        else:
            logger.warning("Failed to update Trilium knowledge base (continuing anyway)")

    # Send Push Notification to Family Hub
    if success:
        logger.info("Sending push notification to Family Hub...")
        newsletter_title = f"Weekly Media Newsletter - KW {datetime.now().isocalendar()[1]}"
        push_success = send_push_notification(newsletter_title)

        if push_success:
            logger.info("Push notification sent successfully!")
        else:
            logger.warning("Failed to send push notification (continuing anyway)")

    logger.info("=" * 60)
    if success:
        logger.info("SUCCESS: Newsletter generated and saved to NAS!")
        logger.info(f"Report location: {filepath}")
    else:
        logger.warning("WARNING: Newsletter generation failed")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nScript interrupted by user")
    except Exception as e:
        logger.exception(f"Unexpected error in main: {e}")
