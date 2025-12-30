# EC2 Deployment Guide

This file contains copy‑paste commands and configuration snippets to deploy the Water Pipeline Management System to an AWS EC2 instance (Ubuntu 22.04 / Node 18+).

1) Create EC2 instance

- Launch an EC2 instance (Ubuntu 22.04) and configure your Security Group with these inbound rules:
  - TCP 22 (SSH) from your IP
  - TCP 80 (HTTP) and TCP 443 (HTTPS) from 0.0.0.0/0
  - (Optional) TCP 3000 if you want to expose the app directly

2) SSH and install Node 18+

```bash
ssh -i /path/to/key.pem ubuntu@EC2_PUBLIC_IP
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs build-essential git
node -v
npm -v
```

3) Clone project and install dependencies

```bash
cd /srv
sudo mkdir -p /srv/jms && sudo chown $USER:$USER /srv/jms
cd /srv/jms
git clone <your-repo-url> .
npm ci
```

4) Environment variables

Create environment variables for production. For quick testing you can export them in the shell. For production use pm2/systemd env or AWS Parameter Store.

```bash
export PORT=3000
export DEVICE_TOKEN='JMS_DEVICE_001'
export FIREBASE_DB_URL='https://your-project-default-rtdb.firebaseio.com'
export FIREBASE_DB_SECRET='your_firebase_secret_or_empty'
```

An example `.env.example` is included in the repo. Do NOT commit real secrets to git.

5) Start with pm2

```bash
sudo npm install -g pm2
pm2 start ecosystem.config.js --env production
pm2 save
pm2 startup systemd
# run the printed command to enable pm2 on boot
```

6) Optional: Nginx reverse proxy and SSL

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl enable --now nginx
```

Sample `/etc/nginx/sites-available/jms`:

```
server {
    listen 80;
    server_name example.com www.example.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/jms /etc/nginx/sites-enabled/jms
sudo nginx -t && sudo systemctl reload nginx
# Once DNS points to the instance, obtain SSL cert:
sudo certbot --nginx -d example.com -d www.example.com
```

7) Quick checks

```bash
# Check API locally
curl -i http://127.0.0.1:3000/api/poll/all

# WebSocket (from your dev machine)
npm install -g wscat
wscat -c ws://example.com
```

8) Best practices

- Use `firebase-admin` on servers using a service account JSON; avoid embedding DB secrets. I can migrate server code to `firebase-admin` for you.
- Ensure the process user has write permission to the repo dir so `pipeline.db` is writable.
- Back up `pipeline.db` regularly to S3 or snapshot EBS.
- Use AWS Secrets Manager or Parameter Store for production secrets.
