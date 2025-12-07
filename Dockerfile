# Two Generals Protocol - Interactive Visualizer & Paper
# Build: docker build -t riffcc/two-generals:latest .
# Run: docker run -p 8080:80 riffcc/two-generals:latest

FROM nginx:alpine

# Copy web visualizer (pre-built dist)
COPY web/dist/ /usr/share/nginx/html/

# Copy paper
COPY paper/main.pdf /usr/share/nginx/html/paper/main.pdf

# Copy Lean 4 source files for exploration
COPY lean4/*.lean /usr/share/nginx/html/lean4/
COPY lean4/lakefile.lean /usr/share/nginx/html/lean4/
COPY lean4/lean-toolchain /usr/share/nginx/html/lean4/

# Custom nginx config to serve .lean files with proper MIME type
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    \
    location = /paper { \
        return 301 /paper/main.pdf; \
    } \
    \
    location /paper/ { \
        add_header Content-Disposition "inline"; \
    } \
    \
    location /lean4/ { \
        types { \
            text/plain lean; \
        } \
        add_header Content-Type text/plain; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
