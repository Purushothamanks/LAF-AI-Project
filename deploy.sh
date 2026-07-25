#!/bin/bash
set -e

REMOTE_HOST="98.89.32.42"
REMOTE_USER="ubuntu"
KEY_PATH="/home/purushothaman/Videos/laf-project/Final-Pro-Key.pem"
REMOTE_DIR="/home/ubuntu/laf-project"

echo "=========================================="
echo "    LAF PLATFORM CLEAN DEPLOYMENT SCRIPT  "
echo "=========================================="

echo "Step 1: Syncing fresh codebase to remote server..."
rsync -avz -e "ssh -i $KEY_PATH -o StrictHostKeyChecking=no" \
  --exclude 'node_modules' \
  --exclude 'dist' \
  --exclude '.git' \
  --exclude 'laf_storage.db*' \
  /home/purushothaman/Videos/laf-project/ $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/

echo "Step 2: Building remote Docker image without cache and restarting container..."
ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no $REMOTE_USER@$REMOTE_HOST "
  cd $REMOTE_DIR
  echo 'Building Docker image laf:latest...'
  sudo docker build --no-cache -t laf:latest .
  
  echo 'Stopping and removing old container laf...'
  sudo docker stop laf || true
  sudo docker rm laf || true
  
  echo 'Starting fresh container laf...'
  sudo docker run -d --name laf --network host \
    --restart unless-stopped laf:latest
  
  echo 'Checking status of container...'
  sudo docker ps | grep laf
"

echo "Step 3: Auto-committing and pushing updates to GitHub repository..."
cd /home/purushothaman/Videos/laf-project
git add .
git commit -m "Fresh start: Clean high-performance LAF architecture: $(date '+%Y-%m-%d %H:%M:%S')" || true
git push origin main || true

echo "Deployment and GitHub sync completed successfully!"
