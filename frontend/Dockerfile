FROM node:22-alpine

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install

COPY . .

EXPOSE 3000

# Install deps at runtime to handle volume mount overwriting node_modules
CMD ["sh", "-c", "pnpm install && pnpm dev --hostname 0.0.0.0"]
