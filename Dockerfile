FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY ui.py .
COPY templates/ templates/
COPY static/ static/

RUN pip install --no-cache-dir ".[ui]"

RUN mkdir -p /data/screenshots /data/pdfs /data/videos /data/images

ENV CURIOSITY_DB=/data/curiosity.db
EXPOSE 8080

CMD ["curiosity", "serve", "--host", "0.0.0.0"]
