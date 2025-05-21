#!/bin/bash

SSL_KEY_PATH="${SSL_KEY_PATH:-certs/out/server.key}"
SSL_CERT_PATH="${SSL_CERT_PATH:-certs/out/server.crt}"
SSL_CA_PATH="${SSL_CA_PATH:-certs/out/ca.crt}"

uvicorn \
  --factory app.main:create_app \
  --host 0.0.0.0 \
  --port 443 \
  --ssl-keyfile ${SSL_KEY_PATH} \
  --ssl-certfile ${SSL_CERT_PATH} \
  --ssl-ca-certs ${SSL_CA_PATH} \
  --ssl-cert-reqs 1 \
  --reload
