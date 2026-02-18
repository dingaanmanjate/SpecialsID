# Use AWS Lambda base image for Python 3.12
FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for Playwright/Chromium
RUN microdnf update -y && microdnf install -y 
    atk 
    cups-libs 
    gtk3 
    libXcomposite 
    libXcursor 
    libXdamage 
    libXext 
    libXi 
    libXrandr 
    libXScrnSaver 
    libXtst 
    pango 
    at-spi2-atk 
    libdrm 
    libgbm 
    libxshmfence 
    libX11 
    libxcb 
    alsa-lib 
    mesa-libgbm 
    nss 
    nspr

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only to save space)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium
RUN chmod -R 777 /ms-playwright

# Copy function code
COPY pnpscrLambda.py ${LAMBDA_TASK_ROOT}

# Set the handler
CMD [ "pnpscrLambda.lambda_handler" ]
