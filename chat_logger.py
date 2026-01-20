"""
Chat Logger Module

Logs all chat conversations to a Google Sheet for analysis.
Supports both local development and Streamlit Cloud deployment.
"""

import os
import json
from datetime import datetime
from typing import Optional
import gspread
from google.oauth2 import service_account

# Sheet configuration
SPREADSHEET_NAME = "Mofakult Chat Logs"
WORKSHEET_NAME = "Conversations"
SHARE_EMAIL = "daniel.fankhauser.media@gmail.com"

# Shared Drive folder ID (same as documents folder)
# Set via environment variable or Streamlit secrets
FOLDER_ID = None  # Will be loaded from env

# Required scopes for Google Sheets
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_folder_id():
    """Get the Google Drive folder ID from environment or secrets."""
    global FOLDER_ID
    if FOLDER_ID:
        return FOLDER_ID
    
    # Try environment variable
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if folder_id:
        FOLDER_ID = folder_id
        return FOLDER_ID
    
    # Try Streamlit secrets
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'GOOGLE_DRIVE_FOLDER_ID' in st.secrets:
            FOLDER_ID = st.secrets['GOOGLE_DRIVE_FOLDER_ID']
            return FOLDER_ID
    except Exception:
        pass
    
    return None


def get_credentials():
    """
    Get Google credentials from file or Streamlit secrets.
    
    Returns:
        Credentials object or None if not available
    """
    try:
        # First try: Local credentials file
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
        if os.path.exists(creds_path):
            with open(creds_path, 'r') as f:
                creds_data = json.load(f)
            return service_account.Credentials.from_service_account_info(
                creds_data, scopes=SCOPES
            )
        
        # Second try: Streamlit secrets (for cloud deployment)
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'GOOGLE_CREDENTIALS' in st.secrets:
                creds_data = json.loads(st.secrets['GOOGLE_CREDENTIALS'])
                return service_account.Credentials.from_service_account_info(
                    creds_data, scopes=SCOPES
                )
        except Exception:
            pass
        
        return None
        
    except Exception as e:
        print(f"[Logger] Error loading credentials: {e}")
        return None


def get_or_create_spreadsheet(client: gspread.Client) -> Optional[gspread.Spreadsheet]:
    """
    Get existing spreadsheet or create a new one in the Shared Drive.
    
    Args:
        client: Authenticated gspread client
        
    Returns:
        Spreadsheet object or None
    """
    try:
        # Try to open existing spreadsheet
        spreadsheet = client.open(SPREADSHEET_NAME)
        print(f"[Logger] Found existing spreadsheet: {SPREADSHEET_NAME}")
        return spreadsheet
    except gspread.SpreadsheetNotFound:
        # Create new spreadsheet in the Shared Drive folder
        try:
            folder_id = get_folder_id()
            
            if folder_id:
                # Create in Shared Drive folder
                spreadsheet = client.create(SPREADSHEET_NAME, folder_id=folder_id)
                print(f"[Logger] Created spreadsheet in Shared Drive folder")
            else:
                # Fallback: create in Service Account's drive
                spreadsheet = client.create(SPREADSHEET_NAME)
                # Share with user since it's not in shared drive
                spreadsheet.share(SHARE_EMAIL, perm_type='user', role='writer')
                print(f"[Logger] Created spreadsheet, shared with: {SHARE_EMAIL}")
            
            # Setup worksheet with headers
            worksheet = spreadsheet.sheet1
            worksheet.update_title(WORKSHEET_NAME)
            worksheet.append_row([
                "Timestamp",
                "Session ID", 
                "User Message",
                "Assistant Response",
                "Response Time (s)"
            ])
            
            # Format header row (bold)
            try:
                worksheet.format('A1:E1', {'textFormat': {'bold': True}})
            except Exception:
                pass  # Formatting is optional
            
            print(f"[Logger] Spreadsheet ready: {SPREADSHEET_NAME}")
            
            return spreadsheet
            
        except Exception as e:
            print(f"[Logger] Error creating spreadsheet: {e}")
            return None


