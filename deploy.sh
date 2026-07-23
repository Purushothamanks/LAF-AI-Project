#!/bin/bash
set -e

if [ -f "/home/purushothaman/Videos/laf-project/Final-Pro-Key.pem" ]; then
  KEY_PATH="/home/purushothaman/Videos/laf-project/Final-Pro-Key.pem"
elif [ -f "/home/purushothaman/AWS keys/Final-Pro-Key.pem" ]; then
  KEY_PATH="/home/purushothaman/AWS keys/Final-Pro-Key.pem"
else
  KEY_PATH="./Final-Pro-Key.pem"
fi
REMOTE_HOST="98.89.32.42"
REMOTE_USER="ubuntu"
REMOTE_DIR="/home/ubuntu/laf-project"

echo "=========================================="
echo "    LAF PLATFORM DEPLOYMENT SCRIPT        "
echo "=========================================="

echo "Step 1: Syncing codebase to remote server..."
rsync -avz -e "ssh -i '$KEY_PATH' -o StrictHostKeyChecking=no" \
  --exclude 'backend/laf_storage.db*' \
  --exclude 'backend/__pycache__' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/dist' \
  --exclude '.git' \
  ./ $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/

echo "Step 2: Building remote Docker image and restarting container..."
ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no $REMOTE_USER@$REMOTE_HOST "
  cd $REMOTE_DIR
  echo 'Building Docker image laf:latest...'
  sudo docker build -t laf:latest .
  
  echo 'Stopping and removing old container laf...'
  sudo docker stop laf || true
  sudo docker rm laf || true
  
  echo 'Wiping old user conversation data for a fresh start...'
  sudo rm -rf /home/ubuntu/laf-project/backend/laf_storage.db*
  touch /home/ubuntu/laf-project/backend/laf_storage.db

  echo 'Starting new container laf...'
  sudo docker run -d --name laf --network host \
    -v /home/ubuntu/laf-project/backend/laf_storage.db:/app/backend/laf_storage.db \
    -v /home/ubuntu/laf-project/.env:/app/.env \
    --env-file /home/ubuntu/laf-project/.env \
    --restart unless-stopped laf:latest
    
  echo 'Checking status of containers...'
  sudo docker ps | grep laf
"

echo "Deployment completed successfully!"
