FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	libmagic1 \
	libmagic-dev \
	libpq-dev \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
EXPOSE 8080

CMD ["sh", "-c", "flask db upgrade && uwsgi --http-socket 0.0.0.0:8080 --wsgi-file fhost.py --callable app --processes 4 --threads 2"]
