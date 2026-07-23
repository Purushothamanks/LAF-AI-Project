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
        echo '=== Check Backend Code (main.py / cli.py) ==='
        cat /home/ubuntu/laf-project/backend/main.py
        echo ''
        cat /home/ubuntu/laf-project/backend/cli.py
        echo ''
        echo '=== Check Nginx Config ==='
        sudo ls -la /etc/nginx/sites-enabled/
        sudo cat /etc/nginx/nginx.conf
        echo ''
        echo '=== Check if any Nginx sites exist ==='
        sudo ls -la /etc/nginx/sites-available/
        for f in /etc/nginx/sites-available/*; do
          echo "--- $f ---"
          sudo cat $f
        done
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
            timeout=120
        )
        
        print("=== stdout ===")
        print(result.stdout)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_laf_web()
