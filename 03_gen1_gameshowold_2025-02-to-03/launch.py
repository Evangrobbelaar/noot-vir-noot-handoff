import subprocess
import time
from threading import Thread

def run_script(script_name):
    subprocess.Popen(['python', script_name], creationflags=subprocess.CREATE_NEW_CONSOLE)

def main():
    run_script('leaderboard.py')
    time.sleep(2)
    run_script('bsd.py')

if __name__ == "__main__":
    main()