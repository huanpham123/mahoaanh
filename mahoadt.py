from flask import Flask, render_template, redirect, url_for, flash
import os
import glob
import platform
from cryptography.fernet import Fernet
import logging
from datetime import datetime
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_connected_devices():
    """Lấy danh sách thiết bị kết nối"""
    devices = []
    system = platform.system()
    
    if system == 'Windows':
        # Quét các ổ đĩa trên Windows
        for drive in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            path = f"{drive}:\\"
            if os.path.exists(path):
                devices.append(path)
    elif system == 'Darwin':  # macOS
        # Kiểm tra thư mục /Volumes
        if os.path.exists('/Volumes'):
            devices.extend([f"/Volumes/{d}" for d in os.listdir('/Volumes')])
    elif system == 'Linux':
        # Kiểm tra thư mục /media và /run
        media_path = f"/media/{os.getlogin()}"
        if os.path.exists(media_path):
            devices.extend([f"{media_path}/{d}" for d in os.listdir(media_path)])
    
    return devices

def find_photos_directory():
    """Tìm thư mục ảnh trên các thiết bị kết nối"""
    possible_paths = [
        'DCIM/Camera',
        'DCIM/100ANDRO',
        'Internal Storage/DCIM/Camera',
        'Phone/DCIM/Camera',
        'Card/DCIM/Camera',
        'Pictures'
    ]
    
    for device in get_connected_devices():
        for path in possible_paths:
            full_path = os.path.join(device, path)
            if os.path.exists(full_path):
                logger.info(f"Found photos directory at: {full_path}")
                return full_path
    
    logger.warning("No photos directory found in connected devices")
    return None

def load_or_create_key():
    """Tạo hoặc load encryption key"""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desktop, exist_ok=True)
    
    key_file = os.path.join(desktop, 'photo_encryption.key')
    
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read(), key_file
    
    key = Fernet.generate_key()
    with open(key_file, 'wb') as f:
        f.write(key)
    
    return key, key_file

def safe_file_operation(func, path, *args, **kwargs):
    """Thực hiện thao tác file an toàn với retry"""
    max_retries = 3
    delay = 1  # giây
    
    for i in range(max_retries):
        try:
            return func(path, *args, **kwargs)
        except (OSError, IOError) as e:
            if i == max_retries - 1:
                raise
            logger.warning(f"Retry {i+1} for {path} due to {str(e)}")
            time.sleep(delay)

@app.route('/')
def index():
    return render_template('mahoa.html')

@app.route('/encrypt')
def encrypt():
    try:
        start_time = datetime.now()
        photos_dir = find_photos_directory()
        
        if not photos_dir:
            flash('Không tìm thấy thư mục ảnh. Vui lòng kết nối điện thoại và chọn chế độ truyền file (MTP).', 'danger')
            return redirect(url_for('index'))
        
        key, key_file = load_or_create_key()
        cipher = Fernet(key)
        
        # Tìm tất cả ảnh hợp lệ
        extensions = ('*.jpg', '*.jpeg', '*.png', '*.heic', '*.JPG', '*.JPEG')
        image_files = []
        
        for ext in extensions:
            try:
                image_files.extend(glob.glob(os.path.join(photos_dir, ext)))
            except Exception as e:
                logger.warning(f"Error scanning for {ext}: {str(e)}")
        
        if not image_files:
            flash('Không tìm thấy ảnh nào trong thư mục.', 'warning')
            return redirect(url_for('index'))
        
        # Sắp xếp theo thời gian sửa đổi
        image_files.sort(key=lambda x: safe_file_operation(os.path.getmtime, x), reverse=True)
        target_files = image_files[:5]
        
        # Mã hóa từng file
        success_count = 0
        for img_path in target_files:
            try:
                # Đọc file
                with safe_file_operation(open, img_path, 'rb') as f:
                    data = f.read()
                
                # Mã hóa
                encrypted_data = cipher.encrypt(data)
                
                # Ghi file mã hóa
                encrypted_path = f"{img_path}.encrypted"
                with safe_file_operation(open, encrypted_path, 'wb') as f:
                    f.write(encrypted_data)
                
                # Xóa file gốc
                safe_file_operation(os.remove, img_path)
                success_count += 1
                logger.info(f"Encrypted: {img_path}")
            except Exception as e:
                logger.error(f"Failed to encrypt {img_path}: {str(e)}")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        flash(f'Đã mã hóa thành công {success_count}/5 ảnh. Khóa bảo mật lưu tại: {key_file} (Thời gian: {elapsed:.2f}s)', 
              'success' if success_count > 0 else 'warning')
    
    except Exception as e:
        logger.exception("Encryption failed")
        flash(f'Lỗi hệ thống: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/decrypt')
def decrypt():
    try:
        start_time = datetime.now()
        photos_dir = find_photos_directory()
        
        if not photos_dir:
            flash('Không tìm thấy thư mục ảnh.', 'danger')
            return redirect(url_for('index'))
        
        # Load key
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        key_file = os.path.join(desktop, 'photo_encryption.key')
        
        if not os.path.exists(key_file):
            flash('Không tìm thấy file khóa giải mã trên Desktop.', 'danger')
            return redirect(url_for('index'))
        
        with open(key_file, 'rb') as f:
            key = f.read()
        
        cipher = Fernet(key)
        
        # Tìm các file mã hóa
        encrypted_files = glob.glob(os.path.join(photos_dir, '*.encrypted'))
        
        if not encrypted_files:
            flash('Không tìm thấy file mã hóa nào.', 'warning')
            return redirect(url_for('index'))
        
        # Giải mã từng file
        success_count = 0
        for enc_path in encrypted_files:
            try:
                # Đọc file mã hóa
                with safe_file_operation(open, enc_path, 'rb') as f:
                    encrypted_data = f.read()
                
                # Giải mã
                decrypted_data = cipher.decrypt(encrypted_data)
                
                # Khôi phục tên file gốc
                original_path = os.path.splitext(enc_path)[0]
                with safe_file_operation(open, original_path, 'wb') as f:
                    f.write(decrypted_data)
                
                # Xóa file mã hóa
                safe_file_operation(os.remove, enc_path)
                success_count += 1
                logger.info(f"Decrypted: {enc_path}")
            except Exception as e:
                logger.error(f"Failed to decrypt {enc_path}: {str(e)}")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        flash(f'Đã giải mã thành công {success_count}/{len(encrypted_files)} file. (Thời gian: {elapsed:.2f}s)',
              'success' if success_count > 0 else 'warning')
    
    except Exception as e:
        logger.exception("Decryption failed")
        flash(f'Lỗi giải mã: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
