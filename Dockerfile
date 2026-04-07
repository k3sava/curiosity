FROM python:3.12-slim
WORKDIR /app

COPY . .
RUN pip install --no-cache-dir ".[ui]"
RUN mkdir -p /data/screenshots /data/pdfs /data/videos /data/images

ENV CURIOSITY_DB=/data/curiosity.db
EXPOSE 8080

CMD ["python3", "ui.py", "--host", "0.0.0.0"]
