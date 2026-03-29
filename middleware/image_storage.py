import json
import logging
import os
import sys
import base64
import io
from datetime import datetime
from typing import Dict, Any, Optional, List
from PIL import Image

sys_path_added = False
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))
    sys_path_added = True

from config import config
from logger import get_logger


logger = get_logger()


class ImageStorage:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or config.storage_dir
        self.images_dir = os.path.join(self.storage_dir, "images")
        self.metadata_dir = os.path.join(self.storage_dir, "metadata")
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)

    def _generate_filename(self) -> str:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{timestamp}.png"

    def save_image(self, b64_data: str, metadata: Dict[str, Any]) -> str:
        filename = self._generate_filename()
        image_path = os.path.join(self.images_dir, filename)
        metadata_path = os.path.join(self.metadata_dir, filename.replace(".png", ".json"))
        
        image_data = base64.b64decode(b64_data)
        image = Image.open(io.BytesIO(image_data))
        image.save(image_path, "PNG")
        
        metadata["filename"] = filename
        metadata["timestamp"] = datetime.utcnow().isoformat() + "Z"
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info("Image saved", filename=filename)
        
        return filename

    def get_image(self, filename: str) -> Optional[Dict[str, Any]]:
        image_path = os.path.join(self.images_dir, filename)
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                b64_data = base64.b64encode(f.read()).decode('utf-8')
            metadata_path = os.path.join(self.metadata_dir, filename.replace(".png", ".json"))
            metadata = {}
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            return {
                "filename": filename,
                "image": b64_data,
                "metadata": metadata
            }
        return None

    def list_images(self, limit: int = 50) -> List[Dict[str, Any]]:
        images: List[Dict[str, Any]] = []
        for filename in sorted(os.listdir(self.images_dir), reverse=True)[:limit]:
            if filename.endswith(".png"):
                image_data = self.get_image(filename)
                if image_data:
                    image_data["filename"] = filename
                    images.append(image_data)
        return images


image_storage = ImageStorage()
