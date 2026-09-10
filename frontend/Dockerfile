FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

ARG NODE_ENV=production
ENV NODE_ENV=${NODE_ENV}

ARG VITE_API_URL=https://botpasarprime-production.up.railway.app/api/v1
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

CMD ["npm","run","preview","--","--host","0.0.0.0"]
