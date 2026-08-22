FROM node:20-alpine

WORKDIR /app

# Install dependencies first (leverages Docker cache)
COPY package.json package-lock.json* ./
RUN npm ci

# Copy the rest of the application files
COPY . .

# Build the Next.js app
RUN npm run build

# Expose port 3000
EXPOSE 3000

# Switch to non-root user
USER node

# Start the application in production mode
CMD ["npm", "run", "start"]
