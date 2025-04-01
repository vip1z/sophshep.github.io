// script.js - Enhanced Passport Reader Script
document.addEventListener('DOMContentLoaded', function() {
    initializeUploadAreas();
    setupFormSubmission();
    setupDebugTools();
});

// Initialize all upload areas
function initializeUploadAreas() {
    const uploadAreas = [
        { elementId: 'uploadArea', inputId: 'passportFile', type: 'passport' },
        { elementId: 'personalPhotoUpload', inputId: 'personalPhoto', type: 'photo' },
        { elementId: 'optionalDocsUpload', inputId: 'optionalDocs', type: 'docs' }
    ];

    uploadAreas.forEach(area => {
        const uploadArea = document.getElementById(area.elementId);
        const fileInput = document.getElementById(area.inputId);

        if (uploadArea && fileInput) {
            setupDragAndDrop(uploadArea, fileInput, area.type);
        }
    });
}

// Setup drag and drop functionality
function setupDragAndDrop(uploadArea, fileInput, type) {
    // Click handler
    uploadArea.addEventListener('click', () => fileInput.click());

    // Drag and drop handlers
    ['dragover', 'dragenter'].forEach(event => {
        uploadArea.addEventListener(event, (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragging');
        });
    });

    ['dragleave', 'dragend'].forEach(event => {
        uploadArea.addEventListener(event, () => {
            uploadArea.classList.remove('dragging');
        });
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragging');
        
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleFileUpload(fileInput.files[0], type);
        }
    });

    // Regular file input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFileUpload(e.target.files[0], type);
        }
    });
}

// Handle file upload based on type
function handleFileUpload(file, type) {
    if (!file) return;

    const feedbackElement = document.getElementById(`${type}UploadFeedback`);
    const previewElement = document.getElementById(`${type}Preview`);

    // Validate file
    if (!validateFile(file, type)) {
        showFeedback(feedbackElement, 'نوع الملف غير مدعوم', 'error');
        return;
    }

    showFeedback(feedbackElement, 'جاري معالجة الملف...', 'loading');

    if (type === 'passport') {
        processPassportImage(file, feedbackElement, previewElement);
    } else {
        // For other file types (photo/docs)
        previewFile(file, previewElement);
        showFeedback(feedbackElement, 'تم تحميل الملف بنجاح', 'success');
    }
}

// Validate file type and size
function validateFile(file, type) {
    const validTypes = {
        passport: ['image/jpeg', 'image/png', 'application/pdf'],
        photo: ['image/jpeg', 'image/png'],
        docs: ['image/jpeg', 'image/png', 'application/pdf']
    };

    const maxSizes = {
        passport: 10 * 1024 * 1024, // 10MB
        photo: 500 * 1024, // 500KB
        docs: 500 * 1024 // 500KB
    };

    return validTypes[type].includes(file.type) && file.size <= maxSizes[type];
}

// Process passport image and extract data
async function processPassportImage(file, feedbackElement, previewElement) {
    try {
        showLoading(true);
        
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'فشل في معالجة الجواز');
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.message || 'تعذر استخراج البيانات');
        }

        // Store data in session
        sessionStorage.setItem('passportData', JSON.stringify(result.data));
        
        // Fill form and show preview
        fillFormData(result.data);
        previewFile(file, previewElement);
        showFeedback(feedbackElement, 'تم استخراج بيانات الجواز', 'success');

        // Auto-redirect to results if on mobile
        if (window.innerWidth < 768) {
            window.location.href = result.redirect_url;
        }

    } catch (error) {
        console.error('Passport processing error:', error);
        showFeedback(feedbackElement, error.message, 'error');
        showErrorNotification(error.message);
    } finally {
        showLoading(false);
    }
}

