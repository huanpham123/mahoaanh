from flask import Flask, render_template, redirect, url_for, flash, request
import os
import glob
import string
import platform
from cryptography.fernet import Fernet
import logging
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper: Tìm thư mục ảnh trên điện thoại
def find_phone_photos_dir():
    # Danh sách các vị trí có khả năng chứa ảnh
    common_paths = []
    system = platform.system()
    
    # Windows
    if system == 'Windows':
        for drive in string.ascii_uppercase:
            # Android
            common_paths.extend([
                f"{drive}:\\Phone\\DCIM\\Camera",
                f"{drive}:\\Internal storage\\DCIM\\Camera",
                f"{drive}:\\Card\\DCIM\\Camera",
                f"{drive}:\\DCIM\\Camera",
            ])
            # iOS
            common_paths.extend([
                f"{drive}:\\Apple iPhone\\Internal Storage\\DCIM",
                f"{drive}:\\iPhone\\DCIM",
            ])
    
    # macOS
    elif system == 'Darwin':
        common_paths.extend([
            "/Volumes/iPhone/DCIM",
            "/Volumes/NO NAME/DCIM/Camera",
            "/Volumes/ANDROID/DCIM/Camera",
        ])
    
    # Linux
    elif system == 'Linux':
        common_paths.extend([
            "/media/$USER/Phone/DCIM/Camera",
            "/media/$USER/Card/DCIM/Camera",
            "/run/user/$USER/gvfs/mtp:host=*/DCIM/Camera",
        ])
    
    # Kiểm tra từng đường dẫn
    for path in common_paths:
        # Xử lý các biến trong đường dẫn
        path = path.replace("$USER", os.getlogin())
        path = os.path.expanduser(path)
        
        # Tìm kiếm các pattern có thể
        if '*' in path:
            for expanded in glob.glob(path):
                if os.path.isdir(expanded):
                    logger.info(f"Found photo directory: {expanded}")
                    return expanded
        elif os.path.isdir(path):
            logger.info(f"Found photo directory: {path}")
            return path
    
    # Tìm kiếm đệ quy nếu không thấy
    logger.warning("Could not find DCIM/Camera, starting recursive search...")
    search_roots = ['/', '/Volumes'] if system != 'Windows' else ['C:\\', 'D:\\']
    
    for root in search_roots:
        for dirpath, dirnames, filenames in os.walk(root):
            if 'DCIM' in dirnames:
                camera_path = os.path.join(dirpath, 'DCIM', 'Camera')
                if os.path.isdir(camera_path):
                    logger.info(f"Found camera recursively: {camera_path}")
                    return camera_path
    return None

# Helper: load hoặc tạo key trên Desktop
def load_or_create_key():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desktop, exist_ok=True)
    
    key_file = os.path.join(desktop, 'image_encryption.key')
    if os.path.exists(key_file):
        with open(key_file, 'rb') as kf:
            return kf.read(), key_file
    
    key = Fernet.generate_key()
    with open(key_file, 'wb') as kf:
        kf.write(key)
    return key, key_file

@app.route('/')
def index():
    return render_template('mahoa.html')

@app.route('/encrypt')
def encrypt():
    try:
        phone_dir = find_phone_photos_dir()
        if not phone_dir:
            flash('Không tìm thấy thư mục ảnh!', 'danger')
            return redirect(url_for('index'))

        key, key_file = load_or_create_key()
        cipher = Fernet(key)

        # Lấy 5 ảnh mới nhất
        imgs = glob.glob(os.path.join(phone_dir, '*.[jJ][pP][gG]')) + \
               glob.glob(os.path.join(phone_dir, '*.[pP][nN][gG]'))
        imgs.sort(key=os.path.getmtime, reverse=True)

        for img in imgs[:5]:
            try:
                with open(img, 'rb') as f:
                    data = f.read()
                encrypted = cipher.encrypt(data)
                with open(f"{img}.encrypted", 'wb') as f:
                    f.write(encrypted)
                os.remove(img)
            except Exception as e:
                print(f"Lỗi khi xử lý {img}: {e}")

        flash('Mã hóa thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    return redirect(url_for('index'))

@app.route('/decrypt')
def decrypt():
    phone_dir = find_phone_photos_dir()
    if not phone_dir:
        flash('Không tìm thấy thư mục ảnh trên điện thoại.', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Load key
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        key_file = os.path.join(desktop, 'image_encryption.key')
        
        if not os.path.exists(key_file):
            flash('Không tìm thấy file khóa trên Desktop.', 'danger')
            return redirect(url_for('index'))
        
        with open(key_file, 'rb') as kf:
            key = kf.read()
        
        cipher = Fernet(key)

        # Tìm file mã hóa
        encs = glob.glob(os.path.join(phone_dir, '*.encrypted'))
        if not encs:
            flash('Không tìm thấy file mã hóa nào.', 'warning')
            return redirect(url_for('index'))
        
        # Giải mã
        success_count = 0
        for enc in encs:
            try:
                # Đọc file mã hóa
                with open(enc, 'rb') as ef:
                    ed = ef.read()
                
                # Giải mã
                dec = cipher.decrypt(ed)
                
                # Khôi phục tên file gốc
                orig = enc.replace('.encrypted', '')
                with open(orig, 'wb') as df:
                    df.write(dec)
                
                # Xóa file mã hóa
                os.remove(enc)
                success_count += 1
                logger.info(f"Decrypted: {enc}")
            except Exception as e:
                logger.error(f"Error decrypting {enc}: {str(e)}")
        
        flash(f'Đã giải mã {success_count}/{len(encs)} file thành công.', 
              'success' if success_count > 0 else 'warning')
    except Exception as e:
        logger.exception("Decryption failed")
        flash(f'Lỗi giải mã: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
