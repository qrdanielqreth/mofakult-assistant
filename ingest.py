"""
Ingestion Script (Improved Version)

Loads documents from Google Drive, chunks them, generates embeddings,
and upserts them to Pinecone. Handles errors gracefully and skips
problematic files instead of crashing.

Usage:
    python ingest.py
"""

import json
import os
import sys
import time
import tempfile
import io
from collections import defaultdict
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from llama_index.core import VectorStoreIndex, Settings, Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.ingestion import IngestionPipeline
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding

# Load environment variables
load_dotenv()

# Set console encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Supported MIME types for text extraction
SUPPORTED_MIME_TYPES = {
    # Native files (can be downloaded directly)
    'application/pdf': '.pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/vnd.ms-excel': '.xls',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    'application/vnd.ms-powerpoint': '.ppt',
    'text/plain': '.txt',
    'text/csv': '.csv',
}

# Google native types that need export
# Using plain text for better text extraction!
GOOGLE_EXPORT_TYPES = {
    'application/vnd.google-apps.document': ('text/plain', '.txt'),  # Changed from PDF to TEXT!
    'application/vnd.google-apps.spreadsheet': ('text/csv', '.csv'),  # Changed from PDF to CSV!
    'application/vnd.google-apps.presentation': ('text/plain', '.txt'),  # Changed from PDF to TEXT!
}

# Skip these types
SKIP_MIME_TYPES = {
    'application/vnd.google-apps.folder',
    'application/vnd.google-apps.shortcut',
    'application/vnd.google-apps.form',
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
    'video/mp4', 'video/quicktime', 'video/x-msvideo',
    'audio/mpeg', 'audio/wav',
    'application/zip', 'application/x-zip',
}


def get_settings() -> dict:
    """Load and validate required environment variables."""
    required_vars = [
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_DRIVE_FOLDER_ID",
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "pinecone_api_key": os.getenv("PINECONE_API_KEY"),
        "pinecone_index_name": os.getenv("PINECONE_INDEX_NAME", "rag-index"),
        "google_credentials_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        "google_drive_folder_id": os.getenv("GOOGLE_DRIVE_FOLDER_ID"),
    }


def get_drive_service(creds_path: str):
    """Initialize Google Drive API service."""
    with open(creds_path, 'r') as f:
        creds_data = json.load(f)
    
    credentials = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    
    return build('drive', 'v3', credentials=credentials)


def list_files_recursive(service, folder_id: str, path: str = "") -> list:
    """Recursively list all files in a folder."""
    files_list = []
    folders_to_scan = [(folder_id, path)]
    
    while folders_to_scan:
        current_folder, current_path = folders_to_scan.pop(0)
        
        query = f"'{current_folder}' in parents and trashed = false"
        page_token = None
        
        while True:
            try:
                results = service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, size)',
                    pageToken=page_token,
                    pageSize=100,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                
                items = results.get('files', [])
                
                for item in items:
                    mime_type = item.get('mimeType', '')
                    
                    if mime_type == 'application/vnd.google-apps.folder':
                        # Add folder to scan queue
                        new_path = f"{current_path}/{item['name']}" if current_path else item['name']
                        folders_to_scan.append((item['id'], new_path))
                    else:
                        item['path'] = current_path
                        files_list.append(item)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                print(f"   [WARN] Error listing folder {current_folder}: {e}")
                break
    
    return files_list


def download_file(service, file_info: dict, temp_dir: str) -> str:
    """Download a file from Google Drive. Returns path to downloaded file or None."""
    file_id = file_info['id']
    file_name = file_info['name']
    mime_type = file_info.get('mimeType', '')
    
    try:
        # Determine how to download
        if mime_type in GOOGLE_EXPORT_TYPES:
            # Export Google native file as PDF
            export_mime, extension = GOOGLE_EXPORT_TYPES[mime_type]
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
            local_path = os.path.join(temp_dir, f"{file_name}{extension}")
        elif mime_type in SUPPORTED_MIME_TYPES:
            # Download native file
            request = service.files().get_media(fileId=file_id)
            extension = SUPPORTED_MIME_TYPES.get(mime_type, '')
            local_path = os.path.join(temp_dir, f"{file_name}")
        else:
            return None
        
        # Download to temp file
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        # Write to file
        with open(local_path, 'wb') as f:
            f.write(fh.getvalue())
        
        return local_path
        
    except Exception as e:
        error_msg = str(e)
        if 'exportSizeLimitExceeded' in error_msg:
            print(f"   [SKIP] {file_name} - Too large for export")
        elif 'fileNotDownloadable' in error_msg:
            print(f"   [SKIP] {file_name} - Cannot be downloaded")
        else:
            print(f"   [SKIP] {file_name} - Error: {str(e)[:50]}")
        return None


def load_document_from_file(file_path: str, metadata: dict) -> Document:
    """Load a document from a local file."""
    from llama_index.core.readers.file.base import SimpleDirectoryReader
    
    try:
        reader = SimpleDirectoryReader(input_files=[file_path])
        docs = reader.load_data()
        
        if docs:
            # Add metadata
            for doc in docs:
                doc.metadata.update(metadata)
            return docs
        return None
    except Exception as e:
        return None


