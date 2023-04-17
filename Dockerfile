FROM jupyterhub/jupyterhub:latest

RUN apt-get update && apt-get install -y nano git
RUN pip install jupyter_server notebook python-dotenv

RUN mkdir security && cd security && openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "/C=IT/ST=Italia/L=Genova/O=CoCoA/OU=CoCoA/CN=cocoa@dima.unige.it"

RUN curl "https://cocoa.dima.unige.it/cocoa/download/bin/cocoa-5.4.1p-linux.tgz" -o cocoa.tgz && gunzip -dc cocoa.tgz | tar -xf - -C ./ && rm cocoa.tgz && mv cocoa-5.4 /usr/local/bin/cocoa &&\
    cd /usr/local/bin/cocoa/bin && if ! test -f CoCoAInterpreter ; then cp $(ls | grep without | grep -v grep) CoCoAInterpreter; fi

RUN git clone https://github.com/mpedy/CoCoAKernel.git /srv/jupyterhub/cocoakernel

RUN cd cocoakernel/ && ./install.sh

RUN useradd -mr test
RUN echo test:test | chpasswd

RUN jupyterhub --generate-config \
    && echo 'c.JupyterHub.ssl_cert="security/cert.pem"' >> jupyterhub_config.py \
    && echo 'c.JupyterHub.ssl_key="security/key.pem"' >> jupyterhub_config.py

ENTRYPOINT [ "jupyterhub" ]