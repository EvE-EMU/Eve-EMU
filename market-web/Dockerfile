FROM nginx:1.27-alpine

COPY market-web/nginx.conf /etc/nginx/conf.d/default.conf
COPY market-web/public /usr/share/nginx/html

EXPOSE 8088
