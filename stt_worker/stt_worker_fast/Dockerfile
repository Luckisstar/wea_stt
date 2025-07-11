FROM python:3.10-slim-buster

WORKDIR /app

# Copy the entire stt_worker directory into the container
COPY ./stt_worker ./stt_worker

# Copy requirements.txt from the specific worker directory and install
COPY ./stt_worker/stt_worker_fast/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "./stt_worker/stt_worker_fast/worker.py"]