class ChatLogger:
    """
    Logger class for tracking chat conversations in Google Sheets.
    """
    
    def __init__(self):
        """Initialize the chat logger."""
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        self.enabled = False
        self._initialize()
    
    def _initialize(self):
        """Set up connection to Google Sheets."""
        try:
            credentials = get_credentials()
            if not credentials:
                print("[Logger] No credentials available - logging disabled")
                return
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = get_or_create_spreadsheet(self.client)
            
            if self.spreadsheet:
                # Try to get the worksheet, or use the first one
                try:
                    self.worksheet = self.spreadsheet.worksheet(WORKSHEET_NAME)
                except gspread.WorksheetNotFound:
                    # Use the first worksheet (Sheet1/Tabelle1)
                    self.worksheet = self.spreadsheet.sheet1
                    # Rename it to our name
                    try:
                        self.worksheet.update_title(WORKSHEET_NAME)
                    except Exception:
                        pass  # May not have permission to rename
                
                # Check if headers exist, if not add them
                try:
                    first_row = self.worksheet.row_values(1)
                    if not first_row or first_row[0] != "Timestamp":
                        self.worksheet.insert_row([
                            "Timestamp",
                            "Session ID",
                            "User Message", 
                            "Assistant Response",
                            "Response Time (s)"
                        ], index=1)
                except Exception:
                    pass  # Headers might already exist
                
                self.enabled = True
                print("[Logger] Successfully connected to Google Sheets")
            
        except Exception as e:
            print(f"[Logger] Initialization error: {e}")
            self.enabled = False
    
    def log_conversation(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        response_time: float = 0.0
    ):
        """
        Log a conversation turn to Google Sheets.
        
        Args:
            session_id: Unique identifier for the chat session
            user_message: The user's input message
            assistant_response: The assistant's response
            response_time: Time taken to generate response (seconds)
        """
        if not self.enabled:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Truncate long messages to avoid cell limits (50000 chars max)
            user_msg = user_message[:5000] if len(user_message) > 5000 else user_message
            assistant_msg = assistant_response[:10000] if len(assistant_response) > 10000 else assistant_response
            
            row = [
                timestamp,
                session_id,
                user_msg,
                assistant_msg,
                f"{response_time:.2f}"
            ]
            
            self.worksheet.append_row(row, value_input_option='USER_ENTERED')
            
        except Exception as e:
            print(f"[Logger] Error logging conversation: {e}")
            # Don't crash the app if logging fails
            pass


# Singleton instance
_logger_instance = None


def get_logger() -> ChatLogger:
    """
    Get the singleton ChatLogger instance.
    
    Returns:
        ChatLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ChatLogger()
    return _logger_instance


def log_chat(session_id: str, user_message: str, assistant_response: str, response_time: float = 0.0):
    """
    Convenience function to log a chat conversation.
    
    Args:
        session_id: Unique identifier for the chat session
        user_message: The user's input message
        assistant_response: The assistant's response
        response_time: Time taken to generate response (seconds)
    """
    logger = get_logger()
    logger.log_conversation(session_id, user_message, assistant_response, response_time)


# Test when running directly
if __name__ == "__main__":
    print("Testing Chat Logger...")
    
    # Load dotenv for local testing
    from dotenv import load_dotenv
    load_dotenv()
    
    logger = get_logger()
    
    if logger.enabled:
        print("[OK] Logger is enabled")
        print(f"[OK] Spreadsheet: {SPREADSHEET_NAME}")
        
        # Test log
        log_chat(
            session_id="test-session-001",
            user_message="Dies ist eine Testnachricht",
            assistant_response="Dies ist eine Testantwort vom Assistenten.",
            response_time=1.23
        )
        print("[OK] Test message logged successfully")
        print(f"\nCheck your Google Drive for: {SPREADSHEET_NAME}")
    else:
        print("[ERROR] Logger is not enabled - check credentials")
