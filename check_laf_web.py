import subprocess
import os

def check_laf_web():
    # AWS server details from deploy.sh
    key_path = "/home/purushothaman/AWS keys/Final-Pro-Key.pem"
    remote_host = "98.89.32.42"
    remote_user = "ubuntu"
    
    # SSH command
    ssh_cmd = [
        "ssh",
        "-F", "/dev/null",
        "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{remote_user}@{remote_host}",
        """
        echo '=== Docker Inspect LAF Container (Network) ==='
        sudo docker inspect laf --format '{{json .NetworkSettings}}' | python3 -m json.tool
        echo ''
        echo '=== Docker PS with Ports ==='
        sudo docker ps --format "table {{.Names}}\\t{{.Ports}}\\t{{.Status}}"
        echo ''
        echo '=== Check if Nginx is running ==='
        sudo systemctl status nginx 2>&1 || echo "Nginx not running via systemd"
        echo ''
        echo '=== Check Docker Compose / deploy config ==='
        cd /home/ubuntu/laf-project && ls -la
        echo ''
        echo '=== Check Dockerfile ==='
        cat /home/ubuntu/laf-project/Dockerfile
        """
    ]
    
    env = dict(
        PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    )
    
    try:
        result = subprocess.run(
            ssh_cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print("=== stdout ===")
        print(result.stdout)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_laf_web()
