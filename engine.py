# media_engine.py
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
    
    def extract_keywords_from_visual_plan(self, visual_plan_text):
        keywords = []
        lines = visual_plan_text.split('\n')
        for line in lines:
            if any(marker in line.lower() for marker in ['keyword', 'search', 'query', 'broll', 'visual']):
                parts = re.split(r'[:\-]', line, maxsplit=1)
                if len(parts) > 1:
                    kw = parts[1].strip().strip('"').strip("'")
                    if kw and len(kw) > 2:
                        keywords.append(kw)
        if not keywords:
            for line in lines:
                if len(line) > 10 and not line.startswith('#'):
                    clean = line.strip().strip('-').strip('*').strip()
                    if clean and len(clean) > 5:
                        keywords.append(clean)
        return keywords[:8]
    
    def search_for_scenes(self, visual_plan_text, scenes_count=5):
        keywords = self.extract_keywords_from_visual_plan(visual_plan_text)
        scene_assets = []
        for i, kw in enumerate(keywords[:scenes_count]):
            media_type = "video" if i % 2 == 0 else "image"
            results = self.search_all(kw, media_type=media_type, per_page=2)
            scene_assets.append({
                "scene": i + 1, "keyword": kw,
                "media_type": media_type, "assets": results[:2],
            })
        return scene_assets


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
    
    def create_text_clip(self, text, duration, size=(1080, 1920), fontsize=60, color='white', position='center'):
        try:
            from moviepy.editor import TextClip
            txt_clip = TextClip(text, fontsize=fontsize, color=color, font='Arial-Bold', method='caption', size=(size[0] - 100, None))
            txt_clip = txt_clip.set_duration(duration).set_position(position)
            return txt_clip
        except Exception:
            return None
    
    def assemble_shorts(self, scenes, audio_path=None, output_path="output.mp4"):
        try:
            from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, concatenate_videoclips
        except ImportError:
            return {"error": "MoviePy not installed"}
        
        clips = []
        scene_duration = 60 / max(len(scenes), 1)
        
        for i, scene in enumerate(scenes):
            assets = scene.get("assets", [])
            if not assets:
                continue
            asset = assets[0]
            url = asset.get("url", "")
            media_type = asset.get("type", "image")
            
            try:
                if media_type == "video" and url:
                    filepath = self.download_media(url, f"scene_{i}.mp4")
                    if filepath:
                        clip = VideoFileClip(filepath).subclip(0, min(scene_duration, 5))
                        clip = clip.resize(height=1920)
                        w, h = clip.size
                        target_w = 1080
                        if w > target_w:
                            x1 = (w - target_w) // 2
                            clip = clip.crop(x1=x1, y1=0, width=target_w, height=1920)
                        clips.append(clip)
                elif media_type == "image" and url:
                    filepath = self.download_media(url, f"scene_{i}.jpg")
                    if filepath:
                        clip = ImageClip(filepath).set_duration(min(scene_duration, 5))
                        clip = clip.resize(height=1920)
                        w, h = clip.size
                        target_w = 1080
                        if w > target_w:
                            x1 = (w - target_w) // 2
                            clip = clip.crop(x1=x1, y1=0, width=target_w, height=1920)
                        clips.append(clip)
            except Exception:
                continue
        
        if not clips:
            return {"error": "No valid clips could be created"}
        
        try:
            final = concatenate_videoclips(clips, method="compose")
            if audio_path and os.path.exists(audio_path):
                try:
                    audio = AudioFileClip(audio_path)
                    audio = audio.subclip(0, min(final.duration, audio.duration))
                    final = final.set_audio(audio)
                except Exception:
                    pass
            
            final.write_videofile(
                output_path, fps=24, codec='libx264', audio_codec='aac',
                temp_audiofile=os.path.join(self.temp_dir, 'temp_audio.m4a'),
                remove_temp=True, threads=2, preset='ultrafast', logger=None
            )
            return {"success": True, "path": output_path, "duration": final.duration}
        except Exception as e:
            return {"error": str(e)}
    
    def create_project_package(self, script, visual_plan, scene_assets, audio_url=None):
        import json
        return {
            "script": script, "visual_plan": visual_plan,
            "scenes": scene_assets, "audio_url": audio_url,
            "instructions": "Import assets into your video editor and follow the scene timeline.",
        }
