FROM node:22-slim AS frontend

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Vite inlines env vars at build time, so the Kakao key has to be present here
# rather than injected as a runtime secret. It ends up in the client bundle
# either way -- that is what a Kakao JS key is; the origin allowlist in the
# Kakao console is the control, not secrecy.
ARG VITE_KAKAO_MAP_KEY
ENV VITE_KAKAO_MAP_KEY=$VITE_KAKAO_MAP_KEY
RUN npm run build


FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md constraints.txt ./
COPY src/ ./src/

RUN pip install --no-cache-dir -c constraints.txt .

# api/data.py reads these at startup and raises CorridorDataUnavailable without
# them. They are no longer committed, so this copies whatever the build context
# has: build them first (scripts/build_processed.py, or scripts/build_smoke_data.py
# for a smoke test) and the image carries them. Build from a clean checkout and
# the directory is empty -- the app still starts and /health answers, while the
# data routes return 503 until a data/processed/ volume is mounted (issue #141).
COPY data/processed/ ./data/processed/

# main.py serves this at / when the directory exists.
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["uvicorn", "stationcast.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
