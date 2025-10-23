FROM python:3.12-slim
WORKDIR /srv
ADD ./scanner/requirements.txt /srv/requirements.txt
RUN pip install -r requirements.txt 
ADD ./scanner/*.py /srv/
ENV PYTHONUNBUFFERED=1
CMD python -u /srv/scanner/scanner.py
#CMD python /srv/run.py

