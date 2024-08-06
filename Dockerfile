ARG LAMBDA_TASK_ROOT="/usr/src/app"

FROM python:3.10

ARG LAMBDA_TASK_ROOT
WORKDIR ${LAMBDA_TASK_ROOT}

ADD ./app ${LAMBDA_TASK_ROOT}
ADD ./app/assets ${LAMBDA_TASK_ROOT}/app/assets
ADD requirements.txt ${LAMBDA_TASK_ROOT}
ADD ./vendor/ffmpeg-7.0.1-arm64-static /usr/local/bin/
RUN pip3 install  --no-cache-dir awslambdaric --target ${LAMBDA_TASK_ROOT} 

ENV GRADIO_SERVER_NAME="0.0.0.0"

ARG GRADIO_SERVER_PORT=7860
ENV GRADIO_SERVER_PORT=${GRADIO_SERVER_PORT}
EXPOSE ${GRADIO_SERVER_PORT}

RUN pip3 install --no-cache-dir --upgrade -r requirements.txt  --target ${LAMBDA_TASK_ROOT} 

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
CMD [ "main.handler" ]


