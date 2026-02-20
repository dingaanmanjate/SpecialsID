FROM public.ecr.aws/lambda/python:3.12

# Install build dependencies for Amazon Linux 2023
RUN microdnf update -y && microdnf install -y gcc-c++ cmake

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY pnp-cleanerLambda.py ${LAMBDA_TASK_ROOT}

CMD [ "pnp-cleanerLambda.lambda_handler" ]
