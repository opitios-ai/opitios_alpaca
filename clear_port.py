#!/usr/bin/env python3
"""
Automatic Port 8090 Cleaner
自动清理8090端口占用的进程
"""
import subprocess
import sys
import time
import os

def kill_port_8090():
    """Kill processes using port 8090"""
    print("Checking for processes using port 8090...")
    
    try:
        if os.name == 'nt':  # Windows
            # Find processes using port 8090
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'TCP'], 
                capture_output=True, text=True
            )
            
            lines = result.stdout.split('\n')
            pids_to_kill = []
            
            for line in lines:
                if ':8090' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit():
                            pids_to_kill.append(pid)
                            print(f"Found process PID {pid} using port 8090")
            
            # Kill the processes
            for pid in pids_to_kill:
                try:
                    subprocess.run(['taskkill', '/F', '/PID', pid], check=True)
                    print(f"Killed process PID {pid}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to kill PID {pid}: {e}")
                    
        else:  # Linux/Mac
            # Find and kill processes using port 8090
            try:
                result = subprocess.run(
                    ['lsof', '-ti:8090'], 
                    capture_output=True, text=True
                )
                
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid.strip():
                            try:
                                subprocess.run(['kill', '-9', pid.strip()], check=True)
                                print(f"Killed process PID {pid.strip()}")
                            except subprocess.CalledProcessError as e:
                                print(f"Failed to kill PID {pid.strip()}: {e}")
                else:
                    print("No processes found using port 8090")
                    
            except FileNotFoundError:
                print("lsof command not found, trying alternative method...")
                try:
                    subprocess.run(['fuser', '-k', '8090/tcp'], check=True)
                    print("Killed processes using port 8090 with fuser")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    print("Could not kill processes automatically")
        
        # Wait a moment for processes to close
        time.sleep(2)
        
        # Verify port is free
        if verify_port_free():
            print("Port 8090 is now available")
            return True
        else:
            print("Port 8090 may still be in use")
            return False
            
    except Exception as e:
        print(f"Error while cleaning port: {e}")
        return False

def verify_port_free():
    """Check if port 8090 is free"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(
                ['netstat', '-an'], 
                capture_output=True, text=True
            )
            return ':8090' not in result.stdout
        else:  # Linux/Mac
            result = subprocess.run(
                ['ss', '-tuln'], 
                capture_output=True, text=True
            )
            return ':8090' not in result.stdout
    except:
        return True  # Assume free if can't check

def main():
    """Main function"""
    print("Opitios Alpaca Port 8090 Cleaner")
    print("=" * 40)
    
    if verify_port_free():
        print("Port 8090 is already free")
        return
    
    print("Port 8090 is in use, attempting to clear...")
    success = kill_port_8090()
    
    if success:
        print("\nPort 8090 cleared successfully!")
        print("You can now start the server with: python main.py")
    else:
        print("\nCould not clear port automatically")
        print("Please manually check and kill processes using port 8090")
        print("Windows: netstat -ano | findstr :8090")
        print("Linux/Mac: lsof -i :8090")

if __name__ == "__main__":
    main()