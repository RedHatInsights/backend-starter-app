# Use ubi9 image for our python distribution
FROM registry.access.redhat.com/ubi9/python-39

# Install net-tools for netstat and ifconfig, which are useful for troubleshooting
USER root
RUN yum install net-tools -y

# Install requirements for app
COPY requirements.txt /
RUN pip install -r /requirements.txt
COPY . /

# Run app
CMD python /run_app.py
