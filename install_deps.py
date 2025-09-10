import subprocess
import sys

try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mysql-connector-python"])
    print("Successfully installed mysql-connector-python")
except subprocess.CalledProcessError as e:
    print(f"Failed to install mysql-connector-python: {e}")
    sys.exit(1)
