FROM python:3.13-slim

WORKDIR /app

COPY mcp_servers/search.requirements.txt .
RUN pip install --no-cache-dir -r search.requirements.txt

COPY mcp_servers/search_server.py .

ENV SEARCH_MCP_HOST=0.0.0.0
EXPOSE 8100

CMD ["python", "search_server.py"]
