// Configuration - use relative URL to work from any host
const MIDDLEWARE_URL = window.location.origin;

// State
let models = [];
let currentImage = null;
let currentImageFilenames = null;
let currentMetadata = null;
let imageOffset = 0;
const IMAGE_BATCH_SIZE = 50;
let isLoadingMore = false;

// DOM Elements
const els = {
    statusIndicator: document.getElementById('statusIndicator'),
    statusText: document.getElementById('statusText'),
    modelInfo: document.getElementById('modelInfo'),
    modelSelect: document.getElementById('modelSelect'),
    promptInput: document.getElementById('promptInput'),
    promptAssistBtn: document.getElementById('promptAssistBtn'),
    generateBtn: document.getElementById('generateBtn'),
    errorMessage: document.getElementById('errorMessage'),
    heightSelect: document.getElementById('heightSelect'),
    widthSelect: document.getElementById('widthSelect'),
    stepsDropdown: document.getElementById('stepsDropdown'),
    seedInput: document.getElementById('seedInput'),
    randomSeedBtn: document.getElementById('randomSeedBtn'),
    placeholderText: document.getElementById('placeholderText'),
    generatedImage: document.getElementById('generatedImage'),
    spinner: document.getElementById('spinner'),
    imageInfo: document.getElementById('imageInfo'),
    downloadBtn: document.getElementById('downloadBtn'),
    historyGrid: document.getElementById('historyGrid'),
    loadingMore: document.getElementById('loadingMore'),
    scrollSentinel: document.getElementById('scrollSentinel'),
    unloadModelBtn: document.getElementById('unloadModelBtn'),
    cfgInput: document.getElementById('cfgInput'),
}

// Utility Functions
function generateRandomSeed() {
    return Math.floor(Math.random() * 2147483647);
}

function showLoading(show) {
    if (show) {
        els.placeholderText.style.display = 'none';
        els.generatedImage.style.display = 'none';
        els.spinner.style.display = 'block';
        els.generateBtn.disabled = true;
        els.promptAssistBtn.disabled = true;
    } else {
        els.placeholderText.style.display = 'block';
        els.spinner.style.display = 'none';
        els.generateBtn.disabled = false;
        els.promptAssistBtn.disabled = false;
    }
}

function showError(message) {
    els.errorMessage.textContent = message;
    els.errorMessage.classList.add('visible');
    setTimeout(() => {
        els.errorMessage.classList.remove('visible');
    }, 5000);
}

function clearError() {
    els.errorMessage.classList.remove('visible');
}

let serverConfig = null;

async function checkServerStatus() {
    try {
        const response = await fetch(`${MIDDLEWARE_URL}/v1/health`);
        if (response.ok) {
            serverConfig = await response.json();
            const isHealthy = serverConfig.status === 'healthy';
            els.statusIndicator.classList.toggle('connected', isHealthy);
            els.statusText.textContent = isHealthy ? 'Connected' : 'Disconnected';
            if (serverConfig?.server_uri) {
                try {
                    const url = new URL(serverConfig.server_uri);
                    document.getElementById('serverInfo').textContent = `Backend: ${url.hostname} (${isHealthy ? 'OK' : 'Offline'})`;
                } catch {
                    document.getElementById('serverInfo').textContent = `Backend: ${serverConfig.server_uri} (${isHealthy ? 'OK' : 'Offline'})`;
                }
            }

            // Update model info in status bar
            if (serverConfig?.loaded_models && serverConfig.loaded_models.length > 0) {
                const modelCount = serverConfig.loaded_models.length;
                const modelNames = serverConfig.loaded_models.slice(0, 3).join(', ');
                const modelText = modelCount === 1 ? `1 model: ${modelNames}` : `${modelCount} models: ${modelNames}${modelCount > 3 ? '...' : ''}`;
                els.modelInfo.textContent = modelText;
                els.modelInfo.style.display = 'block';
            } else {
                els.modelInfo.textContent = 'No models loaded';
                els.modelInfo.style.display = 'block';
            }
            return isHealthy;
        }
    } catch (error) {
        els.statusIndicator.classList.remove('connected');
        els.statusText.textContent = 'Disconnected';
        console.error('Server status check failed:', error);
        els.modelInfo.textContent = 'Failed to load models';
        els.modelInfo.style.display = 'block';
    }
    return false;
}

