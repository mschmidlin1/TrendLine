FROM node:22-bookworm AS frontend
WORKDIR /src/frontend
COPY src/dashboard/frontend/package.json src/dashboard/frontend/package-lock.json ./
RUN npm ci
COPY src/dashboard/frontend/ ./
RUN npm run build

FROM python:3.11-bookworm
WORKDIR /app
COPY src/dashboard/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/dashboard/backend/ ./backend
COPY --from=frontend /src/frontend/dist ./backend/static
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
