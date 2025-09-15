FROM google/shaka-packager:latest
WORKDIR /work
COPY pack.sh /work/pack.sh
COPY app.py /work/app.py
RUN chmod +x /work/pack.sh
EXPOSE 8080
ENV PORT=8080
CMD ["python3", "/work/app.py"]