async function loadModels() {
    try {
        const response = await fetch(`${MIDDLEWARE_URL}/models`);
        const data = await response.json();

        if (data.models) {
            models = data.models;
            const promptAssistModel = serverConfig?.prompt_assist_model;
            const promptAssistAvailable = promptAssistModel && models.some(m => m.id === promptAssistModel);

            const imageModels = models.filter(m =>
                (m.labels?.includes('image') || m.id?.toLowerCase().includes('sd') || m.id?.toLowerCase().includes('flux')) && m.id !== promptAssistModel
            );

            els.modelSelect.innerHTML = imageModels.length > 0 ?
                imageModels.map(m => `<option value="${m.id}">${m.id}</option>`).join('') :
                '<option value="">No image models found</option>';

            // Set default model from localStorage
            const defaultModel = localStorage.getItem('diffused_lemon_model') || 'SD-Turbo';
            if (imageModels.find(m => m.id === defaultModel)) {
                els.modelSelect.value = defaultModel;
            }

            // Update prompt assist button based on availability
            if (promptAssistAvailable) {
                els.promptAssistBtn.disabled = false;
                els.promptAssistBtn.textContent = '🎨 Prompt Assist';
            } else {
                els.promptAssistBtn.disabled = true;
                els.promptAssistBtn.textContent = 'Prompt Assist Unavailable';
            }
        }
    } catch (error) {
        console.error('Failed to load models:', error);
        els.modelInfo.textContent = 'Failed to load models';
    }
}

async function handlePromptAssist() {
    const prompt = els.promptInput.value.trim();
    if (!prompt) {
        showError('Please enter a prompt first');
        return;
    }

    showLoading(true);
    clearError();

    try {
        const response = await fetch(`${MIDDLEWARE_URL}/prompt-assist`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt
            })
        });

        if (!response.ok) {
            throw new Error('Failed to expand prompt');
        }

        const data = await response.json();

        if (!data.expanded_prompt || !data.original_prompt) {
            throw new Error('Invalid response from prompt assist');
        }

        els.promptInput.value = data.expanded_prompt;
        els.promptInput.classList.add('expanded');
        els.promptInput.dataset.original = data.original_prompt;
        els.promptInput.dataset.promptAssisted = 'true';

        showError('Prompt expanded! You can edit it before generating.');
    } catch (error) {
        showError(error.message);
    } finally {
        showLoading(false);
    }
}

