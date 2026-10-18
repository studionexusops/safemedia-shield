FROM pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV MODEL_DIR=/app/models
ENV HF_HOME=/app/hf_cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    libwebp-dev \
    libjpeg-dev \
    zlib1g-dev \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    python -c "import torch, numpy as np; assert torch.from_numpy(np.zeros((2,2))).shape == (2,2)"

# Pre-download Big-LaMa and Florence-2 weights via pure HTTP (no GPU/QEMU needed at build time)
RUN mkdir -p /app/models /app/hf_cache && \
    curl -L "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt" -o /app/models/big-lama.pt && \
    huggingface-cli download microsoft/Florence-2-base

COPY handler.py /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
