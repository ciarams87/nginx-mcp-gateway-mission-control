FROM node:22-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY server.mjs ./
COPY public ./public
EXPOSE 3000
CMD ["node","server.mjs"]
