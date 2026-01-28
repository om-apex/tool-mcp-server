FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

# Copy demo data
COPY data/demo/ data/demo/

EXPOSE 8000

CMD ["om-apex-mcp-http"]