// Fill form with extracted data
function fillFormData(data) {
    const fieldMap = {
        'passportNo': 'passport_no',
        'familyName': 'family_name',
        'givenName': 'given_name',
        'nationality': 'nationality',
        'dateOfBirth': 'date_of_birth',
        'placeOfBirth': 'place_of_birth',
        'issueDate': 'issue_date',
        'expiryDate': 'expiry_date',
        'gender': 'gender',
        'placeOfIssue': 'place_of_issue'
    };

    Object.entries(fieldMap).forEach(([fieldId, dataKey]) => {
        const element = document.getElementById(fieldId);
        if (element && data[dataKey]) {
            element.value = data[dataKey];
            
            // Trigger change event for dependent fields
            const event = new Event('change');
            element.dispatchEvent(event);
        }
    });

    // Update nationality dropdown
    if (data.nationality) {
        const nationalitySelect = document.getElementById('nationality');
        if (nationalitySelect) {
            for (let option of nationalitySelect.options) {
                if (option.value === data.nationality) {
                    option.selected = true;
                    break;
                }
            }
        }
    }
}

// Preview uploaded file
function previewFile(file, previewElement) {
    if (!previewElement) return;

    if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
            previewElement.innerHTML = `<img src="${e.target.result}" class="img-thumbnail" alt="Preview">`;
            previewElement.style.display = 'block';
        };
        reader.readAsDataURL(file);
    } else if (file.type === 'application/pdf') {
        previewElement.innerHTML = `
            <div class="pdf-preview">
                <i class="bi bi-file-earmark-pdf"></i>
                <span>${file.name}</span>
            </div>
        `;
        previewElement.style.display = 'block';
    }
}

// Form submission handler
function setupFormSubmission() {
    const form = document.getElementById('passportForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Validate required fields
        if (!validateForm()) {
            showErrorNotification('الرجاء ملء جميع الحقول المطلوبة');
            return;
        }

        try {
            showLoading(true);
            
            const formData = new FormData(form);
            const passportData = JSON.parse(sessionStorage.getItem('passportData') || {};
            
            // Merge form data with passport data
            const combinedData = {
                ...passportData,
                ...Object.fromEntries(formData.entries())
            };

            // Send to server
            const response = await fetch('/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(combinedData)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'فشل في إرسال البيانات');
            }

            // Redirect to success page or show message
            if (result.redirect_url) {
                window.location.href = result.redirect_url;
            } else {
                showSuccessNotification(result.message || 'تم إرسال البيانات بنجاح');
                // Reset form after 2 seconds
                setTimeout(() => form.reset(), 2000);
            }

        } catch (error) {
            console.error('Form submission error:', error);
            showErrorNotification(error.message || 'حدث خطأ أثناء الإرسال');
        } finally {
            showLoading(false);
        }
    });
}

// Form validation
function validateForm() {
    const requiredFields = [
        'passportNo', 'familyName', 'givenName',
        'nationality', 'dateOfBirth', 'gender'
    ];

    return requiredFields.every(fieldId => {
        const element = document.getElementById(fieldId);
        return element && element.value.trim() !== '';
    });
}

// UI Feedback Functions
function showLoading(show) {
    const loader = document.getElementById('globalLoader');
    if (loader) {
        loader.style.display = show ? 'flex' : 'none';
    }
}

function showFeedback(element, message, type) {
    if (!element) return;
    
    element.textContent = message;
    element.className = 'upload-feedback';
    element.classList.add(type);
    element.style.display = 'block';

    // Auto-hide after 5 seconds
    if (type !== 'loading') {
        setTimeout(() => {
            element.style.display = 'none';
        }, 5000);
    }
}

function showSuccessNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification success';
    notification.innerHTML = `
        <i class="bi bi-check-circle"></i>
        <span>${message}</span>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 500);
    }, 3000);
}

function showErrorNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification error';
    notification.innerHTML = `
        <i class="bi bi-exclamation-circle"></i>
        <span>${message}</span>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 500);
    }, 5000);
}

// Debug tools (for development)
function setupDebugTools() {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        const debugBtn = document.createElement('button');
        debugBtn.id = 'debugBtn';
        debugBtn.textContent = 'Debug';
        debugBtn.addEventListener('click', showDebugInfo);
        document.body.appendChild(debugBtn);
    }
}

function showDebugInfo() {
    const passportData = sessionStorage.getItem('passportData');
    console.log('Stored Passport Data:', passportData ? JSON.parse(passportData) : 'No data');
    
    // Add more debug info as needed
}
