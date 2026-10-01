FROM php:8.3-apache
COPY . /var/www/html/
RUN a2enmod rewrite
ENV KMRL_BACKEND_URL=http://load_balancer_api:8000
EXPOSE 80
