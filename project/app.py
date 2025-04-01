from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import cv2
import pytesseract
from datetime import datetime
import re
import logging
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure key in production

# Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['SELECTABLE_OPTIONS'] = {
    'travel_purpose': ['اختر', 'نقل كفالة', 'تجديد اقامة 24 شهر', 'علاج', 'زيارة عائلية', 'أخرى'],
    'accommodation': ['اختر', 'فحص طبي', 'منزل عائلة', 'سكن طلابي', 'مستشفى', 'أخرى'],
    'visa_duration': [' اختر', 'نقل كفالة', 'تجديد اقامة', '6 أشهر', 'سنة', 'أكثر من سنة'],
    'entry_type': ['اختر', 'مرتين', 'متعددة الدخول'],
    'payment_method': ['اختر', 'تحويل بنكي', 'بطاقة ائتمان', 'دفع إلكتروني', 'تمويل', 'أخرى'],
    'application_type': ['اختر', 'عاجل', 'سريع', 'VIP', 'عادي', 'خاص']
}

# Configure logging
logging.basicConfig(
    filename='passport_reader.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
)

# Set Tesseract path (uncomment and configure for your OS)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows
# pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'  # macOS/Linux

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def preprocess_image(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("تعذر قراءة ملف الصورة")

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Enhance resolution
        gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        
        # Noise reduction
        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # Thresholding
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        
        return gray
    except Exception as e:
        logging.error(f"Image preprocessing failed: {str(e)}")
        raise

def extract_passport_data(image_path):
    try:
        # Preprocess image
        processed_img = preprocess_image(image_path)
        
        # OCR Configuration
        custom_config = r'--oem 3 --psm 6 -l eng+ara+fra'
        text = pytesseract.image_to_string(processed_img, config=custom_config)
        
        # Save extracted text for debugging
        debug_file = os.path.join(app.config['UPLOAD_FOLDER'], 'debug_extracted_text.txt')
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # Extract data
        data = {
            'passport_no': extract_passport_number(text),
            'family_name': extract_family_name(text),
            'given_name': extract_given_name(text),
            'nationality': extract_nationality(text),
            'date_of_birth': extract_date(text, 'date_of_birth'),
            'place_of_birth': extract_place_of_birth(text),
            'issue_date': extract_date(text, 'issue_date'),
            'expiry_date': extract_date(text, 'expiry_date'),
            'gender': extract_gender(text),
            'place_of_issue': extract_place_of_issue(text),
            'image_path': f"uploads/{os.path.basename(image_path)}",
            'raw_text': text[:500] + "..." if len(text) > 500 else text
        }
        
        logging.info(f"Extracted data: {str(data)}")
        return data
        
    except Exception as e:
        logging.error(f"Data extraction failed: {str(e)}")
        raise ValueError(f"Data extraction error: {str(e)}")

# Data extraction helper functions
def extract_passport_number(text):
    patterns = [
        r'[A-Z]{1,2}[0-9]{6,8}',  # International format
        r'P<([A-Z]{1,2}[0-9]{6,8})',  # MRZ format
        r'(?:رقم|Number)[\s:]*([A-Z0-9]{6,9})',  # Arabic/English labels
        r'[0-9]{2}[A-Z]{3}[0-9]{5}'  # Alternative format
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1) if len(match.groups()) > 0 else match.group(0)
    return ""

def extract_family_name(text):
    # Try MRZ format first
    mrz_match = re.search(r'P<[A-Z]+<<([A-Z]+)', text)
    if mrz_match:
        return mrz_match.group(1)
    
    # Try text labels
    label_match = re.search(r'(?:اسم العائلة|Family Name)[\s:]*([A-Z\u0600-\u06FF\s]+)', text, re.IGNORECASE)
    if label_match:
        return label_match.group(1).strip()
    
    return ""

def extract_given_name(text):
    # MRZ format
    mrz_match = re.search(r'P<[A-Z]+<<[A-Z]+<([A-Z<]+)', text)
    if mrz_match:
        names = mrz_match.group(1).split('<')
        return ' '.join([name for name in names if name])
    
    # Text labels
    label_match = re.search(r'(?:الاسم الأول|Given Name)[\s:]*([A-Z\u0600-\u06FF\s]+)', text, re.IGNORECASE)
    if label_match:
        return label_match.group(1).strip()
    
    return ""

def extract_nationality(text):
    # 3-letter country code
    code_match = re.search(r'Nationality[\s:]*([A-Z]{3})', text, re.IGNORECASE)
    if code_match:
        return code_match.group(1)
    
    # Full country name
    country_match = re.search(r'(?:جنسية|Nationality)[\s:]*([A-Z\u0600-\u06FF\s]+)', text, re.IGNORECASE)
    if country_match:
        return country_match.group(1).strip()
    
    return ""

def extract_date(text, date_type):
    date_patterns = [
        r'(\d{2}[./-]\d{2}[./-]\d{4})',  # DD/MM/YYYY
        r'(\d{4}[./-]\d{2}[./-]\d{2})',  # YYYY/MM/DD
        r'(\d{6})',  # YYMMDD
        r'(?:(?:تاريخ|Date)[\s:]*([\d/]+))'  # Arabic/English labels
    ]
    
    dates = []
    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        dates.extend(matches)
    
    if not dates:
        return ""
    
    # Try to parse dates (return first valid one)
    for date_str in dates:
        try:
            # Clean date string
            date_str = re.sub(r'[./-]', '', date_str)
            
            if len(date_str) == 6:  # YYMMDD format
                date = datetime.strptime(date_str, '%y%m%d')
            elif len(date_str) == 8:  # YYYYMMDD format
                date = datetime.strptime(date_str, '%Y%m%d')
            else:
                continue
                
            return date.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return ""

def extract_place_of_birth(text):
    place_match = re.search(r'(?:مكان الولادة|Place of Birth)[\s:]*([A-Z\u0600-\u06FF\s]+)', text, re.IGNORECASE)
    return place_match.group(1).strip() if place_match else ""

def extract_gender(text):
    gender_match = re.search(r'(?:الجنس|Sex)[\s:]*([MF\u0630\u0643\u0631\u0623\u0646\u062B\u0649])', text, re.IGNORECASE)
    if gender_match:
        gender = gender_match.group(1).upper()
        if gender in ['M', 'ذ', 'ك', 'ر']:
            return 'M'
        elif gender in ['F', 'أ', 'ن', 'ث', 'ى']:
            return 'F'
    return ""

def extract_place_of_issue(text):
    issue_match = re.search(r'(?:مكان الإصدار|Place of Issue)[\s:]*([A-Z\u0600-\u06FF\s]+)', text, re.IGNORECASE)
    return issue_match.group(1).strip() if issue_match else ""

# Routes
@app.route('/')
def index():
    return render_template('index.html', selectable_options=app.config['SELECTABLE_OPTIONS'])

@app.route('/result')
def result():
    if 'passport_data' not in session:
        return redirect(url_for('index'))
    return render_template('result.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': 'File type not allowed',
            'allowed_extensions': list(app.config['ALLOWED_EXTENSIONS'])
        }), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        data = extract_passport_data(filepath)
        session['passport_data'] = data
        
        return jsonify({
            'success': True,
            'redirect_url': url_for('result'),
            'data': {k: v for k, v in data.items() if k != 'raw_text'}
        })
        
    except Exception as e:
        logging.error(f"Upload failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to process passport image. Please ensure the image is clear and try again.'
        }), 500

@app.route('/submit', methods=['POST'])
def submit_form():
    try:
        if 'passport_data' not in session:
            raise ValueError('No passport data found in session')
        
        form_data = request.get_json()
        
        # Validate required fields
        required_fields = ['passport_no', 'family_name', 'given_name', 'nationality']
        for field in required_fields:
            if field not in form_data or not form_data[field]:
                raise ValueError(f'Missing required field: {field}')
        
        # Here you would typically save to database
        logging.info(f"Form submitted with data: {str(form_data)}")
        
        # Prepare response with all submitted data
        response_data = {
            'passport_info': {k: v for k, v in form_data.items() if k in [
                'passport_no', 'family_name', 'given_name', 'nationality',
                'date_of_birth', 'place_of_birth', 'issue_date',
                'expiry_date', 'gender', 'place_of_issue'
            ]},
            'additional_options': {k: v for k, v in form_data.items() if k in [
                'travel_purpose', 'accommodation', 'visa_duration',
                'entry_type', 'payment_method', 'application_type'
            ]}
        }
        
        return jsonify({
            'success': True,
            'message': 'تم حفظ البيانات بنجاح',
            'data': response_data
        })
        
    except Exception as e:
        logging.error(f"Form submission failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
