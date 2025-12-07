// Состояние приложения
const state = {
    selectedFile: null,
    authToken: localStorage.getItem('authToken') || '',
    parsedData: null,
    originalFilename: null,
    editedData: null
};

// Элементы DOM
const elements = {
    uploadArea: document.getElementById('uploadArea'),
    fileInput: document.getElementById('fileInput'),
    fileInfo: document.getElementById('fileInfo'),
    fileName: document.getElementById('fileName'),
    fileSize: document.getElementById('fileSize'),
    removeFile: document.getElementById('removeFile'),
    parseBtn: document.getElementById('parseBtn'),

    uploadSection: document.getElementById('uploadSection'),
    progressSection: document.getElementById('progressSection'),
    resultsSection: document.getElementById('resultsSection'),
    errorSection: document.getElementById('errorSection'),

    progressFill: document.getElementById('progressFill'),
    progressPercentage: document.getElementById('progressPercentage'),

    editableData: document.getElementById('editableData'),
    headerInfo: document.getElementById('headerInfo'),
    itemsTable: document.getElementById('itemsTable'),
    summaryInfo: document.getElementById('summaryInfo'),
    jsonContent: document.getElementById('jsonContent'),

    errorMessage: document.getElementById('errorMessage'),

    newParseBtn: document.getElementById('newParseBtn'),
    retryBtn: document.getElementById('retryBtn'),
    downloadJsonBtn: document.getElementById('downloadJsonBtn'),
    copyJsonBtn: document.getElementById('copyJsonBtn'),
    toggleJsonBtn: document.getElementById('toggleJsonBtn'),
    saveAndContinueBtn: document.getElementById('saveAndContinueBtn'),

    settingsBtn: document.getElementById('settingsBtn'),
    settingsModal: document.getElementById('settingsModal'),
    closeModal: document.getElementById('closeModal'),
    cancelSettings: document.getElementById('cancelSettings'),
    saveSettings: document.getElementById('saveSettings'),
    authTokenInput: document.getElementById('authToken')
};

// Инициализация
function init() {
    setupEventListeners();

    // Проверяем токен при загрузке
    if (!state.authToken) {
        showModal();
    } else {
        elements.authTokenInput.value = state.authToken;
    }
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Upload area
    elements.uploadArea.addEventListener('click', () => elements.fileInput.click());
    elements.uploadArea.addEventListener('dragover', handleDragOver);
    elements.uploadArea.addEventListener('dragleave', handleDragLeave);
    elements.uploadArea.addEventListener('drop', handleDrop);

    // File input
    elements.fileInput.addEventListener('change', handleFileSelect);
    elements.removeFile.addEventListener('click', removeFile);

    // Parse button
    elements.parseBtn.addEventListener('click', parseDocument);

    // Action buttons
    elements.newParseBtn.addEventListener('click', resetApp);
    elements.retryBtn.addEventListener('click', resetApp);
    elements.downloadJsonBtn.addEventListener('click', downloadJson);
    elements.copyJsonBtn.addEventListener('click', copyJson);
    elements.toggleJsonBtn.addEventListener('click', toggleJson);
    elements.saveAndContinueBtn.addEventListener('click', saveAndContinue);

    // Settings
    elements.settingsBtn.addEventListener('click', showModal);
    elements.closeModal.addEventListener('click', hideModal);
    elements.cancelSettings.addEventListener('click', hideModal);
    elements.saveSettings.addEventListener('click', saveSettings);

    // Modal backdrop click
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            hideModal();
        }
    });
}

// File handling
function handleDragOver(e) {
    e.preventDefault();
    elements.uploadArea.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    elements.uploadArea.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    elements.uploadArea.classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFile(file) {
    // Проверка типа файла
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png', 'image/tiff', 'image/bmp'];
    const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
        showError('📄 Неподдерживаемый формат файла. Загрузите PDF, JPG, PNG, TIFF или BMP.');
        return;
    }

    // Проверка размера файла (макс 50MB)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
        const sizeMB = (file.size / 1024 / 1024).toFixed(1);
        showError(`📄 Файл слишком большой (${sizeMB}МБ). Максимальный размер: 50МБ.`);
        return;
    }

    state.selectedFile = file;
    state.originalFilename = file.name;
    displayFileInfo(file);
}

