FROM python:3.11-bookworm

WORKDIR /app

COPY requirements.txt .
COPY src ./src
COPY resources ./resources
COPY pyproject.toml .

RUN pip install --no-cache-dir -r requirements.txt



ENV PYTHONPATH=/app/src:/app/src/streamlit-dash

EXPOSE 8501
CMD ["streamlit", "run", "src/streamlit-dash/trendline_streamlit.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]


#cd ~/repos/TrendLine
#docker build -f src/streamlit-dash/Dockerfile -t trendline-streamlit .