FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# WITH_OCR=true adds the local OCR fallback (needs ~500 MB RAM at peak, so off for 512 MB hosts)
ARG WITH_OCR=false

WORKDIR /srv/backend
COPY backend/requirements.txt backend/requirements-ocr.txt ./
RUN pip install -r requirements.txt
RUN if [ "$WITH_OCR" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
      && rm -rf /var/lib/apt/lists/* \
      && pip install -r requirements-ocr.txt \
      && python -c "from rapidocr import RapidOCR; import numpy as np; RapidOCR()(np.full((64, 256, 3), 255, np.uint8))"; \
    fi

COPY backend/ .
COPY data/ /srv/data/
ENV DATA_DIR=/srv/data

RUN useradd --create-home app && chown -R app /srv
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
