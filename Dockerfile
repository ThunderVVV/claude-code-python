FROM registry.access.redhat.com/ubi8/python-312:latest AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src

COPY . .

RUN pip install --upgrade pip setuptools wheel \
    && pip install . pyinstaller \
    && pyinstaller --clean --noconfirm cc-py.spec

FROM registry.access.redhat.com/ubi8/python-312:latest AS test
WORKDIR /test

COPY --from=build /src/dist/cc-py /test/cc-py

RUN chmod +x /test/cc-py \
    && /test/cc-py --help

FROM scratch AS export
COPY --from=build /src/dist/cc-py /cc-py