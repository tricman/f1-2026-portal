FROM python:3.11-slim

WORKDIR /app

# Install Pillow dependencies for F1 TV Dark-Mode PNG table rendering and git for GitOps Portal updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir Pillow

COPY . /app

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "-m", "src.cloud_server"]

