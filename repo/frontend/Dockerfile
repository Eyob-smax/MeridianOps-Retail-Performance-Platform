FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM deps AS base
COPY . .

FROM base AS runtime
ENV VITE_API_BASE_URL=http://localhost:8000/api/v1 \
	VITE_APP_NAME="MeridianOps Retail Performance"
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM base AS test
CMD ["npm", "run", "test"]
