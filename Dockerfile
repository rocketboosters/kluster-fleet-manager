FROM python:3.9

WORKDIR /application

COPY pyproject.toml /application/pyproject.toml
COPY README.md /application/README.md

RUN pip install --no-cache-dir poetry \
 && poetry config virtualenvs.create false \
 && poetry install --no-root

COPY manager /application/manager

ENTRYPOINT ["poetry", "run", "kluster_manager"]
CMD ["--help"]
