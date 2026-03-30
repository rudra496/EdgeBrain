FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --production 2>/dev/null || npm install

COPY . .

EXPOSE 3000

CMD ["npm", "start"]
