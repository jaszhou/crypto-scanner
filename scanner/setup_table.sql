docker run -it postgres:15 psql -h localhost -U crypto_user -d crypto_db -f postgres_schema.sql

docker run -it --rm postgres:15 psql -h localhost -U crypto_user -d crypto_db -f postgres_schema.sql
