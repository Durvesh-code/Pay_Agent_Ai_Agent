# Stage 1: Build the React App
FROM node:20-alpine as builder

WORKDIR /app

# COPY ONLY package.json (Ignore package-lock.json to fix Windows/Linux conflict)
COPY package.json ./

# Install dependencies from scratch for Linux
RUN npm install

# Copy source code and build
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy the build output from Stage 1 to Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]