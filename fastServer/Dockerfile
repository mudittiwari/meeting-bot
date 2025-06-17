FROM python:3.10-slim

WORKDIR /app

COPY . /app/
COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt
COPY start.sh .
RUN chmod +x start.sh
CMD ["./start.sh"]

# CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7000"]