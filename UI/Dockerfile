# Stage 1: Build the Angular application
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve the application with Nginx
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the build output to replace the default nginx contents.
# The project name is 'ai-agent-ui' and using application builder outputs to 'browser' subdirectory
COPY --from=build /app/dist/ai-agent-ui/browser /usr/share/nginx/html

EXPOSE 80
