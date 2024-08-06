ARG LAMBDA_TASK_ROOT="/usr/src/app"

FROM python:3.10

RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    python3-dev 

ARG LAMBDA_TASK_ROOT
WORKDIR ${LAMBDA_TASK_ROOT}

ADD ./app ${LAMBDA_TASK_ROOT}
ADD ./assets ${LAMBDA_TASK_ROOT}/assets
ADD requirements.txt ${LAMBDA_TASK_ROOT}

RUN pip3 install  --no-cache-dir awslambdaric --target ${LAMBDA_TASK_ROOT} 

ENV GRADIO_SERVER_NAME="0.0.0.0"

ARG GRADIO_SERVER_PORT=7860
ENV GRADIO_SERVER_PORT=${GRADIO_SERVER_PORT}
EXPOSE ${GRADIO_SERVER_PORT}

RUN pip3 install --no-cache-dir --upgrade -r requirements.txt  --target ${LAMBDA_TASK_ROOT} 

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD [ "main.handler" ]


