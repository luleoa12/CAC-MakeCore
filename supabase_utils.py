import os
from supabase import create_client, Client
from werkzeug.utils import secure_filename

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

import time
import random
import string

def create_user_folders_in_supabase(username):
    """
    Creates the folders {username}/program_thumbnails/ and {username}/profile/ in the Supabase bucket by uploading a .keep file to each.
    """
    for subfolder in ["program_thumbnails", "profile"]:
        folder_path = f"{username}/{subfolder}/.keep"
        try:
            supabase.storage.from_(SUPABASE_BUCKET).upload(folder_path, b"", {"content-type": "text/plain"})
            print(f"[Supabase] Created folder: {folder_path}")
        except Exception as e:
            print(f"[Supabase] Error creating folder {folder_path}: {e}")

def upload_image_to_supabase(file_storage, folder=None):
    if hasattr(file_storage, 'stream'):
        file_storage.stream.seek(0)
        file_bytes = file_storage.read()
        filename = secure_filename(file_storage.filename)
        mimetype = getattr(file_storage, 'mimetype', 'image/jpeg')
    else:
        file_storage.seek(0)
        file_bytes = file_storage.read()
        filename = getattr(file_storage, 'name', 'image.jpg')
        mimetype = 'image/jpeg'
    
    timestamp = int(time.time())
    randstr = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, 'jpg')
    unique_filename = f"{name}_{timestamp}_{randstr}.{ext}"
    path = f"{folder}/{unique_filename}" if folder else unique_filename

    print(f"[Supabase] Attempting to upload: {unique_filename} to path: {path} (bucket: {SUPABASE_BUCKET})")
    try:
        res = supabase.storage.from_(SUPABASE_BUCKET).upload(path, file_bytes, {"content-type": mimetype})
        print(f"[Supabase] Upload response: {res}")
    except Exception as e:
        print("[Supabase] Upload failed:", e)
        return None
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{path}"
    print(f"[Supabase] Public URL: {public_url}")
    return public_url

def delete_image_from_supabase(image_url):

    if not image_url or SUPABASE_BUCKET not in image_url:
        return False

    try:
        filename = image_url.split(f"/{SUPABASE_BUCKET}/", 1)[1]
    except IndexError:
        return False
    res = supabase.storage.from_(SUPABASE_BUCKET).remove([filename])

    if (hasattr(res, 'status_code') and res.status_code == 200) or (isinstance(res, dict) and res.get('error') is None):
        return True
    return False

def list_supabase_images():
    res = supabase.storage.from_(SUPABASE_BUCKET).list("") 
    if hasattr(res, 'data'):
        files = res.data
    elif isinstance(res, dict) and 'data' in res:
        files = res['data']
    else:
        print("Error listing files:", getattr(res, 'error', res))
        return []

    public_urls = []
    for file in files:
        url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{file['name']}"
        public_urls.append(url)
    return public_urls
