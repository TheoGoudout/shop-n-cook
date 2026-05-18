#!/bin/sh
set -e
# Inject FRONTEND_URL into the HTML template at container startup.
# Single-quoted variable list limits substitution to only ${FRONTEND_URL},
# leaving any other ${...} patterns in the file untouched.
envsubst '${FRONTEND_URL}' \
  < /usr/share/nginx/html/index.html.template \
  > /usr/share/nginx/html/index.html
