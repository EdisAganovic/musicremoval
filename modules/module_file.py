import hashlib
import requests
import time

def calculate_file_hash(filepath, hash_algorithm="sha256"):
    """
    Calculates the hash of a file.
    Useful for verifying file integrity after download.
    """
    hasher = hashlib.new(hash_algorithm)
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None
    except Exception as e:
        print(f"Error calculating hash for {filepath}: {e}")
        return None

def download_file_concurrent(url, filename):
    """
    Downloads a single file concurrently, streaming content to disk.
    """
    print(f"[{filename}] Starting download from {url}...")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()

            total_size = int(r.headers.get('content-length', 0))
            downloaded_size = 0
            start_time = time.time()

            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

            end_time = time.time()
            duration = end_time - start_time
            speed = (downloaded_size / (1024 * 1024)) / duration if duration > 0 else 0
            print(f"\n[{filename}] Successfully downloaded. Size: {downloaded_size / (1024*1024):.2f} MB, Time: {duration:.2f}s, Speed: {speed:.2f} MB/s")
            return True, filename
    except requests.exceptions.RequestException as e:
        print(f"\n[{filename}] Error downloading: {e}")
        return False, filename
    except IOError as e:
        print(f"\n[{filename}] File system error saving {filename}: {e}")
        return False, filename
