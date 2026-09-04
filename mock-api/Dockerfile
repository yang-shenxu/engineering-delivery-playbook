# mock-api 服务镜像
# 用途一：docker compose 一键起模拟数据接口（FastAPI :8018）
# 用途二：被 compose 的 verify 一次性服务复用（挂载仓库源码跑三件套测试）
#
# 国内网络可指定 PyPI 镜像加速构建：
#   docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

FROM python:3.11-slim

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL}

WORKDIR /app

# 运行依赖 fastapi/uvicorn；pytest/httpx/pyyaml 供 verify 复用（report_tool 依赖 yaml）
COPY requirements.txt .
RUN pip install -r requirements.txt pyyaml

COPY data.py query_engine.py main.py ./

EXPOSE 8018

HEALTHCHECK --interval=5s --timeout=3s --retries=12 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8018/health', timeout=2)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8018"]
