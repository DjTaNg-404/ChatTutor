FROM python:3.11-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY docker/requirements.txt /tmp/requirements.txt

RUN python -m pip install --upgrade pip \
    && pip install --index-url "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" -r /tmp/requirements.txt

COPY app ./app

RUN mkdir -p memory/sessions memory/notes kg_output .cache/huggingface

EXPOSE 8000
