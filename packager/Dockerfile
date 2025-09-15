FROM google/shaka-packager:latest
WORKDIR /work
COPY pack.sh /work/pack.sh
COPY app.py /work/app.py
RUN chmod +x /work/pack.sh && \
    bash -lc 'which apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/* || true' && \
    python3 -m pip install --no-cache-dir flask
EXPOSE 8080
ENV PORT=8080
CMD ["python3", "/work/app.py"]
