# Diffused Lemon - Design Document

## Overview

A 3-layer architecture for AI image generation:
1. **Backend**: Lemonade server (OpenAI-compatible)
2. **Middleware**: Python service to orchestrate requests and storage
3. **Frontend**: Single-file HTML/JS UI with mobile/desktop support

---

## Layer 1: Backend (Lemonade Server)

### API Endpoints Used

- **GET `/api/v1/models`** - List available image generation models
- **POST `/api/v1/images/generations`** - Generate images from text prompts
- **POST `/api/v1/chat/completions`** - Expand prompts using fluxassistant model

### Prompt Expansion Workflow

1. User enters simple prompt (e.g., "mountain landscape")
2. Frontend sends to fluxassistant via `/api/v1/chat/completions`
3. Fluxassistant returns expanded prompt (e.g., "A serene mountain landscape at sunset with pine trees reflecting in a calm lake, cinematic lighting, 8k resolution")
4. User can edit the expanded prompt before generating image

### Request Format (Chat Completions)
```json
{
  "model": "fluxassistant",
  "messages": [
    {
      "role": "user",
      "content": "Expand this prompt for image generation: mountain landscape"
    }
  ],
  "stream": false
}
```

### Response Format
```json
{
  "id": "0",
  "object": "chat.completion",
  "created": 1742927481,
  "model": "fluxassistant",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "A serene mountain landscape at sunset with pine trees reflecting in a calm lake, cinematic lighting, 8k resolution"
    },
    "finish_reason": "stop"
  }]
}
```

### Request Format (Image Generation)
```json
{
  "model": "SD-Turbo",
  "prompt": "A serene mountain landscape at sunset...",
  "size": "512x512",
  "steps": 4,
  "seed": 12345,
  "response_format": "b64_json"
}
```

### Response Format
```json
{
  "created": 1712345678,
  "data": [
    {
      "b64_json": "base64-encoded-image-data"
    }
  ]
}
```

---

## Layer 2: Middleware (Python)

### Configuration (JSON/Environment Variables)

```json
{
  "server_uri": "http://localhost:8000",
  "storage_dir": "/path/to/storage",
  "log_file": "/path/to/logs.json",
  "log_level": "INFO",
  "auth_token": "optional-api-key",
  "default_model": "SD-Turbo",
  "default_size": "512x512",
  "prompt_assist_model": "fluxassistant",
  "prompt_assist_system_prompt": "Expand the user's simple image generation prompt into a detailed, descriptive prompt that would help generate a more interesting image. Keep it concise but evocative."
}
```

### Environment Variables
- `LM_SERVER_URI` - Backend server URL
- `LM_STORAGE_DIR` - Image storage directory
- `LM_LOG_FILE` - Log file path
- `LM_AUTH_TOKEN` - API authentication token
- `LM_DEFAULT_MODEL` - Default image generation model
- `LM_DEFAULT_SIZE` - Default image size
- `LM_PROMPT_ASSIST_MODEL` - Model for prompt expansion
- `LM_PROMPT_ASSIST_SYSTEM_PROMPT` - System prompt for expansion

### Workflow

#### Prompt Assist Flow
1. Receive prompt assist request with simple prompt
2. Send to fluxassistant model via `/api/v1/chat/completions`
3. Extract expanded text from response
4. Return expanded prompt to frontend
5. Frontend displays in editable field for user review

