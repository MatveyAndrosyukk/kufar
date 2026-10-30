FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Europe/Minsk
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
COPY app/ /app/
COPY flats/ /flats/
COPY deploy/flats_check.py /flats_check.py
WORKDIR /app
VOLUME /data
CMD ["python", "main.py"]
