import os.path
import base64
import re
import asyncio
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from colorama import Fore

# If modifying these scopes, delete the file token.json.
# We only need read/modify access (to mark as read).
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_gmail_service():
    """Authenticates the user and returns the Gmail service."""
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("Missing 'credentials.json' from Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

async def wait_for_vtop_otp(timeout_seconds=60) -> str:
    """
    Polls the inbox for an unread VTOP OTP email.
    Extracts the 6-digit code and marks the email as read.
    """
    print(f"   {Fore.CYAN}[.] Connecting to Gmail API for OTP autofill...")
    
    try:
        service = await asyncio.to_thread(get_gmail_service)
    except Exception as e:
        print(f"   {Fore.RED}[x] Gmail Auth Failed: {e}")
        return None

    print(f"   {Fore.CYAN}[.] Waiting for VTOP email... (Timeout: {timeout_seconds}s)")
    
    # The query specifically looks for unread emails containing "OTP"
    # Update "vitap.ac.in" if the sender address is different
    query = "is:unread subject:OTP" 

    for _ in range(timeout_seconds // 3):
        try:
            # 1. Search for matching emails
            results = await asyncio.to_thread(
                service.users().messages().list, userId='me', q=query, maxResults=1
            )
            messages = results.execute().get('messages', [])

            if messages:
                message_id = messages[0]['id']
                
                # 2. Fetch the email content
                msg = await asyncio.to_thread(
                    service.users().messages().get, userId='me', id=message_id, format='full'
                )
                msg_data = msg.execute()

                # 3. Extract the body text
                parts = msg_data.get('payload', {}).get('parts', [])
                body_data = ""
                for part in parts:
                    if part['mimeType'] == 'text/plain':
                        body_data = part['body'].get('data', '')
                        break
                
                if not body_data:
                    # Fallback if there are no parts (simple email)
                    body_data = msg_data.get('payload', {}).get('body', {}).get('data', '')

                if body_data:
                    # Decode base64 email body
                    clean_text = base64.urlsafe_b64decode(body_data).decode('utf-8')
                    
                    # 4. Use Regex to find exactly 6 consecutive digits
                    match = re.search(r'(?<!\d)\d{6}(?!\d)', clean_text)
                    if match:
                        otp_code = match.group(0)
                        
                        # 5. Mark as read so we don't fetch it again on the next login
                        await asyncio.to_thread(
                            service.users().messages().modify,
                            userId='me',
                            id=message_id,
                            body={'removeLabelIds': ['UNREAD']}
                        )
                        msg_call = service.users().messages().modify(userId='me', id=message_id, body={'removeLabelIds': ['UNREAD']})
                        msg_call.execute()
                        
                        print(f"   {Fore.GREEN}[✓] Gmail Intercepted OTP: {otp_code}")
                        return otp_code

        except Exception as e:
            print(f"   {Fore.RED}[!] Gmail check error: {e}")

        # Wait 3 seconds before polling again
        await asyncio.sleep(3)

    print(f"   {Fore.RED}[x] Gmail Timeout: No OTP email received.")
    return None