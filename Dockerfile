FROM python:3.10-alpine AS base

RUN mkdir -p /app
WORKDIR /app

FROM base AS build

RUN mkdir /buildroot
RUN apk add gcc make musl-dev
RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install -r requirements.txt --root /buildroot

FROM base

COPY --from=build /buildroot /
COPY . .

ENV TUNNEL_DOMAIN=
ENV SECURE True
EXPOSE 8000

CMD ["uvicorn", "ttun_server:server", "--host", "0.0.0.0", "--port", "8000"]
