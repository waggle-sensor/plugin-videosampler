FROM waggle/plugin-base:1.1.1-base
LABEL version="0.1.0" \
      description="Video sampler"

RUN apt-get update \
  && apt-get install -y \
  ffmpeg \
  && rm -rf /var/lib/apt/lists/*

# COPY app.py /app/
COPY record.py requirements.txt /app/
RUN pip3 install --no-cache-dir --upgrade -r /app/requirements.txt

ENTRYPOINT ["python3", "-u", "/app/record.py"]