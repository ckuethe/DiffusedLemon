import aiohttp
from aiohttp import web
from typing import Dict, Any, Optional, List
import json
import os
import argparse
import base64
import io
import time
import asyncio
from datetime import datetime, UTC
from PIL import Image

from .config import config
from .logger import get_logger


logger = get_logger()


class LemonadeClient:
    _flux_assistant_session: Optional[aiohttp.ClientSession] = None
    _flux_assistant_last_used: float = 0
    _unload_task: Optional["asyncio.Task"] = None
    _tasks: set = set()

    def __init__(self, server_uri: Optional[str] = None):
        self.server_uri = server_uri or config.server_uri
        self.auth_token = config.auth_token
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session and self._session != LemonadeClient._flux_assistant_session:
            await self._session.close()
        self._session = None

    async def close(self):
        if self._session and self._session != LemonadeClient._flux_assistant_session:
            await self._session.close()
            self._session = None

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        if self._session is None:
            raise Exception(
                "Client session not initialized. Use 'async with' context manager."
            )

        url = f"{self.server_uri}{endpoint}"
        headers = kwargs.get("headers", {"Content-Type": "application/json"})
        if self.auth_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        kwargs["headers"] = headers

        try:
            async with self._session.request(method, url, **kwargs) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"HTTP {response.status} from Lemonade: {error_text}")
                    raise Exception(f"HTTP {response.status}: {error_text}")
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"Connection error to Lemonade: {e}")
            raise Exception(f"Failed to connect to Lemonade server: {e}")

    async def get_models(self) -> list:
        if self._session is None:
            raise Exception(
                "Client session not initialized. Use 'async with' context manager."
            )
        response = await self._request("GET", "/api/v1/models")
        return response.get("data", [])

    async def chat_completion(
        self, model: str, messages: list, stream: bool = False
    ) -> str:
        payload = {"model": model, "messages": messages, "stream": stream}
        response = await self._request("POST", "/api/v1/chat/completions", json=payload)
        return response["choices"][0]["message"]["content"]

    async def generate_image(
        self,
        model: str,
        prompt: str,
        size: str = "512x512",
        steps: int = 4,
        seed: Optional[int] = None,
        cfg_scale: Optional[float] = None,
    ) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "steps": steps,
            "response_format": "b64_json",
        }
        if seed is not None:
            payload["seed"] = seed
        if cfg_scale is not None:
            payload["cfg_scale"] = cfg_scale

        response = await self._request(
            "POST", "/api/v1/images/generations", json=payload
        )
        return response["data"][0]["b64_json"]

    async def is_server_available(self) -> bool:
        try:
            await self._request("GET", "/api/v1/models")
            return True
        except Exception:
            return False

    @classmethod
    async def get_flux_assistant_session(cls) -> aiohttp.ClientSession:
        cls._flux_assistant_last_used = time.time()
        if cls._flux_assistant_session is None:
            logger.debug("Creating new flux assistant session")
            cls._flux_assistant_session = aiohttp.ClientSession()
            logger.debug(
                f"Flux assistant session created: {cls._flux_assistant_session}"
            )
        else:
            logger.debug(
                f"Reusing flux assistant session: {cls._flux_assistant_session}"
            )
        return cls._flux_assistant_session

    @classmethod
    async def maybe_unload_flux_assistant(cls) -> None:
        unload_delay = config.get("flux_assistant_unload_delay", 0)
        logger.debug("Flux assistant unload check", delay=unload_delay)

        if unload_delay < 0:
            logger.debug("Flux assistant unloading immediately (delay < 0)")
            await cls.unload_flux_assistant()
        elif unload_delay > 0:
            logger.debug(
                f"Flux assistant scheduling unload in {unload_delay}s",
                existing_task=str(cls._unload_task) if cls._unload_task else None,
            )
            if cls._unload_task and not cls._unload_task.done():
                logger.debug(
                    "Cancelling existing unload task",
                    task_id=id(cls._unload_task),
                )
                cls._unload_task.cancel()

            task = asyncio.create_task(cls._delayed_unload(unload_delay))
            cls._tasks.add(task)
            task.add_done_callback(cls._tasks.discard)
            cls._unload_task = task
            logger.debug(
                "Unload task created",
                task_id=id(task),
            )
        else:
            if cls._unload_task and not cls._unload_task.done():
                logger.debug(
                    "Cancelling pending unload task (delay = 0)",
                    task_id=id(cls._unload_task),
                )
                cls._unload_task.cancel()

    @classmethod
    async def _delayed_unload(cls, delay: float) -> None:
        logger.debug(f"Delayed unload starting, waiting {delay}s")
        await asyncio.sleep(delay)
        if cls._flux_assistant_session is not None:
            logger.debug("Delayed unload executing")
            await cls.unload_flux_assistant()
        else:
            logger.debug("Delayed unload skipped (session already None)")

    @classmethod
    async def unload_flux_assistant(cls) -> None:
        logger.debug("Attempting to unload flux assistant")
        if cls._flux_assistant_session:
            try:
                await cls._flux_assistant_session.close()
                cls._flux_assistant_session = None
                logger.info("Flux assistant session unloaded")
            except Exception as e:
                logger.error("Failed to unload flux assistant session", error=str(e))

        # Try to unload the model from Lemonade server
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"model_name": config.prompt_assist_model}
                async with session.post(
                    f"{config.server_uri}/api/v1/unload",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status == 200:
                        logger.info(
                            "Flux assistant model unloaded from Lemonade",
                            model=config.prompt_assist_model,
                        )
                    else:
                        error_text = await response.text()
                        logger.warning(
                            "Failed to unload flux assistant model",
                            status=response.status,
                            error=error_text,
                        )
        except Exception as e:
            logger.warning(
                "Could not unload flux assistant model from Lemonade",
                error=str(e),
            )

    @classmethod
    async def close_all(cls) -> None:
        if cls._flux_assistant_session:
            await cls._flux_assistant_session.close()
            cls._flux_assistant_session = None
        if cls._unload_task and not cls._unload_task.done():
            cls._unload_task.cancel()


class ImageStorage:
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or config.storage_dir
        self.images_dir = os.path.join(self.storage_dir, "images")
        self.metadata_dir = os.path.join(self.storage_dir, "metadata")
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)
        self.thumbs_dir = os.path.join(self.storage_dir, "thumbs")
        os.makedirs(self.thumbs_dir, exist_ok=True)

    def _generate_filename(self) -> str:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        return f"{timestamp}.png"

    def save_image(
        self,
        b64_data: str,
        metadata: Dict[str, Any],
        suffix: str = "",
        base_filename: str = "",
    ) -> str:
        if base_filename:
            base = base_filename.replace(".png", "")
            filename = f"{base}_{suffix}.png" if suffix else base_filename
        else:
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
            if suffix:
                timestamp = f"{timestamp}_{suffix}"
            filename = f"{timestamp}.png"
        image_path = os.path.join(self.images_dir, filename)
        metadata_path = os.path.join(
            self.metadata_dir, filename.replace(".png", ".json")
        )

        image_data = base64.b64decode(b64_data)
        image = Image.open(io.BytesIO(image_data))
        image.save(image_path, "PNG")

        metadata["filename"] = filename
        metadata["timestamp"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info("Image saved", filename=filename)

        self.generate_thumbnail(filename)

        return filename

    def generate_thumbnail(self, filename: str) -> str:
        image_path = os.path.join(self.images_dir, filename)
        if not os.path.exists(image_path):
            logger.warning(
                "Thumbnail generation skipped, image not found", filename=filename
            )
            return ""
        thumb_filename = filename.rsplit(".", 1)[0] + ".jpg"
        thumb_path = os.path.join(self.thumbs_dir, thumb_filename)
        if os.path.exists(thumb_path):
            logger.info("Thumbnail already exists", filename=thumb_filename)
            return thumb_filename
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail((128, 128), Image.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=85)
        logger.info("Thumbnail generated", filename=thumb_filename, source=filename)
        return thumb_filename

    def get_image(self, filename: str) -> Optional[Dict[str, Any]]:
        image_path = os.path.join(self.images_dir, filename)
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            metadata_path = os.path.join(
                self.metadata_dir, filename.replace(".png", ".json")
            )
            metadata = {}
            if os.path.exists(metadata_path):
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
            return {"filename": filename, "image": b64_data, "metadata": metadata}
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

    def get_metadata(self, filename: str) -> Optional[Dict[str, Any]]:
        metadata_path = os.path.join(
            self.metadata_dir, filename.replace(".png", ".json")
        )
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                return json.load(f)
        return None

    def list_images_metadata(
        self, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        images: List[Dict[str, Any]] = []
        all_filenames = sorted(os.listdir(self.images_dir), reverse=True)
        for filename in all_filenames[offset : offset + limit]:
            if filename.endswith(".png"):
                metadata_path = os.path.join(
                    self.metadata_dir, filename.replace(".png", ".json")
                )
                if os.path.exists(metadata_path):
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                    images.append({"filename": filename, "metadata": metadata})
        return images


image_storage = ImageStorage()


async def handle_prompt_assist(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        simple_prompt = data.get("prompt", "").strip()

        if not simple_prompt:
            return web.json_response({"error": "Prompt is required"}, status=400)

        session = await LemonadeClient.get_flux_assistant_session()
        client = LemonadeClient()
        client._session = session
        try:
            messages = [
                {"role": "system", "content": config.prompt_assist_system_prompt},
                {
                    "role": "user",
                    "content": f"Expand this prompt for image generation: {simple_prompt}",
                },
            ]

            expanded_prompt = await client.chat_completion(
                model=config.prompt_assist_model, messages=messages, stream=False
            )

            logger.info(
                "Prompt assist completed",
                original_prompt=simple_prompt,
                expanded_prompt=expanded_prompt[:100],
            )

            await LemonadeClient.maybe_unload_flux_assistant()

            return web.json_response(
                {"original_prompt": simple_prompt, "expanded_prompt": expanded_prompt}
            )
        finally:
            await client.close()
    except Exception as e:
        logger.error("Prompt assist failed", error=str(e))
        return web.json_response({"error": str(e)}, status=500)


async def handle_generate(request: web.Request) -> web.Response:
    try:
        data = await request.json()

        required_fields = ["prompt", "model", "size", "steps", "seed"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            return web.json_response(
                {"error": f"Missing required fields: {missing}"}, status=400
            )

        prompt = data["prompt"]
        model = data["model"]
        size = data["size"]
        steps = data["steps"]
        seed = data["seed"]

        cfg_scale = data.get("cfg_scale")

        await LemonadeClient.maybe_unload_flux_assistant()

        start_time = time.time()

        async with LemonadeClient() as client:
            b64_image = await client.generate_image(
                model=model,
                prompt=prompt,
                size=size,
                steps=steps,
                seed=seed,
                cfg_scale=cfg_scale,
            )

            generation_time = time.time() - start_time

            metadata = {
                "prompt": prompt,
                "model": model,
                "size": size,
                "steps": steps,
                "seed": seed,
                "cfg_scale": cfg_scale,
                "generation_time": round(generation_time, 2),
            }

            if "original_prompt" in data:
                metadata["original_prompt"] = data["original_prompt"]
                metadata["prompt_assisted"] = True
            else:
                metadata["prompt_assisted"] = False

            filename = image_storage.save_image(b64_image, metadata)

            logger.info(
                "Image generated successfully",
                filename=filename,
                model=model,
                size=size,
                generation_time=f"{generation_time:.2f}s",
            )

            response_data = {
                "filename": filename,
                "image": b64_image,
                "metadata": metadata,
            }
            logger.info("Generate response", filename=filename)
            return web.json_response(response_data)

    except Exception as e:
        logger.error("Image generation failed", error=str(e))
        return web.json_response({"error": str(e)}, status=500)


async def handle_get_models(request: web.Request) -> web.Response:
    try:
        async with LemonadeClient() as client:
            models = await client.get_models()
            return web.json_response({"models": models})
    except Exception as e:
        logger.error("Failed to get models", error=str(e))
        return web.json_response({"error": str(e)}, status=500)


async def handle_get_image(request: web.Request) -> web.Response:
    try:
        filename = request.match_info.get("filename")
        if not filename:
            return web.json_response({"error": "Filename required"}, status=400)
        image_data = image_storage.get_image(filename)

        if not image_data:
            return web.json_response({"error": "Image not found"}, status=404)

        return web.json_response(image_data)
    except Exception as e:
        logger.error("Failed to get image", error=str(e))
        return web.json_response({"error": str(e)}, status=500)


async def handle_get_thumbnail(request: web.Request) -> web.Response:
    try:
        filename = request.match_info.get("filename")
        if not filename:
            return web.json_response({"error": "Filename required"}, status=400)
        thumb_filename = image_storage.generate_thumbnail(filename)
        if not thumb_filename:
            return web.json_response({"error": "Thumbnail not found"}, status=404)
        thumb_path = os.path.join(image_storage.thumbs_dir, thumb_filename)
        with open(thumb_path, "rb") as f:
            thumb_data = f.read()
        return web.Response(body=thumb_data, content_type="image/jpeg")
    except Exception as e:
        logger.error("Failed to get thumbnail", error=str(e))
        return web.json_response({"error": str(e)}, status=500)


async def handle_list_images(request: web.Request) -> web.Response:
    try:
        limit = int(request.query.get("limit", 50))
        images = image_storage.list_images(limit)
        return web.json_response({"images": images})
    except Exception as e:
        logger.error("Failed to list images", error=str(e))
        return web.json_response({"error": str(e)}, status=500)


async def handle_list_images_metadata(request: web.Request) -> web.Response:
    try:
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))
        images = image_storage.list_images_metadata(limit, offset)
        return web.json_response({"images": images})
    except Exception as e:
        logger.error("Failed to list images metadata", error=str(e))
        return web.json_response({"error": str(e)}, status=500)


ESRGAN_MODELS = {
    "photo": "RealESRGAN-x4plus",
    "anime": "RealESRGAN-x4plus-anime",
}


async def handle_upscale(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        image_b64 = data.get("image")
        upscale_mode = data.get("mode", "off")
        original_filename = data.get("filename")

        logger.info(
            "Upscale request received",
            mode=upscale_mode,
            image_len=len(image_b64),
            original_filename=original_filename,
        )

        if not image_b64:
            return web.json_response({"error": "Image data required"}, status=400)

        if upscale_mode == "off":
            logger.info("Upscale mode is off, returning original")
            return web.json_response({"image": image_b64, "upscaled": False})

        if not original_filename:
            original_filename = image_storage.save_image(
                image_b64, {"type": "original"}
            )

        model_name = ESRGAN_MODELS.get(upscale_mode)
        if not model_name:
            return web.json_response(
                {"error": f"Invalid upscaler mode: {upscale_mode}"}, status=400
            )

        logger.info(
            "Sending upscale request to backend",
            model=model_name,
            url=f"{config.server_uri}/api/v1/images/upscale",
        )

        async with aiohttp.ClientSession() as session:
            payload = {
                "image": image_b64,
                "model": model_name,
            }
            async with session.post(
                f"{config.server_uri}/api/v1/images/upscale",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                response_text = await response.text()
                logger.info(
                    f"Upscale response: status={response.status}, body={response_text[:500]}"
                )
                if response.status >= 400:
                    logger.error(
                        f"HTTP {response.status} from upscale: {response_text}"
                    )
                    return web.json_response(
                        {"error": f"Upscale failed: {response_text}"}, status=500
                    )
                result = json.loads(response_text)

        logger.info("Parsed upscale response keys", keys=list(result.keys()))
        upscaled_b64 = result.get("image") or result.get("b64_json")
        if (
            not upscaled_b64
            and "data" in result
            and isinstance(result["data"], list)
            and len(result["data"]) > 0
        ):
            upscaled_b64 = result["data"][0].get("b64_json")
        if not upscaled_b64:
            logger.warning("No image data in upscale response", response=result)
            return web.json_response(
                {
                    "error": "No image data in upscale response",
                    "keys": list(result.keys()),
                },
                status=500,
            )

        logger.info("Upscale successful", upscaled_len=len(upscaled_b64))

        original_metadata = image_storage.get_metadata(original_filename) or {}
        logger.info(
            "Original metadata", filename=original_filename, metadata=original_metadata
        )
        upscaled_metadata = {
            **original_metadata,
            "type": "upscaled",
            "upscale_mode": upscale_mode,
        }
        logger.info("Upscaled metadata before save", metadata=upscaled_metadata)
        upscaled_filename = image_storage.save_image(
            upscaled_b64,
            upscaled_metadata,
            base_filename=original_filename,
            suffix="upscaled",
        )

        logger.info(
            "Saved images", original=original_filename, upscaled=upscaled_filename
        )

        return web.json_response(
            {
                "image": upscaled_b64,
                "upscaled": True,
                "original_filename": original_filename,
                "upscaled_filename": upscaled_filename,
            }
        )

    except Exception as e:
        logger.error("Upscale failed", error=str(e), exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def handle_health(request: web.Request) -> web.Response:
    async with LemonadeClient() as client:
        available = await client.is_server_available()

    unload_delay = config.get("flux_assistant_unload_delay", 0)
    default_size = config.get("default_size", "512x512")

    return web.json_response(
        {
            "status": "healthy" if available else "unhealthy",
            "server_uri": config.server_uri,
            "storage_dir": config.storage_dir,
            "flux_assistant_unload_delay": unload_delay,
            "default_size": default_size,
        }
    )


async def handle_index(request: web.Request) -> web.Response:
    frontend_path = os.path.join(
        os.path.dirname(__file__), "..", "frontend", "index.html"
    )
    if os.path.exists(frontend_path):
        with open(frontend_path, "r") as f:
            html_content = f.read()
        return web.Response(text=html_content, content_type="text/html")
    return web.Response(text="Frontend not found", status=404)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_post("/prompt-assist", handle_prompt_assist)
    app.router.add_post("/generate", handle_generate)
    app.router.add_get("/models", handle_get_models)
    app.router.add_get("/images", handle_list_images)
    app.router.add_get("/images/metadata", handle_list_images_metadata)
    app.router.add_post("/upscale", handle_upscale)
    app.router.add_get("/images/{filename}/thumb", handle_get_thumbnail)
    app.router.add_get("/images/{filename}", handle_get_image)
    app.router.add_get("/health", handle_health)
    return app


def main():
    parser = argparse.ArgumentParser(description="Diffused Lemon Middleware Server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port to bind to (default: 8080)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Set log level based on flags
    if args.debug:
        os.environ["LM_LOG_LEVEL"] = "DEBUG"
    elif args.verbose:
        os.environ["LM_LOG_LEVEL"] = "INFO"

        # Recreate logger with stream output for debug mode
    if args.debug:
        from .logger import JSONLogger

        log_level = os.environ.get("LM_LOG_LEVEL", "DEBUG")
        logger.logger = JSONLogger(
            config.log_file, log_level, stream_output=True
        ).logger
    else:
        from .logger import JSONLogger

        log_level = os.environ.get("LM_LOG_LEVEL", "INFO")
        logger.logger = JSONLogger(
            config.log_file, log_level, stream_output=False
        ).logger

    web.run_app(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
