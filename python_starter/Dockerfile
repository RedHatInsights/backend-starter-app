# Use ubi8 image for our python distribution
FROM registry.access.redhat.com/ubi8/python-38

# Install net-tools for netstat and ifconfig, which are useful for troubleshooting
USER root
RUN yum install net-tools -y

# Install requirements for app
COPY requirements.txt /
RUN pip install -r /requirements.txt
COPY . /

# Run app
CMD python /run_app.py
