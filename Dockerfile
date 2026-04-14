FROM python:3.12-slim-bookworm AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ patchelf \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --upgrade pip setuptools wheel \
    && pip install . pyinstaller \
    && pyinstaller --clean --noconfirm cc-py.spec

FROM scratch AS export
COPY --from=build /src/dist/ /dist/