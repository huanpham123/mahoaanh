from flask import Flask, render_template, redirect, url_for, flash, request
import os
import glob
from cryptography.fernet import Fernet
import logging
from datetime import datetime

app = Flask(__name__)
# Đặt secret_key cố định để không mất session khi server restart (trong lúc debug)
# Trong môi trường thực tế, nên dùng os.urandom(24)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_or_create_key():
    """Tạo hoặc load encryption key từ Desktop."""
    # Đảm bảo thư mục Desktop tồn tại
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desktop_path, exist_ok=True)
    
    key_file = os.path.join(desktop_path, 'photo_encryption.key')
    
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            key = f.read()
            logger.info(f"Loaded existing key from: {key_file}")
            return key, key_file
    
    key = Fernet.generate_key()
    with open(key_file, 'wb') as f:
        f.write(key)
    logger.info(f"Generated new key at: {key_file}")
    return key, key_file

@app.route('/')
def index():
    return render_template('mahoa.html')

@app.route('/encrypt', methods=['POST'])
def encrypt():
    photos_dir = request.form.get('path')
    if not photos_dir or not os.path.isdir(photos_dir):
        flash('Đường dẫn không hợp lệ! Vui lòng kiểm tra lại.', 'danger')
        return redirect(url_for('index'))

    try:
        start_time = datetime.now()
        key, key_file = load_or_create_key()
        cipher = Fernet(key)
        
        # Tìm tất cả các loại ảnh phổ biến, không phân biệt chữ hoa/thường
        extensions = ('*.jpg', '*.jpeg', '*.png', '*.heic', '*.JPG', '*.JPEG', '*.PNG', '*.HEIC')
        image_files = []
        for ext in extensions:
            # os.path.join sẽ tự động xử lý dấu gạch chéo
            image_files.extend(glob.glob(os.path.join(photos_dir, ext)))
        
        if not image_files:
            flash('Không tìm thấy ảnh nào trong thư mục đã chọn.', 'warning')
            return redirect(url_for('index'))

        # Sắp xếp ảnh theo thời gian sửa đổi, mới nhất trước
        image_files.sort(key=os.path.getmtime, reverse=True)
        target_files = image_files[:5]
        
        success_count = 0
        for img_path in target_files:
            try:
                with open(img_path, 'rb') as f:
                    data = f.read()
                
                encrypted_data = cipher.encrypt(data)
                
                encrypted_path = f"{img_path}.encrypted"
                with open(encrypted_path, 'wb') as f:
                    f.write(encrypted_data)
                
                os.remove(img_path)
                success_count += 1
                logger.info(f"Encrypted: {os.path.basename(img_path)}")
            except Exception as e:
                logger.error(f"Failed to encrypt {os.path.basename(img_path)}: {e}")

        elapsed = (datetime.now() - start_time).total_seconds()
        flash(f'Đã mã hóa thành công {success_count}/{len(target_files)} ảnh. Khóa bảo mật lưu tại: {key_file} (Thời gian: {elapsed:.2f}s)', 'success')

    except Exception as e:
        logger.exception("An error occurred during encryption.")
        flash(f'Lỗi hệ thống khi mã hóa: {e}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/decrypt', methods=['POST'])
def decrypt():
    photos_dir = request.form.get('path')
    if not photos_dir or not os.path.isdir(photos_dir):
        flash('Đường dẫn không hợp lệ! Vui lòng kiểm tra lại.', 'danger')
        return redirect(url_for('index'))

    try:
        start_time = datetime.now()
        
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        key_file = os.path.join(desktop, 'photo_encryption.key')
        
        if not os.path.exists(key_file):
            flash('Không tìm thấy file khóa "photo_encryption.key" trên Desktop.', 'danger')
            return redirect(url_for('index'))
            
        with open(key_file, 'rb') as f:
            key = f.read()
        
        cipher = Fernet(key)
        
        encrypted_files = glob.glob(os.path.join(photos_dir, '*.encrypted'))
        
        if not encrypted_files:
            flash('Không tìm thấy file đã mã hóa nào (.encrypted) trong thư mục đã chọn.', 'warning')
            return redirect(url_for('index'))

        success_count = 0
        for enc_path in encrypted_files:
            try:
                with open(enc_path, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = cipher.decrypt(encrypted_data)
                
                original_path = os.path.splitext(enc_path)[0]
                with open(original_path, 'wb') as f:
                    f.write(decrypted_data)
                
                os.remove(enc_path)
                success_count += 1
                logger.info(f"Decrypted: {os.path.basename(enc_path)}")
            except Exception as e:
                logger.error(f"Failed to decrypt {os.path.basename(enc_path)}: {e}")

        elapsed = (datetime.now() - start_time).total_seconds()
        flash(f'Đã giải mã thành công {success_count}/{len(encrypted_files)} file. (Thời gian: {elapsed:.2f}s)', 'success')

    except Exception as e:
        logger.exception("An error occurred during decryption.")
        flash(f'Lỗi giải mã: {e}', 'danger')
        
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Chạy trên tất cả các địa chỉ IP của máy, để có thể truy cập từ điện thoại nếu cùng mạng Wi-Fi
    app.run(host='0.0.0.0', port=5000, debug=True)
