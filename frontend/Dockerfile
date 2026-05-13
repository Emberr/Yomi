FROM node:22-alpine

LABEL org.opencontainers.image.title="Yomi frontend"
LABEL org.opencontainers.image.description="Next.js frontend for Yomi."

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY next-env.d.ts next.config.ts tsconfig.json eslint.config.mjs ./
COPY public ./public
COPY src ./src

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
