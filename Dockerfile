# ytauto render environment — everything needed to make finished videos, CPU only (no GPU required):
#   video: ffmpeg · Remotion (React + headless Chromium) · Blender · Lottie
#   graphics: Inkscape · ImageMagick · potrace · librsvg · rembg (background removal)
#   voice: Qwen3-TTS · Chatterbox · Kokoro · Piper · Edge · eSpeak · faster-whisper word alignment
#   audio: sox · numpy sound design
# Used by GitHub Actions, GitHub Codespaces and locally:
#   docker build -t ytauto .
#   docker run --rm -v "$PWD:/work" ytauto python -m ytauto render projects/example
FROM node:22-bookworm-slim

ARG INSTALL_BLENDER=true
ARG BLENDER_VERSION=4.2.3
ARG PIPER_VOICE=en_US-lessac-medium
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/opt/blender:$PATH \
    YTAUTO_PIPER_DIR=/opt/piper \
    YTAUTO_REMOTION_DIR=/opt/ytauto/remotion \
    YTAUTO_WHISPER_DIR=/opt/whisper \
    U2NET_HOME=/opt/u2net

# System packages: ffmpeg (with libass for captions), Python, fonts, espeak-ng fallback voice,
# Chromium runtime libs for Remotion, and X/GL libs Blender needs even when headless.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg python3 python3-venv python3-pip espeak-ng sox \
      inkscape imagemagick potrace librsvg2-bin \
      fonts-dejavu-core fonts-inter fonts-noto-core fonts-noto-color-emoji fontconfig \
      ca-certificates curl xz-utils git \
      libnss3 libdbus-1-3 libatk1.0-0 libgbm1 libasound2 libxrandr2 libxkbcommon0 libxfixes3 \
      libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
      libxi6 libxxf86vm1 libxrender1 libgl1 libegl1 libgl1-mesa-dri libegl-mesa0 libsm6 libice6 libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# Blender (official build — includes OpenImageDenoise for clean CPU renders).
RUN if [ "$INSTALL_BLENDER" = "true" ]; then \
      MAJOR=$(echo "$BLENDER_VERSION" | cut -d. -f1,2) && \
      curl -fsSL "https://download.blender.org/release/Blender${MAJOR}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
        | tar -xJ -C /opt && mv /opt/blender-${BLENDER_VERSION}-linux-x64 /opt/blender && \
      blender --version | head -1; \
    fi

# Python dependencies.
COPY requirements.txt /opt/ytauto/requirements.txt
RUN python3 -m venv $VIRTUAL_ENV && pip install --no-cache-dir -r /opt/ytauto/requirements.txt

# Remotion templates + headless Chromium.
COPY remotion/package.json /opt/ytauto/remotion/package.json
RUN cd /opt/ytauto/remotion && npm install --no-audit --no-fund && npx remotion browser ensure \
    && mkdir -p node_modules/.cache && chmod -R a+rwX node_modules/.cache && chmod a+rwx . \
    && chmod -R a+rX /opt/ytauto/remotion
COPY remotion/ /opt/ytauto/remotion/

# Kokoro voice model (Apache 2.0): the default free narrator. ~350 MB, downloaded once into the image.
ENV YTAUTO_KOKORO_DIR=/opt/kokoro
RUN mkdir -p /opt/kokoro && cd /opt/kokoro \
    && curl -fsSL -o kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx \
    && curl -fsSL -o voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin \
    && chmod -R a+rX /opt/kokoro

# Word-alignment model (faster-whisper base.en, MIT) and background-removal model (rembg isnet, Apache 2.0).
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8', download_root='/opt/whisper')" \
    && python3 -c "from rembg import new_session; new_session('isnet-general-use')" \
    && chmod -R a+rX /opt/whisper /opt/u2net

# Natural open-source narrators, each in its own environment (their dependencies conflict), CPU builds of PyTorch.
# Models (~2-4 GB each) download from Hugging Face on first use and are cached between runs (HF_HOME).
#   Qwen3-TTS (Apache 2.0): very natural, plain-English direction per sentence, voice design + cloning.
#   Chatterbox (MIT): expressive, fast "turbo" model, voice cloning.
ARG INSTALL_QWEN=true
ARG INSTALL_CHATTERBOX=true
RUN if [ "$INSTALL_QWEN" = "true" ]; then \
      python3 -m venv /opt/tts-qwen && \
      /opt/tts-qwen/bin/pip install --no-cache-dir -U pip && \
      /opt/tts-qwen/bin/pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple torch torchaudio && \
      /opt/tts-qwen/bin/pip install --no-cache-dir qwen-tts soundfile; \
    fi
RUN if [ "$INSTALL_CHATTERBOX" = "true" ]; then \
      python3 -m venv /opt/tts-chatterbox && \
      /opt/tts-chatterbox/bin/pip install --no-cache-dir -U pip && \
      /opt/tts-chatterbox/bin/pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        chatterbox-tts "setuptools<81"; \
    fi

# Pre-download an offline Piper voice so renders work without any TTS network access.
COPY ytauto/ /opt/ytauto/ytauto/
RUN mkdir -p /opt/piper && if [ -n "$PIPER_VOICE" ]; then cd /opt/ytauto && \
      python3 -c "from ytauto.tts import ensure_piper_voice; ensure_piper_voice('${PIPER_VOICE}')"; fi \
    && chmod -R a+rX /opt/piper

COPY . /opt/ytauto
# ytauto stages images/footage/Lottie files into remotion/public at render time (runs as a non-root user in CI).
RUN mkdir -p /opt/ytauto/remotion/public && chmod a+rwx /opt/ytauto/remotion /opt/ytauto/remotion/public \
    && python3 -m ytauto doctor || true
WORKDIR /work
ENV HOME=/tmp
CMD ["python", "-m", "ytauto", "doctor"]
