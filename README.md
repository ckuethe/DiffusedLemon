# Diffused Lemon - AI Image Generator

A 3-layer AI image generation application using Lemonade server.

## Architecture

1. **Backend**: Lemonade server (OpenAI-compatible)
2. **Middleware**: Python service with aiohttp
3. **Frontend**: Single-file HTML/JS

## Setup

### Prerequisites

- Python 3.8+
- Lemonade server running with image generation models (SD-Turbo, SDXL-Turbo, etc.)
- Lemonade server running with `fluxassistant` model for prompt expansion

#### Setting up fluxassistant in Lemonade Server

The prompt expansion feature requires the `fluxassistant` model. Import it from Hugging Face:

1. Open Lemonade Server's web interface
2. Go to **Models** → **Import Model**
3. Use this Hugging Face model: `https://huggingface.co/mradermacher/Llama-3.2-3B-Fluxed-uncensored-GGUF`
4. Name the imported model: `user.fluxassistant`
5. Wait for the model to download and load

Alternatively, use the API:

```bash
curl -X POST http://localhost:8000/api/v1/models/import \
  -H "Content-Type: application/json" \
  -d '{
    "source_url": "https://huggingface.co/mradermacher/Llama-3.2-3B-Fluxed-uncensored-GGUF",
    "model_name": "user.fluxassistant"
  }'
```

### Installation

```bash
# Install middleware dependencies
pip install -r middleware/requirements.txt
```

Environment variables override config.json values. The config.json file is automatically loaded from the `middleware/` directory.

| Variable | Description |
|----------|-------------|
| `LM_SERVER_URI` | Lemonade server URL |
| `LM_STORAGE_DIR` | Image storage directory |
| `LM_LOG_FILE` | Log file path |
| `LM_LOG_LEVEL` | Logging level |
| `LM_AUTH_TOKEN` | API authentication token |
| `LM_DEFAULT_MODEL` | Default image generation model |
| `LM_DEFAULT_SIZE` | Default image size |
| `LM_PROMPT_ASSIST_MODEL` | Model for prompt expansion |
| `LM_PROMPT_ASSIST_SYSTEM_PROMPT` | System prompt for expansion |

## Configuration

Edit `middleware/config.json` or use environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `server_uri` | Lemonade server URL | `http://localhost:8000` |
| `storage_dir` | Image storage directory | `/path/to/storage` |
| `log_file` | Log file path | `/path/to/logs.json` |
| `log_level` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `auth_token` | API authentication token | `null` |
| `default_model` | Default image generation model | `SD-Turbo` |
| `default_size` | Default image size | `512x512` |
| `prompt_assist_model` | Model for prompt expansion | `fluxassistant` |
| `prompt_assist_system_prompt` | System prompt for expansion | See config.json |

### Environment Variables

Environment variables override config.json values:

- `LM_SERVER_URI` - Backend server URL
- `LM_STORAGE_DIR` - Image storage directory
- `LM_LOG_FILE` - Log file path
- `LM_AUTH_TOKEN` - API authentication token
- `LM_DEFAULT_MODEL` - Default image generation model
- `LM_DEFAULT_SIZE` - Default image size
- `LM_PROMPT_ASSIST_MODEL` - Model for prompt expansion
- `LM_PROMPT_ASSIST_SYSTEM_PROMPT` - System prompt for expansion

### Example config.json

```json
{
  "server_uri": "http://localhost:8000",
  "storage_dir": "/home/ckuethe/diffused-lemon/storage",
  "log_file": "/home/ckuethe/diffused-lemon/logs.json",
  "log_level": "INFO",
  "auth_token": null,
  "default_model": "SD-Turbo",
  "default_size": "512x512",
  "prompt_assist_model": "fluxassistant",
  "prompt_assist_system_prompt": "Expand the user's simple image generation prompt into a detailed, descriptive prompt that would help generate a more interesting image. Keep it concise but evocative."
}
```

## Usage

### Basic Workflow

1. Open http://localhost:8080 in your browser (middleware serves the frontend)
2. The UI shows server connection status in the header
3. Select a model from the dropdown (auto-populated from Lemonade server)

### Generating an Image

1. Enter a simple prompt (e.g., "mountain landscape")
2. Click **Prompt Assist** to expand it using fluxassistant
3. Edit the expanded prompt if desired
4. Adjust parameters (size, steps, seed)
5. Click **Generate** to create the image
6. The image appears in the main display area
7. Click **Download** to save the image

### Advanced Features

- **Prompt Assist**: Click to expand simple prompts into detailed descriptions using fluxassistant
- **Image History**: View all previously generated images in the grid below
- **Click thumbnails**: View full-size images from history
- **Random Seed**: Generate random seeds with the dice button
- **Model Preference**: Your selected model is saved to localStorage

### Parameters

