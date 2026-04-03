# Frontend - React + Next.js
FROM node:20.10-alpine
WORKDIR /app
# Copy package files
COPY package.json package.json
COPY .eslintrc.json .eslintrc.json
# Install dependencies
RUN npm install --frozen-lockfile
# Copy source code
COPY . .
# Build Next.js
RUN npm run build
# Expose port
EXPOSE 3000
# Start application
CMD ["npm", "start"]