async function handleGenerate() {
    const prompt = els.promptInput.value.trim();
    const model = els.modelSelect.value;
    const height = els.heightSelect.value;
    const width = els.widthSelect.value;
    const size = `${width}x${height}`;
    const steps = els.stepsDropdown.value ? parseInt(els.stepsDropdown.value) : 4;
    let seed = els.seedInput.value.trim();

    if (!prompt) {
        showError('Please enter a prompt');
        return;
    }

    if (!model) {
        showError('Please select a model');
        return;
    }

    if (!seed) {
        seed = generateRandomSeed();
        els.seedInput.value = seed;
    }
    seed = parseInt(seed);

    showLoading(true);
    clearError();

    try {
        const response = await fetch(`${MIDDLEWARE_URL}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt,
                model,
                size,
                steps,
                seed,
                original_prompt: els.promptInput.dataset.original || undefined,
                cfg_scale: els.cfgInput.value ? parseFloat(els.cfgInput.value) : undefined
            })
        });

        if (!response.ok) {
            throw new Error('Failed to generate image');
        }

        const data = await response.json();

        currentMetadata = data.metadata;
        els.promptInput.dataset.promptAssisted = undefined;
        els.promptInput.classList.remove('expanded');
        els.promptInput.dataset.original = undefined;

        els.placeholderText.style.display = 'none';
        els.generatedImage.src = `data:image/png;base64,${data.image}`;
        els.generatedImage.style.display = 'block';
        els.downloadBtn.style.display = 'block';

        currentImage = {
            original: data.image
        };
        currentImageFilenames = {
            original: null
        };

        const date = new Date(data.metadata.timestamp);
        const generationTime = data.metadata.generation_time ? `${data.metadata.generation_time}s` : 'N/A';
        els.imageInfo.innerHTML = `
               <div class="prompt-container"><strong>Prompt:</strong> <span class="prompt-expandable">${data.metadata.prompt.substring(0, 100)}${data.metadata.prompt.length > 100 ? '...' : ''}</span><div class="prompt-full hidden" data-prompt="${data.metadata.prompt.replace(/\\"/g, '&quot;')}"></div></div>
             <p><strong>Model:</strong> ${data.metadata.model}</p>
           <p><strong>Size:</strong> ${data.metadata.size}</p>
           <p><strong>Steps:</strong> ${data.metadata.steps}</p>
           <p><strong>Seed:</strong> ${data.metadata.seed}</p>
           <p><strong>Generated:</strong> ${date.toLocaleString()}</p>
           <p><strong>Generation time:</strong> ${generationTime}</p>
           ${data.metadata.prompt_assisted ? '<p><strong>💡 Prompt was assist expanded</strong></p>' : ''}
         `;

        // Save model preference
        localStorage.setItem('diffused_lemon_model', model);

        // Refresh history
        loadHistory();

    } catch (error) {
        showError(error.message);
    } finally {
        showLoading(false);
        els.placeholderText.style.display = 'none';
    }
}

function loadThumbnail(img) {
    const imgEl = document.createElement('img');
    imgEl.onload = () => {
        const thumbnail = els.historyGrid.querySelector(`[data-filename="${img.filename}"]`);
        if (thumbnail) {
            thumbnail.querySelector('.thumbnail-placeholder').style.display = 'none';
            thumbnail.appendChild(imgEl);
        }
    };
    imgEl.onerror = () => {
        console.error(`Failed to load thumbnail for ${img.filename}`);
    };
    imgEl.src = `${MIDDLEWARE_URL}/images/${img.filename}/thumb`;
}

async function loadHistory() {
    try {
        const response = await fetch(`${MIDDLEWARE_URL}/images/metadata?limit=${IMAGE_BATCH_SIZE}&offset=${imageOffset}`);
        const data = await response.json();

        if (data.images && data.images.length > 0) {
            const existingPlaceholder = els.historyGrid.querySelector('.placeholder');
            if (existingPlaceholder) {
                els.historyGrid.innerHTML = '';
            }

            els.historyGrid.insertAdjacentHTML('beforeend', data.images.map((img) => {
                const date = img.metadata.timestamp ? new Date(img.metadata.timestamp) : new Date();
                const prompt = img.metadata.prompt ? img.metadata.prompt.substring(0, 50) + '...' : 'No prompt';
                const model = img.metadata.model || img.metadata.upscale_mode || 'N/A';
                return `
                <div class="thumbnail" data-filename="${img.filename}" onclick="viewImage(this.dataset.filename)">
                  <div class="thumbnail-placeholder">Loading...</div>
                  <div class="prompt-preview">${prompt}</div>
                  <div class="thumbnail-info">
                    <span>${date.toLocaleDateString()}</span>
                    <span class="model-badge">${model}</span>
                  </div>
                </div>
              `;
            }).join(''));

            data.images.forEach(img => loadThumbnail(img));
        }
    } catch (error) {
        console.error('Failed to load history:', error);
    } finally {
        els.loadingMore.style.display = 'none';
        isLoadingMore = false;
    }
}

async function loadMoreImages() {
    if (isLoadingMore) return;
    isLoadingMore = true;
    els.loadingMore.style.display = 'block';
    imageOffset += IMAGE_BATCH_SIZE;
    await loadHistory();
}

// Infinite scroll observer
const scrollObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !isLoadingMore) {
            loadMoreImages();
        }
    });
}, {
    rootMargin: '200px'
});

// Initialize
async function init() {
    const serverOk = await checkServerStatus();
    await loadModels();
    loadHistory();

    // Set default size from localStorage, then fall back to config
    let defaultSize = null;
    const storedWidth = localStorage.getItem('diffused_lemon_width');
    const storedHeight = localStorage.getItem('diffused_lemon_height');

    if (storedWidth && storedHeight) {
        defaultSize = `${storedWidth}-${storedHeight}`;
    } else if (serverConfig?.default_size) {
        defaultSize = serverConfig.default_size;
        if (defaultSize) {
            const [width, height] = defaultSize.split('-');
            if (els.widthSelect.querySelector(`option[value="${width}"]`)) {
                els.widthSelect.value = width;
            }
            if (els.heightSelect.querySelector(`option[value="${height}"]`)) {
                els.heightSelect.value = height;
            }
        }
    }

    if (!serverOk) {
        showError('Server disconnected. Some features may not work.');
    }

    scrollObserver.observe(els.scrollSentinel);
}

async function viewImage(filename) {
    try {
        const response = await fetch(`${MIDDLEWARE_URL}/images/${filename}`);
        const data = await response.json();

        if (data.image) {
            els.placeholderText.style.display = 'none';
            els.downloadBtn.style.display = 'block';

            const thumbSrc = `${MIDDLEWARE_URL}/images/${filename}/thumb`;
            els.generatedImage.src = thumbSrc;
            els.generatedImage.style.display = 'block';

            await new Promise(resolve => setTimeout(resolve, 100));
            els.generatedImage.src = `data:image/png;base64,${data.image}`;

            currentImage = {
                original: data.image
            };
            currentMetadata = data.metadata;

            const date = data.metadata.timestamp ? new Date(data.metadata.timestamp) : new Date();
            const generationTime = data.metadata.generation_time ? `${data.metadata.generation_time}s` : 'N/A';
            els.imageInfo.innerHTML = `
               <div class="prompt-container"><strong>Prompt:</strong> <span class="prompt-expandable">${(data.metadata.prompt || 'N/A').substring(0, 100)}${(data.metadata.prompt || '').length > 100 ? '...' : ''}</span><div class="prompt-full hidden" data-prompt="${(data.metadata.prompt || 'N/A').replace(/"/g, '&quot;')}"></div></div>
                <p><strong>Model:</strong> ${data.metadata.model || data.metadata.upscale_mode || 'N/A'}</p>
              <p><strong>Size:</strong> ${data.metadata.size}</p>
              <p><strong>Steps:</strong> ${data.metadata.steps}</p>
              <p><strong>Seed:</strong> ${data.metadata.seed}</p>
              <p><strong>Generated:</strong> ${date.toLocaleString()}</p>
              <p><strong>Generation time:</strong> ${generationTime}</p>
 ${data.metadata.prompt_assisted ? "<p><strong>💡 Prompt was assist expanded</strong></p>" : ''}
            `;
        }
    } catch (error) {
        showError('Failed to load image');
    }
}

function downloadImage() {
    if (currentImage && currentMetadata) {
        let link = document.createElement('a');

        if (typeof currentImage === 'object' && currentImageFilenames) {
            let filename = currentImageFilenames.original;
            if (filename) {
                link.href = `${MIDDLEWARE_URL}/images/${filename}`;
                link.download = filename;
                link.click();
                return;
            }
        }

        let imageToDownload = typeof currentImage === 'object' ? currentImage.original : currentImage;
        let downloadFilename = `image_${currentMetadata.timestamp.replace(/[:.]/g, '-').replace(/[\\/\\\\*?<\"|>"\s]/g, '')}.png`;

        link = document.createElement('a');
        link.href = `data:image/png;base64,${imageToDownload}`;
        link.download = downloadFilename;
        link.click();
    }
}

function togglePromptExpand(expandable) {
    const container = expandable.parentElement;
    const fullPrompt = container.querySelector('.prompt-full');

    if (fullPrompt && fullPrompt.classList.contains('prompt-full')) {
        const isHidden = fullPrompt.classList.contains('hidden');

        if (isHidden) {
            fullPrompt.textContent = fullPrompt.dataset.prompt;
            fullPrompt.classList.remove('hidden');
            expandable.style.display = 'none';
        } else {
            fullPrompt.classList.add('hidden');
            expandable.style.display = 'inline';
        }
    }
}

els.promptAssistBtn.addEventListener('click', handlePromptAssist);
els.generateBtn.addEventListener('click', handleGenerate);
els.downloadBtn.addEventListener('click', downloadImage);

document.addEventListener('click', (e) => {
    const expandable = e.target.closest('.prompt-expandable');
    if (expandable) {
        togglePromptExpand(expandable);
    }
});

els.randomSeedBtn.addEventListener('click', () => {
    els.seedInput.value = generateRandomSeed();
});

els.modelSelect.addEventListener('change', () => {
    localStorage.setItem('diffused_lemon_model', els.modelSelect.value);
});

els.widthSelect.addEventListener('change', () => {
    localStorage.setItem('diffused_lemon_width', els.widthSelect.value);
});
els.heightSelect.addEventListener('change', () => {
    localStorage.setItem('diffused_lemon_height', els.heightSelect.value);
});

init();

window.viewImage = viewImage;
