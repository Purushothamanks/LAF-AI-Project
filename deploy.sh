#!/bin/bash
set -e

KEY_PATH="/home/purushothaman/AWS keys/Final-Pro-Key.pem"
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
  
  echo 'Starting new container laf...'
  sudo docker run -d --name laf --network host \
    -v /home/ubuntu/laf-project/backend/laf_storage.db:/app/backend/laf_storage.db \
    --restart unless-stopped laf:latest
    
  echo 'Checking status of containers...'
  sudo docker ps | grep laf
"

echo "Deployment completed successfully!"
