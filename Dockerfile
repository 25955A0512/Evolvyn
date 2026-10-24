FROM python:3.12.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY backend ./backend
COPY sample-data ./sample-data
COPY scripts/container_start.py scripts/verify_local_model.py ./
RUN useradd --create-home --uid 10001 evolvyn && chown -R evolvyn:evolvyn /app
USER evolvyn
EXPOSE 8000
CMD ["python", "container_start.py"]