function displayFileInfo(file) {
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);
    elements.fileInfo.style.display = 'flex';
    elements.uploadArea.style.display = 'none';
    elements.parseBtn.disabled = false;
}

function removeFile() {
    state.selectedFile = null;
    elements.fileInfo.style.display = 'none';
    elements.uploadArea.style.display = 'block';
    elements.parseBtn.disabled = true;
    elements.fileInput.value = '';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Parsing
async function parseDocument() {
    if (!state.selectedFile) {
        showError('📄 Пожалуйста, выберите файл');
        return;
    }

    if (!state.authToken) {
        showModal();
        return;
    }

    // Показываем прогресс
    showSection('progress');

    try {
        // Создаем FormData
        const formData = new FormData();
        formData.append('file', state.selectedFile);

        // Симуляция прогресса
        simulateProgress();

        // Отправляем запрос
        const response = await fetch('/parse', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${state.authToken}`
            },
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorInfo = typeof errorData.detail === 'object' ? errorData.detail : { message: errorData.detail };

            // Обработка различных типов ошибок
            let userMessage = '';

            if (response.status === 401) {
                userMessage = '🔐 Неверная авторизация. Проверьте токен в настройках.';
                // Открываем модальное окно настроек
                setTimeout(() => showModal(), 1000);
            } else if (errorInfo.error_code) {
                // Новый формат с кодами ошибок
                const code = errorInfo.error_code;
                const message = errorInfo.message || 'Неизвестная ошибка';

                // Добавляем эмодзи в зависимости от типа ошибки
                let emoji = '❌';
                if (code === 'E001') emoji = '⚠️';  // Service unavailable
                else if (code === 'E004') emoji = '⏱️';  // Timeout
                else if (code === 'E005') emoji = '🌐';  // Network
                else if (code.startsWith('E00')) emoji = '⚙️';  // Config errors

                userMessage = `${emoji} ${message}`;

                // Добавляем код ошибки только для технических проблем (не показываем клиенту детали)
                if (['E002', 'E003', 'E099'].includes(code)) {
                    userMessage += ` [${code}]`;
                }
            } else if (response.status === 400) {
                // Ошибки валидации - показываем как есть
                userMessage = `📄 ${errorInfo.message || 'Неверный формат файла или слишком большой размер'}`;
            } else if (response.status === 413) {
                userMessage = '📄 Файл слишком большой. Максимальный размер: 50МБ.';
            } else {
                // Другие HTTP ошибки
                userMessage = errorInfo.message || `Не удалось обработать запрос. Попробуйте снова или свяжитесь с поддержкой.`;
            }

            throw new Error(userMessage);
        }

        const data = await response.json();

        if (data.success) {
            state.parsedData = data;
            displayResults(data);
        } else {
            throw new Error(data.error || '❌ Не удалось обработать документ. Попробуйте снова.');
        }

    } catch (error) {
        console.error('Parse error:', error);
        showError(error.message || '❌ Произошла ошибка при обработке документа. Попробуйте снова или свяжитесь с поддержкой.');
    }
}

function simulateProgress() {
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress > 90) {
            progress = 90;
            clearInterval(interval);
        }
        updateProgress(progress);
    }, 500);

    // Сохраняем интервал для возможной очистки
    state.progressInterval = interval;
}

function updateProgress(percentage) {
    percentage = Math.min(100, Math.max(0, percentage));
    elements.progressFill.style.width = percentage + '%';
    elements.progressPercentage.textContent = Math.round(percentage) + '%';
}

// Display results
function displayResults(data) {
    // Очищаем интервал прогресса
    if (state.progressInterval) {
        clearInterval(state.progressInterval);
    }
    updateProgress(100);

    setTimeout(() => {
        showSection('results');

        const parsedData = data.data;

        // Display editable form
        displayEditableData(parsedData);

        // Header information
        displayHeaderInfo(parsedData);

        // Items table
        displayItemsTable(parsedData.line_items || parsedData.items || []);

        // Summary
        displaySummary(parsedData);

        // Raw JSON
        elements.jsonContent.textContent = JSON.stringify(data, null, 2);
    }, 500);
}

function displayHeaderInfo(data) {
    const fields = [
        { label: 'Номер документа', key: 'invoice_number' },
        { label: 'Дата документа', key: 'invoice_date' },
        { label: 'Поставщик', key: 'supplier_name' },
        { label: 'Покупатель', key: 'customer_name' },
        { label: 'Валюта', key: 'currency' }
    ];

    let html = '';
    fields.forEach(field => {
        const value = data[field.key] || 'Н/Д';
        html += `
            <div class="info-item">
                <span class="info-label">${field.label}:</span>
                <span class="info-value">${value}</span>
            </div>
        `;
    });

    elements.headerInfo.innerHTML = html;
}

function displayItemsTable(items) {
    if (!items || items.length === 0) {
        elements.itemsTable.innerHTML = '<p style="padding: 20px; text-align: center; color: var(--text-secondary);">Товары не найдены</p>';
        return;
    }

    let html = `
        <thead>
            <tr>
                <th>№</th>
                <th>Наименование</th>
                <th>Количество</th>
                <th>Ед. изм.</th>
                <th>Цена</th>
                <th>Сумма</th>
            </tr>
        </thead>
        <tbody>
    `;

    items.forEach((item, index) => {
        html += `
            <tr>
                <td>${index + 1}</td>
                <td>${item.description || 'Н/Д'}</td>
                <td>${item.quantity !== undefined ? item.quantity : 'Н/Д'}</td>
                <td>${item.unit || 'Н/Д'}</td>
                <td>${item.unit_price !== undefined ? formatNumber(item.unit_price) : 'Н/Д'}</td>
                <td><strong>${item.total_price !== undefined ? formatNumber(item.total_price) : 'Н/Д'}</strong></td>
            </tr>
        `;
    });

    html += '</tbody>';
    elements.itemsTable.innerHTML = html;
}

function displaySummary(data) {
    const fields = [
        { label: 'Сумма без НДС', key: 'subtotal' },
        { label: 'НДС', key: 'tax_amount' },
        { label: 'Итого', key: 'total_amount', highlight: true }
    ];

    let html = '';
    fields.forEach(field => {
        const value = data[field.key] !== undefined ? formatNumber(data[field.key]) + ' ' + (data.currency || '') : 'Н/Д';
        const style = field.highlight ? 'font-size: 1.2rem; font-weight: 700; color: var(--primary-color);' : '';
        html += `
            <div class="info-item">
                <span class="info-label">${field.label}:</span>
                <span class="info-value" style="${style}">${value}</span>
            </div>
        `;
    });

    elements.summaryInfo.innerHTML = html;
}

function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(num);
}

// Actions
function downloadJson() {
    if (!state.parsedData) return;

    const dataStr = JSON.stringify(state.parsedData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `invoice_parsed_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('Файл скачан');
}

function copyJson() {
    if (!state.parsedData) return;

    const dataStr = JSON.stringify(state.parsedData, null, 2);
    navigator.clipboard.writeText(dataStr).then(() => {
        showToast('Скопировано в буфер обмена');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Ошибка копирования', true);
    });
}

function toggleJson() {
    const isVisible = elements.jsonContent.style.display !== 'none';
    elements.jsonContent.style.display = isVisible ? 'none' : 'block';
    elements.toggleJsonBtn.classList.toggle('active');
}

// Toast notifications
function showToast(message, isError = false) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 30px;
        left: 50%;
        transform: translateX(-50%);
        background: ${isError ? 'var(--danger-color)' : 'var(--secondary-color)'};
        color: white;
        padding: 15px 30px;
        border-radius: 12px;
        box-shadow: var(--shadow-lg);
        z-index: 2000;
        animation: fadeInUp 0.3s ease;
        font-weight: 500;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// Section management
function showSection(section) {
    elements.uploadSection.style.display = 'none';
    elements.progressSection.style.display = 'none';
    elements.resultsSection.style.display = 'none';
    elements.errorSection.style.display = 'none';

    switch(section) {
        case 'upload':
            elements.uploadSection.style.display = 'block';
            break;
        case 'progress':
            elements.progressSection.style.display = 'block';
            break;
        case 'results':
            elements.resultsSection.style.display = 'block';
            break;
        case 'error':
            elements.errorSection.style.display = 'block';
            break;
    }
}

function showError(message) {
    // Конвертируем URL в кликабельные ссылки
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const messageWithLinks = message.replace(urlRegex, '<a href="$1" target="_blank">$1</a>');

    elements.errorMessage.innerHTML = messageWithLinks;
    showSection('error');
}

function resetApp() {
    state.selectedFile = null;
    state.parsedData = null;
    removeFile();
    updateProgress(0);
    showSection('upload');
}

// Settings modal
function showModal() {
    elements.settingsModal.classList.add('active');
    elements.authTokenInput.value = state.authToken;
    elements.authTokenInput.focus();
}

function hideModal() {
    elements.settingsModal.classList.remove('active');
}

function saveSettings() {
    const token = elements.authTokenInput.value.trim();
    if (!token) {
        showToast('Пожалуйста, введите токен авторизации', true);
        return;
    }

    state.authToken = token;
    localStorage.setItem('authToken', token);
    hideModal();
    showToast('Настройки сохранены');
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // ESC to close modal
    if (e.key === 'Escape' && elements.settingsModal.classList.contains('active')) {
        hideModal();
    }

    // Enter to save settings
    if (e.key === 'Enter' && elements.settingsModal.classList.contains('active')) {
        saveSettings();
    }
});

// Field label mappings (Russian labels for fields)
const fieldLabels = {
    // Document Info
    'document_type': 'Тип документа:',
    'document_number': 'Номер документа:',
    'document_date': 'Дата документа:',
    'document_date_normalized': 'Дата (нормализованная):',
    'location': 'Местоположение:',
    'currency': 'Валюта:',

    // Parties - Supplier
    'name': 'Название:',
    'account_number': 'Номер счета:',
    'bank': 'Банк:',
    'address': 'Адрес:',
    'phone': 'Телефон:',
    'edrpou': 'ЄДРПОУ:',
    'ipn': 'ІПН:',

    // References
    'contract_number': 'Номер контракта:',
    'basis_document': 'Основание:',

    // Totals
    'total': 'Сумма без НДС:',
    'vat': 'НДС:',
    'total_with_vat': 'Итого с НДС:',

    // Amounts in words
    'total_in_words': 'Сумма прописью:',
    'vat_in_words': 'НДС прописью:',

    // Line items
    'line_number': '№',
    'article': 'Артикул',
    'product_name': 'Товары (роботи, послуги)',
    'application_mode': 'Режим полімерізації',
    'ukt_zed': 'Код УКТЗЕД',
    'quantity': 'Кількість',
    'price_excluding_vat': 'Ціна без ПДВ',
    'amount_excluding_vat': 'Сума без ПДВ',

    // Invoice fields (alternative)
    'invoice_number': 'Номер счета:',
    'invoice_date': 'Дата счета:',
    'supplier_name': 'Поставщик:',
    'customer_name': 'Покупатель:',
    'description': 'Наименование',
    'unit': 'Ед. изм.',
    'unit_price': 'Цена',
    'total_price': 'Сумма',
    'subtotal': 'Сумма без НДС:',
    'tax_amount': 'НДС:',
    'total_amount': 'Итого:',

    // Additional fields
    'role': 'Роль:',
    'is_signed': 'Подписано:',
    'is_stamped': 'Печать:',
    'stamp_content': 'Содержимое печати:',
    'label_raw': 'Метка:',
    'value_raw': 'Значение:'
};

// Display editable data form
function displayEditableData(data) {
    if (!elements.editableData) return;

    let html = '<div class="editable-data-grid">';

    // Helper function to get label from data or fallback
    const getLabel = (obj, key) => {
        // Check if object has _label for this key
        const labelKey = key + '_label';
        if (obj && obj[labelKey]) {
            return obj[labelKey];
        }
        // Fallback to predefined labels
        return fieldLabels[key] || key;
    };

    // Helper function to create editable field
    const createField = (key, value, label, parentObj) => {
        // Skip _label fields themselves
        if (key.endsWith('_label')) return '';

        const fieldId = `edit_${key}_${Math.random().toString(36).substr(2, 9)}`;
        const displayLabel = label || getLabel(parentObj, key);
        const fieldValue = value !== null && value !== undefined ? value : '';

        // For boolean values
        if (typeof value === 'boolean') {
            return `
                <div class="editable-field">
                    <label class="editable-label" for="${fieldId}">${displayLabel}</label>
                    <select id="${fieldId}" class="editable-input" data-key="${key}">
                        <option value="true" ${value ? 'selected' : ''}>Да</option>
                        <option value="false" ${!value ? 'selected' : ''}>Нет</option>
                    </select>
                </div>
            `;
        }

        // For string/number values
        if (typeof fieldValue === 'string' && fieldValue.length > 60) {
            return `
                <div class="editable-field">
                    <label class="editable-label" for="${fieldId}">${displayLabel}</label>
                    <textarea id="${fieldId}" class="editable-textarea" data-key="${key}">${escapeHtml(fieldValue)}</textarea>
                </div>
            `;
        } else {
            return `
                <div class="editable-field">
                    <label class="editable-label" for="${fieldId}">${displayLabel}</label>
                    <input type="text" id="${fieldId}" class="editable-input" data-key="${key}" value="${escapeHtml(fieldValue)}">
                </div>
            `;
        }
    };

    // Process document_info
    if (data.document_info) {
        html += '<div class="editable-group">';
        html += '<div class="editable-group-title"><i class="fas fa-file-alt"></i> Информация о документе</div>';
        for (const [key, value] of Object.entries(data.document_info)) {
            if (typeof value === 'object') continue;
            html += createField(key, value, null, data.document_info);
        }
        html += '</div>';
    }

    // Process parties (supplier and buyer)
    if (data.parties) {
        if (data.parties.supplier) {
            html += '<div class="editable-group">';
            html += '<div class="editable-group-title"><i class="fas fa-building"></i> Постачальник</div>';
            for (const [key, value] of Object.entries(data.parties.supplier)) {
                if (typeof value === 'object') continue;
                html += createField(key, value, null, data.parties.supplier);
            }
            html += '</div>';
        }

        if (data.parties.buyer) {
            html += '<div class="editable-group">';
            html += '<div class="editable-group-title"><i class="fas fa-user"></i> Покупатель</div>';
            for (const [key, value] of Object.entries(data.parties.buyer)) {
                if (typeof value === 'object') continue;
                html += createField(key, value, null, data.parties.buyer);
            }
            html += '</div>';
        }
    }

    // Process references
    if (data.references) {
        html += '<div class="editable-group">';
        html += '<div class="editable-group-title"><i class="fas fa-link"></i> Ссылки</div>';
        for (const [key, value] of Object.entries(data.references)) {
            if (typeof value === 'object') continue;
            html += createField(key, value, null, data.references);
        }
        html += '</div>';
    }

    // Process totals
    if (data.totals) {
        html += '<div class="editable-group">';
        html += '<div class="editable-group-title"><i class="fas fa-calculator"></i> Итоговые суммы</div>';
        for (const [key, value] of Object.entries(data.totals)) {
            if (typeof value === 'object') continue;
            html += createField(key, value, null, data.totals);
        }
        html += '</div>';
    }

    html += '</div>';

    // Process additional top-level fields (for simpler invoice structures)
    const processedSections = ['document_info', 'parties', 'references', 'totals', 'amounts_in_words',
                                'signatures', 'other_fields', 'line_items', 'items', 'column_mapping'];
    const remainingFields = Object.entries(data).filter(([key]) => !processedSections.includes(key));

    if (remainingFields.length > 0) {
        html += '<div class="editable-group">';
        html += '<div class="editable-group-title"><i class="fas fa-info-circle"></i> Дополнительная информация</div>';
        for (const [key, value] of remainingFields) {
            if (typeof value === 'object' || key.endsWith('_label')) continue;
            html += createField(key, value, null, data);
        }
        html += '</div>';
    }

    // Process line_items as table
    const items = data.line_items || data.items || [];
    if (items.length > 0) {
        html += '<div class="editable-group" style="grid-column: 1 / -1;">';
        html += '<div class="editable-group-title"><i class="fas fa-list"></i> Товары и услуги</div>';
        html += '<div class="table-container">';
        html += '<table class="editable-items-table">';

        // Table header
        const firstItem = items[0];
        html += '<thead><tr>';
        for (const key of Object.keys(firstItem)) {
            if (key.endsWith('_label')) continue;
            const label = data.column_mapping?.[key] || getLabel(firstItem, key);
            html += `<th>${label}</th>`;
        }
        html += '</tr></thead>';

        // Table body
        html += '<tbody>';
        items.forEach((item, index) => {
            html += '<tr>';
            for (const [key, value] of Object.entries(item)) {
                if (key.endsWith('_label')) continue;
                const fieldId = `item_${index}_${key}`;
                html += `<td><input type="text" id="${fieldId}" class="item-input" data-index="${index}" data-key="${key}" value="${escapeHtml(value || '')}"></td>`;
            }
            html += '</tr>';
        });
        html += '</tbody>';
        html += '</table>';
        html += '</div>';
        html += '</div>';
    }

    elements.editableData.innerHTML = html;
}

// Collect edited data from form
function collectEditedData() {
    if (!state.parsedData) return null;

    // Deep clone the original data
    const editedData = JSON.parse(JSON.stringify(state.parsedData.data));

    // Collect all edited fields
    const inputs = document.querySelectorAll('.editable-input, .editable-textarea');
    inputs.forEach(input => {
        const key = input.dataset.key;
        let value = input.value;

        // Convert value types
        if (input.tagName === 'SELECT') {
            value = value === 'true';
        } else if (!isNaN(value) && value !== '') {
            // Try to preserve original number type
            const originalValue = getOriginalValue(editedData, key);
            if (typeof originalValue === 'number') {
                value = parseFloat(value);
            }
        }

        // Update in nested structure
        updateNestedValue(editedData, key, value);
    });

    // Collect line items
    const itemInputs = document.querySelectorAll('.item-input');
    itemInputs.forEach(input => {
        const index = parseInt(input.dataset.index);
        const key = input.dataset.key;
        let value = input.value;

        // Try to preserve number types
        if (editedData.line_items && editedData.line_items[index]) {
            const originalValue = editedData.line_items[index][key];
            if (typeof originalValue === 'number' && !isNaN(value)) {
                value = parseFloat(value);
            }
            editedData.line_items[index][key] = value;
        } else if (editedData.items && editedData.items[index]) {
            const originalValue = editedData.items[index][key];
            if (typeof originalValue === 'number' && !isNaN(value)) {
                value = parseFloat(value);
            }
            editedData.items[index][key] = value;
        }
    });

    return editedData;
}

// Get original value from nested object
function getOriginalValue(obj, key) {
    for (const [k, v] of Object.entries(obj)) {
        if (k === key) {
            return v;
        }
        if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
            const result = getOriginalValue(v, key);
            if (result !== undefined) {
                return result;
            }
        }
    }
    return undefined;
}

// Update nested value in object
function updateNestedValue(obj, key, value) {
    // Try to find and update the key in nested objects
    for (const [k, v] of Object.entries(obj)) {
        if (k === key) {
            obj[k] = value;
            return true;
        }
        if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
            if (updateNestedValue(v, key, value)) {
                return true;
            }
        }
    }
    return false;
}

