FROM node:20-alpine
WORKDIR /app
COPY package.json ./
COPY mcp/ ./mcp/
ENTRYPOINT ["node", "/app/mcp/apextick-mcp.mjs"]
