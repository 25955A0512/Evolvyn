FROM python:3.12.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY mcp-service/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && useradd --create-home --uid 10001 mcpuser
COPY backend/mcp_utilities.py backend/custom_mcp.py ./backend/
USER mcpuser
EXPOSE 8071
CMD ["python", "-m", "backend.custom_mcp"]
