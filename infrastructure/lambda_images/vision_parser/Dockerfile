# Use AWS Lambda base image for Python 3.12
FROM public.ecr.aws/lambda/python:3.12

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY pnp-vision-parserLambda.py ${LAMBDA_TASK_ROOT}

# Set the handler
CMD [ "pnp-vision-parserLambda.lambda_handler" ]
