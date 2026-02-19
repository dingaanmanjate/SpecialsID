# Use AWS Lambda base image for Python 3.12
FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for Poppler (PDF conversion)
RUN microdnf update -y && microdnf install -y poppler-utils

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY gen_pdf_imgLambda.py ${LAMBDA_TASK_ROOT}

# Set the handler
CMD [ "gen_pdf_imgLambda.lambda_handler" ]
