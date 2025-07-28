from flask import Flask, render_template, redirect, url_for, flash
import os
import glob
import string
from cryptography.fernet import Fernet

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Helper: tìm thư mục DCIM/Camera

def find_camera_path():
    for drive in string.ascii_uppercase:
        path = f"{drive}:/DCIM/Camera"
        if os.path.isdir(path):
            return path
    return None

# Helper: load hoặc tạo key trên Desktop
def load_or_create_key():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    key_file = os.path.join(desktop, 'secret.key')
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
    phone_dir = find_camera_path()
    if not phone_dir:
        flash('Không tìm thấy thư mục DCIM/Camera trên điện thoại.', 'danger')
        return redirect(url_for('index'))

    key, key_file = load_or_create_key()
    cipher = Fernet(key)

    # lấy 5 ảnh mới nhất
    exts = ('*.jpg','*.jpeg','*.png')
    imgs = []
    for e in exts:
        imgs.extend(glob.glob(os.path.join(phone_dir, e)))
    if not imgs:
        flash('Không tìm thấy ảnh nào để mã hóa.', 'warning')
        return redirect(url_for('index'))
    imgs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    targets = imgs[:5]

    # mã hóa
    for img in targets:
        with open(img,'rb') as f:
            data = f.read()
        token = cipher.encrypt(data)
        enc_path = img + '.encrypted'
        with open(enc_path,'wb') as ef:
            ef.write(token)
        os.remove(img)
    flash(f'Đã mã hóa {len(targets)} ảnh. Khóa lưu tại: {key_file}', 'success')
    return redirect(url_for('index'))

@app.route('/decrypt')
def decrypt():
    phone_dir = find_camera_path()
    if not phone_dir:
        flash('Không tìm thấy thư mục DCIM/Camera trên điện thoại.', 'danger')
        return redirect(url_for('index'))

    # load key
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    key_file = os.path.join(desktop, 'secret.key')
    if not os.path.exists(key_file):
        flash('File khóa secret.key không tồn tại trên Desktop.', 'danger')
        return redirect(url_for('index'))
    with open(key_file,'rb') as kf:
        key = kf.read()
    cipher = Fernet(key)

    encs = glob.glob(os.path.join(phone_dir, '*.encrypted'))
    if not encs:
        flash('Không tìm thấy file .encrypted nào để giải mã.', 'warning')
        return redirect(url_for('index'))

    # giải mã
    for enc in encs:
        with open(enc,'rb') as ef:
            ed = ef.read()
        dec = cipher.decrypt(ed)
        orig = enc.replace('.encrypted','')
        with open(orig,'wb') as df:
            df.write(dec)
        os.remove(enc)
    flash(f'Đã giải mã {len(encs)} ảnh.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)