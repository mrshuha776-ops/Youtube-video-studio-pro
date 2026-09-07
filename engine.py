import requests
import os
import tempfile
from typing import List, Dict, Any, Optional
import re

class MediaEngine:
    def __init__(self, pexels_key=None, pixabay_key=None):
        self.pexels_key = pexels_key
        self.pixabay_key = pixabay_key
        self.assets = []
    
    def search_pexels(self, query, media_type="video", per_page=5):
        if not self.pexels_key:
            return []
        endpoint = "videos" if media_type == "video" else "search"
        url = f"https://api.pexels.com/v1/{endpoint}"
        headers = {"Authorization": self.pexels_key}
        params = {"query": query, "per_page": per_page, "orientation": "landscape" if media_type == "video" else "all"}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            data = resp.json()
            results = []
            items = data.get("videos", []) if media_type == "video" else data.get("photos", [])
            for item in items:
                if media_type == "video":
                    video_files = item.get("video_files", [])
                    best_file = next((vf for vf in video_files if vf.get("quality") == "hd"), video_files[0] if video_files else None)
                    results.append({
                        "id": item.get("id"), "type": "video",
                        "url": best_file["link"] if best_file else "",
                        "thumbnail": item.get("image"),
                        "duration": item.get("duration", 0),
                        "source": "pexels", "query": query,
                    })
                else:
                    results.append({
                        "id": item.get("id"), "type": "image",
                        "url": item.get("src", {}).get("large", ""),
                        "thumbnail": item.get("src", {}).get("medium", ""),
                        "source": "pexels", "query": query,
                    })
            return results
        except Exception:
            return []

    def search_pixabay(self, query, media_type="video", per_page=5):
        if not self.pixabay_key:
            return []
        endpoint = "videos/" if media_type == "video" else ""
        url = f"https://pixabay.com/api/{endpoint}"
        params = {"key": self.pixabay_key, "q": query, "per_page": per_page}
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            results = []
            for item in data.get("hits", []):
                if media_type == "video":
                    results.append({
                        "id": item.get("id"), "type": "video",
                        "url": item.get("videos", {}).get("large", {}).get("url", ""),
                        "thumbnail": item.get("picture_id"),
                        "source": "pixabay", "query": query,
                    })
                else:
                    results.append({
                        "id": item.get("id"), "type": "image",
                        "url": item.get("largeImageURL", ""),
                        "thumbnail": item.get("webformatURL", ""),
                        "source": "pixabay", "query": query,
                    })
            return results
        except Exception:
            return []

    def search_all(self, query, media_type="video", per_page=3):
        all_results = []
        all_results.extend([r for r in self.search_pexels(query, media_type, per_page) if "error" not in r])
        all_results.extend([r for r in self.search_pixabay(query, media_type, per_page) if "error" not in r])
        return all_results[:per_page * 2]

class VideoAssembler:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def download_media(self, url, filename):
        try:
            resp = requests.get(url, timeout=30, stream=True)
            filepath = os.path.join(self.temp_dir, filename)
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return filepath
        except Exception:
            return None
