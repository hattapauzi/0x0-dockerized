FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	libmagic1 \
	libmagic-dev \
	libpq-dev \
	&& rm -rf /var/lib/apt/lists/* \
	&& (getent group www-data >/dev/null || groupadd --gid 82 www-data) \
	&& (id -u www-data >/dev/null 2>&1 || useradd --uid 82 --gid www-data --shell /bin/false --create-home www-data)

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app

RUN chown -R www-data:www-data /app

EXPOSE 8080

# Run migrations as root, then switch to www-data for uWSGI
CMD ["sh", "-c", "flask db upgrade && uwsgi --http-socket 0.0.0.0:8080 --wsgi-file fhost.py --callable app --processes 4 --threads 2 --uid 82 --gid 82"]
