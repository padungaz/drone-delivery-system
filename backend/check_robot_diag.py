import asyncio
import sqlite3
import socket

print("=== 1. DEVICES IN DATABASE ===")
con = sqlite3.connect("drone_delivery.db")
cur = con.cursor()
try:
    for row in cur.execute("SELECT device_name, device_type, ip_address, port, status, simulator_mode FROM devices").fetchall():
        print(row)
except Exception as e:
    print("Error querying devices:", e)

print("\n=== 2. TESTING PORTS ON 192.168.58.2 ===")
ports_to_test = [8090, 8080, 8081, 7003, 8000, 9100, 2000, 2001, 502, 102]
for port in ports_to_test:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        res = s.connect_ex(("192.168.58.2", port))
        if res == 0:
            print(f" Port {port}: OPEN ✅")
        else:
            print(f" Port {port}: CLOSED / REFUSED (code {res})")
    except Exception as ex:
        print(f" Port {port}: ERROR ({ex})")
    finally:
        s.close()
