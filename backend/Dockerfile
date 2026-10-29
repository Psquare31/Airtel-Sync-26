FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# opencv (used by the local OCR fallback) needs these shared libs
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
# bake the OCR models into the image instead of downloading them at runtime
RUN python -c "from rapidocr import RapidOCR; import numpy as np; RapidOCR()(np.full((64, 256, 3), 255, np.uint8))"

COPY backend/ .
COPY data/ /srv/data/
ENV DATA_DIR=/srv/data

RUN useradd --create-home app && chown -R app /srv
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