def setup_pinecone_index(settings: dict) -> PineconeVectorStore:
    """Initialize Pinecone and create the index if it doesn't exist."""
    print("\n[PINECONE] Setting up Pinecone...")
    
    pc = Pinecone(api_key=settings["pinecone_api_key"])
    index_name = settings["pinecone_index_name"]
    
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    
    if index_name not in existing_indexes:
        print(f"   Creating new index: {index_name}")
        pc.create_index(
            name=index_name,
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        print("   Waiting for index to be ready...")
        time.sleep(10)
    else:
        print(f"   Using existing index: {index_name}")
    
    pinecone_index = pc.Index(index_name)
    stats = pinecone_index.describe_index_stats()
    print(f"   Current vectors in index: {stats.total_vector_count}")
    
    return PineconeVectorStore(pinecone_index=pinecone_index)


def load_documents_from_gdrive(settings: dict) -> list:
    """Load documents from Google Drive with error handling."""
    print("\n[GDRIVE] Loading documents from Google Drive...")
    
    service = get_drive_service(settings["google_credentials_path"])
    folder_id = settings["google_drive_folder_id"]
    
    print(f"   Folder ID: {folder_id}")
    print("   Scanning folders recursively...")
    
    # List all files
    all_files = list_files_recursive(service, folder_id)
    print(f"   Found {len(all_files)} total files")
    
    # Filter to supported types
    supported_files = []
    skipped_stats = defaultdict(int)
    
    for f in all_files:
        mime_type = f.get('mimeType', '')
        
        if mime_type in SKIP_MIME_TYPES:
            skipped_stats['Skipped (images/videos/etc)'] += 1
        elif mime_type in SUPPORTED_MIME_TYPES or mime_type in GOOGLE_EXPORT_TYPES:
            supported_files.append(f)
        else:
            skipped_stats['Unknown type'] += 1
    
    print(f"   Supported files to process: {len(supported_files)}")
    for reason, count in skipped_stats.items():
        print(f"   {reason}: {count}")
    
    # Download and load documents
    print("\n[DOWNLOAD] Downloading and processing files...")
    documents = []
    success_count = 0
    error_count = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, file_info in enumerate(supported_files, 1):
            file_name = file_info['name']
            file_path = file_info.get('path', '')
            
            # Progress
            if i % 10 == 0 or i == len(supported_files):
                print(f"   Processing {i}/{len(supported_files)}...")
            
            # Download file
            local_path = download_file(service, file_info, temp_dir)
            
            if local_path and os.path.exists(local_path):
                # Load document
                metadata = {
                    'file_name': file_name,
                    'file_path': file_path,
                    'source': f"gdrive:{file_info['id']}",
                }
                
                try:
                    docs = load_document_from_file(local_path, metadata)
                    if docs:
                        documents.extend(docs)
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"   [SKIP] {file_name} - Parse error: {str(e)[:30]}")
                    error_count += 1
                
                # Clean up
                try:
                    os.remove(local_path)
                except:
                    pass
            else:
                error_count += 1
    
    print(f"\n[RESULT] Successfully loaded: {success_count} files")
    print(f"[RESULT] Skipped/Errors: {error_count} files")
    print(f"[RESULT] Total documents: {len(documents)}")
    
    return documents


def create_and_run_pipeline(documents: list, vector_store: PineconeVectorStore, settings: dict):
    """Create ingestion pipeline and process documents."""
    print("\n[PIPELINE] Processing documents...")
    
    embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=settings["openai_api_key"],
        dimensions=1536,
    )
    
    text_splitter = SentenceSplitter(
        chunk_size=1024,
        chunk_overlap=200,
    )
    
    Settings.embed_model = embed_model
    
    pipeline = IngestionPipeline(
        transformations=[text_splitter, embed_model],
        vector_store=vector_store,
    )
    
    print("   Chunking documents...")
    print("   Generating embeddings...")
    print("   Upserting to Pinecone...")
    
    # Process in batches to avoid memory issues
    batch_size = 50
    total_nodes = 0
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        print(f"   Processing batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}...")
        
        try:
            nodes = pipeline.run(documents=batch, show_progress=True)
            total_nodes += len(nodes)
        except Exception as e:
            print(f"   [WARN] Batch error: {e}")
    
    print(f"\n[OK] Successfully processed {total_nodes} chunks")
    
    return total_nodes


def main():
    """Main ingestion function."""
    print("=" * 60)
    print("RAG System - Document Ingestion (Improved)")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        settings = get_settings()
        print("\n[OK] Environment variables loaded")
        
        creds_path = settings["google_credentials_path"]
        if not os.path.exists(creds_path):
            raise FileNotFoundError(f"Google credentials file not found: {creds_path}")
        print(f"[OK] Google credentials file found: {creds_path}")
        
        # Setup Pinecone
        vector_store = setup_pinecone_index(settings)
        
        # Load documents from Google Drive
        documents = load_documents_from_gdrive(settings)
        
        if not documents:
            print("\n[WARN] No documents could be loaded.")
            print("   Please check the scan_drive.py output for details.")
            sys.exit(1)
        
        # Process and ingest documents
        create_and_run_pipeline(documents, vector_store, settings)
        
        # Summary
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"Ingestion completed in {elapsed:.1f} seconds")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Run the Streamlit app: streamlit run app.py")
        print("2. Start chatting with your documents!")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