// Save and continue function
async function saveAndContinue() {
    if (!state.parsedData || !state.originalFilename) {
        showToast('Нет данных для сохранения', true);
        return;
    }

    if (!state.authToken) {
        showModal();
        return;
    }

    try {
        // Collect edited data
        const editedData = collectEditedData();
        state.editedData = editedData;

        // Show loading state
        elements.saveAndContinueBtn.disabled = true;
        elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Сохранение...';

        // Send to server
        const response = await fetch('/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.authToken}`
            },
            body: JSON.stringify({
                original_filename: state.originalFilename,
                data: editedData
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || 'Не удалось сохранить данные');
        }

        const result = await response.json();

        // Show success message
        showToast(`✅ ${result.message || 'Данные успешно сохранены!'}`);

        // Reset button
        elements.saveAndContinueBtn.disabled = false;
        elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-save"></i> Сохранить и продолжить';

        // Optional: reset to upload new document
        setTimeout(() => {
            if (confirm('Хотите загрузить новый документ?')) {
                resetApp();
            }
        }, 1500);

    } catch (error) {
        console.error('Save error:', error);
        showToast('❌ ' + error.message, true);

        // Reset button
        elements.saveAndContinueBtn.disabled = false;
        elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-save"></i> Сохранить и продолжить';
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', init);