#### Image Generation Flow
1. Receive image generation request (POST `/generate`)
2. Validate required parameters (model, prompt, size, steps, seed)
3. Dispatch to Lemonade server with:
   - Expanded prompt (or user's final prompt if no assist used)
   - Selected model
   - Image size, steps, seed
   - Authentication headers (if configured)
4. On success:
   - Decode base64 image data
   - Save image as PNG to storage directory
   - Save metadata (prompt, timestamp, model, seed, steps, size) as JSON
   - Return image to frontend
5. On error:
   - Log error details
   - Return error message to frontend

### Storage Structure
```
storage_dir/
├── images/
│   ├── 2024-04-01_12-30-45.png
│   └── 2024-04-01_13-15-22.png
└── metadata/
    ├── 2024-04-01_12-30-45.json
    └── 2024-04-01_13-15-22.json
```

### Metadata Format
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

---

## Layer 3: Frontend (Single HTML File)

### Technologies
- Vanilla JavaScript (ES6+)
- CSS Flexbox/Grid for responsive layout
- Base64 image rendering

### UI Components

#### 1. Model Selector
- Populated from `/api/v1/models` endpoint
- Filters models with "image" label
- Default selection from config

#### 2. Prompt Assist Button
- Separate from image generation
- Click to expand simple prompt using fluxassistant
- Opens expanded prompt in editable field

#### 3. Text Entry Field (Prompt)
- Multi-line textarea for prompt
- Shows expanded prompt after "Prompt Assist"
- User can edit expanded prompt before generating
- Character limit indicator

#### 4. Advanced Parameters (Always Visible)
- **Size dropdown**: 256x256, 512x512, 768x768, 1024x1024
- **Steps slider**: 4-50 (with label showing current value)
- **Seed input**: Number field (auto-generate or manual)

#### 5. Image Display Area
- Responsive container
- Shows generated image (base64)
- Loading spinner during generation
- Error message on failure
- Download button

#### 6. Thumbnail Grid (Image History)
- Scrollable grid of past images
- Click thumbnail to view full image
- Hover shows prompt preview
- Right-click menu: view metadata, regenerate with same seed, regenerate with new seed

### Responsive Design

**Desktop (> 768px)**
- Sidebar with model selector and prompt assist button
- Main content area with prompt, parameters, and image
- Thumbnail grid on side or below main content

**Mobile (≤ 768px)**
- Stack all elements vertically
- Full-width thumbnail grid
- Collapsible history section
- Compact parameter controls

### Single File Packaging

All JavaScript and CSS inlined in HTML:
```html
<!DOCTYPE html>
<html>
<head>
  <style>/* All CSS here */</style>
</head>
<body>
  <!-- All UI elements -->
  <script>
    // All JavaScript here
  </script>
</body>
</html>
```

---

## Data Flow

### Prompt Assist Flow
```
User → Frontend → Middleware → Lemonade Server (fluxassistant) → Middleware → Frontend
```

1. User clicks "Prompt Assist" button
2. Frontend sends simple prompt to middleware (POST `/prompt-assist`)
3. Middleware forwards to fluxassistant via `/api/v1/chat/completions`
4. Fluxassistant returns expanded prompt
5. Middleware returns expanded prompt to frontend
6. Frontend displays in editable text field

### Image Generation Flow
```
User → Frontend → Middleware → Lemonade Server → Middleware → Frontend → User
```

1. User enters/finalizes prompt and sets parameters
2. Frontend sends request to middleware (POST `/generate`)
3. Middleware validates parameters
4. Middleware forwards to Lemonade server
5. Lemonade server generates image and returns base64 data
6. Middleware saves PNG to storage + JSON metadata
7. Middleware returns image data to frontend
8. Frontend displays image and adds to thumbnail grid

---

## Implementation Tasks

### Phase 1: Middleware Setup
- [ ] Create config system (JSON + environment variables)
- [ ] Set up logging (JSON format)
- [ ] Implement Lemonade server client (models, chat, images endpoints)
- [ ] Create image storage system

### Phase 2: Middleware API
- [ ] Create `/prompt-assist` endpoint
- [ ] Create `/generate` endpoint
- [ ] Implement error handling
- [ ] Add health check endpoint

### Phase 3: Frontend UI
- [ ] Model selector component
- [ ] Prompt Assist button
- [ ] Prompt input field (expandable)
- [ ] Advanced parameters controls (size, steps, seed)
- [ ] Image display area with download
- [ ] Thumbnail grid for history

### Phase 4: Integration
- [ ] Connect frontend to middleware
- [ ] Implement loading states
- [ ] Test responsive layout
- [ ] Add error handling UI

### Phase 5: Polish
- [ ] Optimize image storage
- [ ] Add image filtering/sorting
- [ ] Performance testing
- [ ] Documentation

---

## Future Enhancements

- [ ] Image editing (crop, resize)
- [ ] Batch generation with multiple seeds
- [ ] Webhook notifications
- [ ] REST API for batch operations
- [ ] Docker containerization
- [ ] Image metadata editing
- [ ] Prompt history/autosave
- [ ] Export gallery as HTML page

## License

This project is in the **Public Domain**.
