FROM node:24-bookworm-slim
WORKDIR /compiler
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY --chown=node:node compiler/server.mjs ./server.mjs
USER node
EXPOSE 8070
CMD ["node","server.mjs"]
