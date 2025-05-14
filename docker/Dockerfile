ARG PYTHON_VERSION=3.11
ARG CUDA_PYTORCH_TAG=cu118  # Ví dụ: cu118 cho CUDA 11.8, cu121 cho CUDA 12.1, hoặc cpu
ARG TORCH_VERSION=2.1.2
ARG TORCHVISION_VERSION=0.16.2
ARG TORCHAUDIO_VERSION=2.1.2

FROM python:${PYTHON_VERSION}-slim-bullseye

ARG CUDA_PYTORCH_TAG
ARG TORCH_VERSION
ARG TORCHVISION_VERSION
ARG TORCHAUDIO_VERSION

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1
ENV APP_HOME=/app_code

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    git \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR ${APP_HOME}

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir \
    torch==${TORCH_VERSION} torchvision==${TORCHVISION_VERSION} torchaudio==${TORCHAUDIO_VERSION} \
    --index-url https://download.pytorch.org/whl/${CUDA_PYTORCH_TAG}

RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ${APP_HOME}/app
COPY ./run.py ${APP_HOME}/run.py 

RUN mkdir -p ${APP_HOME}/model && mkdir -p ${APP_HOME}/output
RUN useradd --system --create-home --home-dir ${APP_HOME} --shell /bin/bash --user-group appuser
RUN chown -R appuser:appuser ${APP_HOME}

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "app.api:app"]