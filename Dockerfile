FROM public.ecr.aws/docker/library/python:3.13-slim

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 /lambda-adapter /opt/extensions/lambda-adapter

ENV PORT=8000 \
    AWS_LWA_PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/healthz \
    PYTHONUNBUFFERED=1

WORKDIR /var/task

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN DJANGO_DEBUG=False python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["python", "lambda_entrypoint.py"]