- **Model**: Image generation model (SD-Turbo, SDXL-Turbo, etc.)
- **Prompt**: Text description of the image you want to generate
- **Size**: Image dimensions (256x256, 512x512, 768x768, 1024x1024)
- **Steps**: Number of denoising steps (4-50, higher = more detail but slower)
- **Seed**: Random seed for reproducibility (leave empty for random)

## Storage

Images and metadata are stored in:

```
storage/
├── images/      # Generated PNG files
│   └── 2024-04-01_12-30-45.png
└── metadata/    # JSON metadata files
    └── 2024-04-01_12-30-45.json
```

### Metadata Format

Each image has a corresponding JSON file with:

```json
{
  "filename": "2024-04-01_12-30-45.png",
  "prompt": "A serene mountain landscape at sunset...",
  "model": "SD-Turbo",
  "size": "512x512",
  "seed": 12345,
  "steps": 4,
  "cfg_scale": 1.0,
  "timestamp": "2024-04-01T12:30:45Z",
  "prompt_assisted": true,
  "original_prompt": "mountain landscape"
}
```

## API Endpoints

The middleware exposes the following endpoints:

- `GET /` - Main frontend page (HTML)
- `GET /health` - Server health check
- `GET /models` - List available models
- `POST /prompt-assist` - Expand a prompt using fluxassistant
- `POST /generate` - Generate an image
- `GET /images` - List image history (query param: `?limit=50`)
- `GET /images/{filename}` - Get a specific image

## Features

- **Prompt Assist**: Uses fluxassistant to expand simple prompts into detailed descriptions
- **Image History**: View and download previously generated images
- **Responsive UI**: Works on mobile and desktop
- **JSON Logging**: All operations logged in JSON format
- **LocalStorage**: Saves model preference and recent images
- **Base64 Images**: Images displayed directly in browser without intermediate files
- **Single Server**: Frontend served by middleware (relative URLs work from any host)

## Running the Server

The middleware server serves both the API and the frontend UI:

```bash
# From project root
python3 -m middleware.server

# Or
python3 middleware/server.py
```

The server starts on port 8080 by default. Open http://localhost:8080 in your browser.

### Running from another machine

To access the server from another machine on your network, bind to your machine's IP address or `0.0.0.0`:

```bash
# Use your machine's IP (e.g., 192.168.1.100)
python3 middleware/server.py --host 192.168.1.100

# Or bind to all interfaces
python3 middleware/server.py --host 0.0.0.0
```

Then access from another machine: `http://192.168.1.100:8080`

### Debugging

Use the `--verbose` or `--debug` flags for detailed logging:

```bash
# Verbose logging
python3 middleware/server.py --verbose

# Debug logging (most detailed)
python3 middleware/server.py --debug

# Combined with custom host/port
python3 middleware/server.py --host 0.0.0.0 --port 8080 --debug
```

## Troubleshooting

### Server won't start

- Check that Lemonade server is running and accessible
- Verify `server_uri` in config.json points to the correct Lemonade server URL
- Check log file for error messages

### No models found

- Ensure Lemonade server has image generation models loaded
- Check that models have `image` in their labels or `sd`/`flux` in their IDs

### Prompt Assist fails

- Verify that `fluxassistant` model is loaded in Lemonade server
- Check the system prompt configuration in config.json

### Images not saving

- Verify `storage_dir` exists and is writable
- Check that the middleware process has permissions to write to the storage directory

## License

This project is in the **Public Domain**.

I make no claim of copyright to any part of this project. It was generated
using AI prompting with opencode and Qwen3 Coder Next. All code and content
is freely available for any use without restrictions.

## Credits

This section is the only part of this project actually written by me,
@ckuethe. Everything else is the product of AI prompting.

I used [Lemonade](https://github.com/lemonade-sdk/lemonade/) on an AMD
Ryzen AI Max 395; [opencode](https://github.com/anomalyco/opencode/) and
[Qwen3 Coder Next](https://huggingface.co/Qwen/Qwen3-Coder-Next) for code
generation.

Thanks to HAL Heavy Duty on youtube for reminding us to say "Good job,
buddy. Good job." when your machines and tools do what you want.

Thanks to @technigmaai for this
[wiki page](https://github.com/technigmaai/technigmaai-wiki/wiki/AMD-Ryzen-AI-Max--395:-GTT--Memory-Step%E2%80%90by%E2%80%90Step-Instructions-%28Ubuntu-24.04%29) on how to get Strix Halo to use more VRAM than the BIOS would
otherwise allow.

[Vincent Gourbin](https://huggingface.co/VincentGOURBIN/Llama-3.2-3B-Fluxed-Lora-uncensored) and [mradermacher](https://huggingface.co/mradermacher/Llama-3.2-3B-Fluxed-uncensored-GGUF) for the Llama model tuned to elaborate on vague image prompts.

Massive Attack for "Dissolved Girl", and `gemma3-4b-FLM` for deciding
that "Diffused Lemon" would be a good name.
