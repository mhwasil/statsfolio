FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3000

ENV HOST=0.0.0.0 PORT=3000 BASE_URL=/

COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
