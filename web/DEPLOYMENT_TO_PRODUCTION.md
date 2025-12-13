# Production Deployment Guide - tgp.riff.cc

## Overview

This guide documents the deployment of the Two Generals Protocol web demo to production hosting at tgp.riff.cc.

## Build Status

✅ **Production build complete**
- Location: `dist/`
- Bundle size: 202 KB (uncompressed), 60 KB (gzipped)
- Preview server running: http://localhost:4174/

## Deployment Options

### Option 1: Static File Hosting (Recommended)

The built files in `dist/` can be deployed to any static file hosting service:

#### Upload to Web Server

```bash
# Via rsync (if you have SSH access)
rsync -avz --delete dist/ user@tgp.riff.cc:/var/www/html/

# Via SCP
scp -r dist/* user@tgp.riff.cc:/var/www/html/

# Via SFTP
sftp user@tgp.riff.cc
> cd /var/www/html
> put -r dist/*
```

#### Nginx Configuration

If using nginx, configure as follows:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name tgp.riff.cc;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name tgp.riff.cc;

    # SSL Configuration (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/tgp.riff.cc/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tgp.riff.cc/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    root /var/www/tgp.riff.cc;
    index index.html;

    # Security Headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;" always;

    # Gzip Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;

    # Cache static assets (1 year)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Cache HTML files (1 hour)
    location ~* \.html$ {
        expires 1h;
        add_header Cache-Control "public, must-revalidate";
    }

    # SPA fallback (not needed for this project, but included for completeness)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Service Worker should not be cached
    location = /network-simulator.sw.js {
        add_header Cache-Control "no-cache";
        expires 0;
    }
}
```

#### Apache Configuration

If using Apache:

```apache
<VirtualHost *:80>
    ServerName tgp.riff.cc
    Redirect permanent / https://tgp.riff.cc/
</VirtualHost>

<VirtualHost *:443>
    ServerName tgp.riff.cc
    DocumentRoot /var/www/tgp.riff.cc

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/tgp.riff.cc/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/tgp.riff.cc/privkey.pem

    <Directory /var/www/tgp.riff.cc>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted

        # Enable Gzip
        AddOutputFilterByType DEFLATE text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript

        # Cache static assets
        <FilesMatch "\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$">
            Header set Cache-Control "public, max-age=31536000, immutable"
        </FilesMatch>

        # Cache HTML
        <FilesMatch "\.html$">
            Header set Cache-Control "public, max-age=3600, must-revalidate"
        </FilesMatch>
    </Directory>

    # Security Headers
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "DENY"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
</VirtualHost>
```

### Option 2: Deploy to CDN / Cloud Hosting

#### Cloudflare Pages

```bash
# Install Wrangler
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Deploy
wrangler pages deploy dist --project-name=tgp-web
```

#### Netlify

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Login
netlify login

# Deploy
cd web
netlify deploy --prod --dir=dist
```

#### Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
cd web
vercel --prod
```

#### GitHub Pages

```bash
# Build
npm run build

# Copy to gh-pages branch
git checkout -b gh-pages
cp -r dist/* .
git add .
git commit -m "Deploy to GitHub Pages"
git push origin gh-pages --force
```

Then enable GitHub Pages in repository settings pointing to the `gh-pages` branch.

### Option 3: Docker Container

```dockerfile
# Dockerfile
FROM nginx:alpine

# Copy built files
COPY dist/ /usr/share/nginx/html/

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

Build and run:

```bash
cd web
docker build -t tgp-web .
docker run -d -p 80:80 tgp-web
```

## DNS Configuration

Point `tgp.riff.cc` to your hosting:

```
# A Record
tgp.riff.cc.    IN    A    <your-server-ip>

# Or CNAME (if using CDN)
tgp.riff.cc.    IN    CNAME    <cdn-hostname>
```

## SSL/TLS Certificate

### Using Let's Encrypt (Free)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate for nginx
sudo certbot --nginx -d tgp.riff.cc

# Or for Apache
sudo certbot --apache -d tgp.riff.cc

# Auto-renewal is configured automatically
```

## Pre-Deployment Checklist

- [ ] Production build completed successfully
- [ ] Preview server tested locally (http://localhost:4174/)
- [ ] All browser tests passing
- [ ] Accessibility audit completed
- [ ] Performance targets met (<2s load, 60fps, <300ms tab switch)
- [ ] DNS records configured
- [ ] SSL certificate ready
- [ ] Web server configured with compression and caching
- [ ] Security headers configured

## Deployment Steps

1. **Build the production bundle** (already done):
   ```bash
   cd /mnt/castle/garage/two-generals-public/web
   npm run build
   ```

2. **Test the preview locally**:
   ```bash
   npm run preview
   # Open http://localhost:4174/ in browser
   ```

3. **Upload to server**:
   ```bash
   rsync -avz --delete dist/ user@tgp.riff.cc:/var/www/tgp.riff.cc/
   ```

4. **Configure web server** (nginx or Apache as shown above)

5. **Test the live site**:
   - Visit https://tgp.riff.cc
   - Test all tabs and functionality
   - Run Lighthouse audit
   - Verify SSL certificate

6. **Monitor**:
   - Check browser console for errors
   - Monitor server access logs
   - Set up uptime monitoring

## Post-Deployment Verification

### Manual Testing

- [ ] Homepage loads correctly
- [ ] All 4 tabs switch correctly
- [ ] Protocol visualization animates smoothly
- [ ] Performance charts render correctly
- [ ] Interactive controls work
- [ ] Mobile layout responsive
- [ ] No console errors
- [ ] SSL certificate valid

### Automated Testing

```bash
# Run Lighthouse audit
npm install -g lighthouse
lighthouse https://tgp.riff.cc --view

# Expected scores:
# Performance: >90
# Accessibility: >90
# Best Practices: >90
# SEO: >90
```

## Rollback Procedure

If issues are found:

```bash
# Restore previous version
git checkout <previous-tag>
npm run build
rsync -avz --delete dist/ user@tgp.riff.cc:/var/www/tgp.riff.cc/
```

## Monitoring and Analytics

### Optional: Add Analytics

Add to `dist/index.html` before `</head>`:

```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

Or use privacy-friendly alternative like Plausible or Fathom.

### Uptime Monitoring

Set up monitoring with:
- UptimeRobot (free)
- Pingdom
- StatusCake
- CloudFlare monitoring (if using Cloudflare)

## Troubleshooting

### Site doesn't load

1. Check DNS propagation: `dig tgp.riff.cc`
2. Verify web server is running: `systemctl status nginx`
3. Check server logs: `tail -f /var/log/nginx/error.log`

### SSL certificate errors

1. Verify certificate files exist
2. Check certificate expiry: `openssl x509 -in /etc/letsencrypt/live/tgp.riff.cc/cert.pem -noout -dates`
3. Renew if needed: `certbot renew`

### Performance issues

1. Verify gzip is enabled: Check response headers
2. Check CDN/cache status
3. Run Lighthouse audit for specific recommendations

## Support

- **Technical Issues**: Wings@riff.cc
- **Bug Reports**: https://github.com/rifflabs/two-generals-public/issues

---

## Current Build Information

**Build Date**: 2025-12-07
**Build Version**: 0.1.0
**Bundle Size**: 202 KB (60 KB gzipped)
**Node Version**: v18+
**Files Ready**: `dist/`

**Preview Server**: http://localhost:4174/
**Target Domain**: tgp.riff.cc

---

**Ready for deployment!** ✅
