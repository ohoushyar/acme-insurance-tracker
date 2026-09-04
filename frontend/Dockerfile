FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ARG API_UPSTREAM=api:8000
COPY nginx.conf /tmp/default.conf.template
RUN API_UPSTREAM=${API_UPSTREAM} envsubst '$${API_UPSTREAM}' \
      < /tmp/default.conf.template \
      > /etc/nginx/conf.d/default.conf \
    && rm /tmp/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
