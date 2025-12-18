// Состояние приложения
const state = {
    selectedFile: null,
    authToken: localStorage.getItem('authToken') || '',
    parsedData: null,
    originalFilename: null,
    editedData: null,
    interfaceRules: null,  // Правила интерфейса из interface-rules.json
    config: {
        maxFileSizeMB: 50  // Значение по умолчанию, загружается из API
    }
};

// Элементы DOM - инициализируются при загрузке DOM
const elements = {};

// Загрузка правил интерфейса
async function loadInterfaceRules() {
    try {
        const response = await fetch('/static/interface-rules.json');
        if (response.ok) {
            state.interfaceRules = await response.json();
            console.log('Interface rules loaded:', state.interfaceRules);
        } else {
            console.warn('Failed to load interface-rules.json, using defaults');
            state.interfaceRules = null;
        }
    } catch (error) {
        console.error('Error loading interface rules:', error);
        state.interfaceRules = null;
    }
}

// Загрузка конфигурации с сервера
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            state.config.maxFileSizeMB = config.max_file_size_mb || 50;
            console.log('Config loaded:', state.config);
        } else {
            console.warn('Failed to load config, using defaults');
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Инициализация элементов DOM
function initElements() {
    elements.uploadArea = document.getElementById('uploadArea');
    elements.fileInput = document.getElementById('fileInput');
    elements.fileInfo = document.getElementById('fileInfo');
    elements.fileName = document.getElementById('fileName');
    elements.fileSize = document.getElementById('fileSize');
    elements.removeFile = document.getElementById('removeFile');
    elements.parseButtons = document.getElementById('parseButtons');
    elements.parseFastBtn = document.getElementById('parseFastBtn');
    elements.parseDetailedBtn = document.getElementById('parseDetailedBtn');
    elements.uploadSection = document.getElementById('uploadSection');
    elements.progressSection = document.getElementById('progressSection');
    elements.resultsSection = document.getElementById('resultsSection');
    elements.errorSection = document.getElementById('errorSection');
    elements.progressFill = document.getElementById('progressFill');
    elements.progressPercentage = document.getElementById('progressPercentage');
    elements.editableData = document.getElementById('editableData');
    elements.errorMessage = document.getElementById('errorMessage');
    elements.newParseBtn = document.getElementById('newParseBtn');
    elements.retryBtn = document.getElementById('retryBtn');
    elements.backBtn = document.getElementById('backBtn');
    elements.saveAndContinueBtn = document.getElementById('saveAndContinueBtn');
    elements.logoutBtn = document.getElementById('logoutBtn');
    elements.authWarning = document.getElementById('authWarning');
}

// Инициализация
async function init() {
    // Инициализируем элементы DOM
    initElements();

    // Обновляем токен из localStorage (на случай, если он был сохранен на странице входа)
    state.authToken = localStorage.getItem('authToken') || '';

    // Проверяем авторизацию - если нет токена, перенаправляем на страницу входа
    // Сохраняем document_id в URL при редиректе, чтобы не потерять его
    if (!state.authToken) {
        const urlParams = new URLSearchParams(window.location.search);
        const documentId = urlParams.get('document_id');
        if (documentId) {
            window.location.href = `/login.html?redirect=/?document_id=${documentId}`;
        } else {
            window.location.href = '/login.html';
        }
        return;
    }

    // Загружаем конфигурацию и правила интерфейса
    await Promise.all([loadConfig(), loadInterfaceRules()]);

    setupEventListeners();

    // Токен есть, разрешаем загрузку файлов
    enableFileUpload();

    // Проверяем, есть ли document_id в URL для загрузки документа
    const urlParams = new URLSearchParams(window.location.search);
    const documentId = urlParams.get('document_id');
    if (documentId) {
        console.log(`Loading document ${documentId} for editing...`);
        await loadDocumentForEditing(parseInt(documentId));
    }
}

// Загрузка документа для редактирования
async function loadDocumentForEditing(documentId) {
    try {
        console.log(`loadDocumentForEditing called with documentId: ${documentId}, authToken: ${state.authToken ? 'present' : 'missing'}`);

        if (!state.authToken) {
            console.error('No auth token, redirecting to login...');
            const urlParams = new URLSearchParams(window.location.search);
            const documentId = urlParams.get('document_id');
            if (documentId) {
                window.location.href = `/login.html?redirect=/?document_id=${documentId}`;
            } else {
                window.location.href = '/login.html';
            }
            return;
        }

        showProgress();
        setProgress(10, 'Loading document...');

        console.log(`Fetching /api/documents/${documentId}...`);
        const response = await fetch(`/api/documents/${documentId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${state.authToken}`
            }
        });

        console.log(`Response status: ${response.status}`);

        if (!response.ok) {
            if (response.status === 401) {
                // Token expired, redirect to login
                localStorage.removeItem('authToken');
                window.location.href = '/login.html';
                return;
            }
            throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        setProgress(50, 'Processing data...');
        const result = await response.json();

        if (result.success && result.data) {
            setProgress(90, 'Displaying form...');

            // Set data for editing
            state.parsedData = {
                success: true,
                data: result.data,
                processed_at: new Date().toISOString()
            };

            // Set original_filename from data or use default value
            state.originalFilename = result.data.original_filename || `document_${documentId}`;

            // Show editing form
            hideProgress();

            // Show results section
            showSection('results');

            // Display data
            displayEditableData(result.data);

            setProgress(100, 'Done');
            setTimeout(() => hideProgress(), 500);
        } else {
            throw new Error('Document not found or data unavailable');
        }
    } catch (error) {
        console.error('Error loading document:', error);
        hideProgress();
        showError(`Failed to load document: ${error.message}`);
    }
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Проверяем, что элементы существуют
    if (!elements.uploadArea || !elements.fileInput) {
        console.error('Upload elements not found');
        return;
    }

    // Upload area
    elements.uploadArea.addEventListener('click', (e) => {
        // Проверяем авторизацию перед открытием диалога выбора файла
        if (!state.authToken) {
            showAuthRequiredMessage();
            return;
        }
        if (elements.fileInput) {
            elements.fileInput.click();
        }
    });
    elements.uploadArea.addEventListener('dragover', handleDragOver);
    elements.uploadArea.addEventListener('dragleave', handleDragLeave);
    elements.uploadArea.addEventListener('drop', handleDrop);

    // File input
    if (elements.fileInput) {
        elements.fileInput.addEventListener('change', handleFileSelect);
    }
    if (elements.removeFile) {
        elements.removeFile.addEventListener('click', removeFile);
    }

    // Parse buttons
    if (elements.parseFastBtn) {
        elements.parseFastBtn.addEventListener('click', () => parseDocument('fast'));
    }
    if (elements.parseDetailedBtn) {
        elements.parseDetailedBtn.addEventListener('click', () => parseDocument('detailed'));
    }

    // Action buttons
    if (elements.newParseBtn) {
        elements.newParseBtn.addEventListener('click', resetApp);
    }
    if (elements.retryBtn) {
        elements.retryBtn.addEventListener('click', resetApp);
    }
    if (elements.backBtn) {
        elements.backBtn.addEventListener('click', resetApp);
    }
    if (elements.saveAndContinueBtn) {
        elements.saveAndContinueBtn.addEventListener('click', saveAndContinue);
    }

    // Logout
    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener('click', handleLogout);
    }
}


// File handling
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    // Проверяем авторизацию перед drag over
    if (!state.authToken) {
        showAuthRequiredMessage();
        return;
    }
    if (elements.uploadArea) {
        elements.uploadArea.classList.add('drag-over');
    }
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    if (elements.uploadArea) {
        elements.uploadArea.classList.remove('drag-over');
    }
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();

    if (elements.uploadArea) {
        elements.uploadArea.classList.remove('drag-over');
    }

    // Проверяем авторизацию перед drop
    if (!state.authToken) {
        showAuthRequiredMessage();
        return;
    }

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    // Проверяем авторизацию перед выбором файла
    if (!state.authToken) {
        e.target.value = ''; // Очищаем выбор
        showAuthRequiredMessage();
        return;
    }

    const files = e.target.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFile(file) {
    // Проверка авторизации перед обработкой файла
    if (!state.authToken) {
        showAuthRequiredMessage();
        return;
    }

    // Проверка типа файла
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png', 'image/tiff', 'image/bmp'];
    const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
        showError('📄 Unsupported file format. Please upload PDF, JPG, PNG, TIFF or BMP.');
        return;
    }

    // Проверка размера файла
    const maxSize = state.config.maxFileSizeMB * 1024 * 1024;
    if (file.size > maxSize) {
        const sizeMB = (file.size / 1024 / 1024).toFixed(1);
        showError(`📄 File is too large (${sizeMB}MB). Maximum size: ${state.config.maxFileSizeMB}MB.`);
        return;
    }

    state.selectedFile = file;
    state.originalFilename = file.name;
    displayFileInfo(file);
}

// Показать сообщение о необходимости авторизации
function showAuthRequiredMessage() {
    showToast('Please log in first', true);
    // Автоматически открываем модальное окно авторизации
    setTimeout(() => {
                window.location.href = '/login.html';
    }, 500);
}

function displayFileInfo(file) {
    if (elements.fileName) elements.fileName.textContent = file.name;
    if (elements.fileSize) elements.fileSize.textContent = formatFileSize(file.size);
    if (elements.fileInfo) elements.fileInfo.style.display = 'flex';
    if (elements.uploadArea) elements.uploadArea.style.display = 'none';
    // Активируем кнопки анализа
    if (elements.parseFastBtn) {
        elements.parseFastBtn.disabled = false;
    }
    if (elements.parseDetailedBtn) {
        elements.parseDetailedBtn.disabled = false;
    }
}

function removeFile() {
    state.selectedFile = null;
    if (elements.fileInfo) elements.fileInfo.style.display = 'none';
    if (elements.uploadArea) elements.uploadArea.style.display = 'block';
    // Деактивируем кнопки анализа
    if (elements.parseFastBtn) {
        elements.parseFastBtn.disabled = true;
    }
    if (elements.parseDetailedBtn) {
        elements.parseDetailedBtn.disabled = true;
    }
    elements.fileInput.value = '';
}

// Включить/выключить загрузку файлов в зависимости от авторизации
function enableFileUpload() {
    if (!elements.uploadArea || !elements.fileInput) {
        console.error('Upload elements not found in enableFileUpload');
        return;
    }

    if (state.authToken) {
        // Разрешаем загрузку
        elements.uploadArea.style.pointerEvents = 'auto';
        elements.uploadArea.style.opacity = '1';
        elements.uploadArea.style.cursor = 'pointer';
        elements.fileInput.disabled = false;
        // Скрываем предупреждение
        const authWarning = document.getElementById('authWarning');
        if (authWarning) {
            authWarning.style.display = 'none';
        }
    } else {
        // Блокируем загрузку
        disableFileUpload();
    }
}

// Отключить загрузку файлов (при выходе)
function disableFileUpload() {
    elements.uploadArea.style.pointerEvents = 'none';
    elements.uploadArea.style.opacity = '0.6';
    elements.uploadArea.style.cursor = 'not-allowed';
    elements.fileInput.disabled = true;
    // Показываем предупреждение
    const authWarning = document.getElementById('authWarning');
    if (authWarning) {
        authWarning.style.display = 'block';
    }
    // Удаляем выбранный файл, если есть
    if (state.selectedFile) {
        removeFile();
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Parsing
async function parseDocument(mode = 'detailed') {
    if (!state.selectedFile) {
        showError('📄 Please select a file');
        return;
    }

    if (!state.authToken) {
                window.location.href = '/login.html';
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

        // Отправляем запрос с параметром mode
        const response = await fetch(`/parse?mode=${mode}`, {
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
                userMessage = '🔐 Invalid authorization. Please log in again.';
                // Перенаправляем на страницу входа
                setTimeout(() => {
                    window.location.href = '/login.html';
                }, 2000);
            } else if (errorInfo.error_code) {
                // Новый формат с кодами ошибок
                const code = errorInfo.error_code;
                const message = errorInfo.message || 'Unknown error';

                // Добавляем эмодзи в зависимости от типа ошибки
                let emoji = '❌';
                if (code === 'E001') emoji = '⚠️';  // Service unavailable
                else if (code === 'E004') emoji = '⏱️';  // Timeout
                else if (code === 'E005') emoji = '🌐';  // Network
                else if (code.startsWith('E00')) emoji = '⚙️';  // Config errors

                userMessage = `${emoji} ${message}`;

                // Добавляем код ошибки только для технических проблем (не показываем клиенту детали)
                if (['E002', 'E003', 'E006', 'E099'].includes(code)) {
                    userMessage += ` [${code}]`;
                }
            } else if (response.status === 400) {
                // Ошибки валидации - показываем как есть
                userMessage = `📄 ${errorInfo.message || 'Invalid file format or file too large'}`;
            } else if (response.status === 413) {
                userMessage = '📄 File is too large. Maximum size: 50MB.';
            } else {
                // Другие HTTP ошибки
                userMessage = errorInfo.message || `Failed to process request. Please try again or contact support.`;
            }

            throw new Error(userMessage);
        }

        const data = await response.json();

        if (data.success) {
            state.parsedData = data;
            displayResults(data);
        } else {
            throw new Error(data.error || '❌ Failed to process document. Please try again.');
        }

    } catch (error) {
        console.error('Parse error:', error);
        showError(error.message || '❌ An error occurred while processing the document. Please try again or contact support.');
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
    if (elements.progressFill) {
        elements.progressFill.style.width = percentage + '%';
    }
    if (elements.progressPercentage) {
        elements.progressPercentage.textContent = Math.round(percentage) + '%';
    }
}

function showProgress() {
    if (elements.progressSection) {
        elements.progressSection.style.display = 'block';
        elements.uploadSection.style.display = 'none';
        elements.resultsSection.style.display = 'none';
        elements.errorSection.style.display = 'none';
    }
}

function hideProgress() {
    if (elements.progressSection) {
        elements.progressSection.style.display = 'none';
    }
}

function setProgress(percentage, message) {
    updateProgress(percentage);
    // Можно добавить отображение сообщения, если есть элемент для этого
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
    }, 500);
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
    if (elements.uploadSection) elements.uploadSection.style.display = 'none';
    if (elements.progressSection) elements.progressSection.style.display = 'none';
    if (elements.resultsSection) elements.resultsSection.style.display = 'none';
    if (elements.errorSection) elements.errorSection.style.display = 'none';

    switch(section) {
        case 'upload':
            if (elements.uploadSection) elements.uploadSection.style.display = 'block';
            break;
        case 'progress':
            if (elements.progressSection) elements.progressSection.style.display = 'block';
            break;
        case 'results':
            if (elements.resultsSection) elements.resultsSection.style.display = 'block';
            break;
        case 'error':
            if (elements.errorSection) elements.errorSection.style.display = 'block';
            break;
    }
}

function showError(message) {
    // Конвертируем URL в кликабельные ссылки с экранированием для безопасности
    const urlRegex = /(https?:\/\/[^\s<>"']+)/g;

    if (elements.errorMessage) {
        // Сначала находим все URL в оригинальном сообщении
        const urls = [];
        let match;
        const tempMessage = message;
        while ((match = urlRegex.exec(tempMessage)) !== null) {
            urls.push(match[0]);
        }

        // Экранируем весь текст
        let escapedMessage = escapeHtml(message);

        // Заменяем экранированные URL на ссылки
        urls.forEach(url => {
            const escapedUrl = escapeHtml(url);
            escapedMessage = escapedMessage.replace(escapedUrl, `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapedUrl}</a>`);
        });

        elements.errorMessage.innerHTML = escapedMessage;
    }
    showSection('error');
}

function resetApp() {
    state.selectedFile = null;
    state.parsedData = null;
    removeFile();
    updateProgress(0);
    showSection('upload');
}

// Выход из системы
function handleLogout() {
    if (confirm('Are you sure you want to log out?')) {
        // Удаляем токен
        state.authToken = '';
        localStorage.removeItem('authToken');
        localStorage.removeItem('rememberMe');

        // Перенаправляем на страницу входа
        window.location.href = '/login.html';
    }
}


// Field label mappings - пустой объект, все метки берутся из данных (_label)
// Полностью мультиязычное решение без хардкода
const fieldLabels = {};

// Display editable data form
function displayEditableData(data) {
    if (!elements.editableData) {
        return;
    }

    let html = '<div class="editable-data-grid">';

    // Helper function to get label from data or fallback
    const getLabel = (obj, key) => {
        // Сначала проверяем, если значение само является объектом с _label
        if (obj && obj[key] && typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
            if (obj[key]._label) {
                return obj[key]._label;
            }
        }

        // Проверяем, есть ли отдельное поле key + '_label'
        const labelKey = key + '_label';
        if (obj && obj[labelKey]) {
            return obj[labelKey];
        }

        // Fallback to key (все метки берутся из данных, без хардкода)
        return key;
    };

    // Helper function to create editable field
    const createField = (key, value, label, parentObj) => {
        // Skip _label fields themselves
        if (key.endsWith('_label')) return '';

        // Skip empty values ONLY for handwritten/stamp fields
        // Fields that should be hidden if empty: handwritten_date, stamp_content
        const hiddenIfEmptyFields = ['handwritten_date', 'stamp_content'];
        const isHiddenField = hiddenIfEmptyFields.some(field => key.includes(field));

        if (isHiddenField && (value === null || value === undefined || value === '')) {
            return '';
        }

        // For all other fields, show them even if empty (but keep boolean false as it's a valid value)

        const fieldId = `edit_${key}_${Math.random().toString(36).substr(2, 9)}`;
        // Используем _label из данных, если есть
        // Приоритет: переданный label > getLabel (который ищет _label) > key
        // Полностью мультиязычное решение - используем только данные из документа
        let displayLabel = label;
        if (!displayLabel) {
            displayLabel = getLabel(parentObj, key);
        }
        if (!displayLabel || displayLabel === key) {
            displayLabel = key; // Используем ключ, если нет метки в данных
        }

        // Если label равен ключу и это служебное поле, не показываем его
        if (displayLabel === key && key.startsWith('_')) {
            return '';
        }
        const fieldValue = value !== null && value !== undefined ? value : '';

        // For boolean values
        if (typeof value === 'boolean') {
            return `
                <div class="editable-field">
                    <label class="editable-label" for="${fieldId}">${displayLabel}</label>
                    <select id="${fieldId}" class="editable-input" data-key="${key}">
                        <option value="true" ${value ? 'selected' : ''}>Yes</option>
                        <option value="false" ${!value ? 'selected' : ''}>No</option>
                    </select>
                </div>
            `;
        }

        // For string/number values
        // Если это JSON строка (начинается с { или [), всегда используем textarea
        const isJsonString = typeof fieldValue === 'string' && (fieldValue.trim().startsWith('{') || fieldValue.trim().startsWith('['));
        // Для поля name всегда используем textarea (чтобы было видно полностью)
        const isNameField = key === 'name';
        // Если в ключе есть слово "address" (например, "address", "bank_address", "edit_address_xxx"), используем textarea
        const isAddressField = key.toLowerCase().includes('address');
        if (isJsonString || isNameField || isAddressField || (typeof fieldValue === 'string' && fieldValue.length > 60)) {
            return `
                <div class="editable-field">
                    <label class="editable-label" for="${fieldId}">${displayLabel}</label>
                    <textarea id="${fieldId}" class="editable-textarea" data-key="${key}" ${isJsonString ? 'style="min-height: 120px; font-family: monospace; font-size: 0.9rem;"' : ''}>${escapeHtml(fieldValue)}</textarea>
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
        // Используем _label из данных, если есть, иначе только иконку
        const docInfoTitle = data.document_info._label || data._label || '';
        html += `<div class="editable-group-title"><i class="fas fa-file-alt"></i> ${docInfoTitle}</div>`;

        // Определяем порядок полей: тип документа, номер документа, дата, место, остальное
        const docInfoFieldOrder = ['document_type', 'document_number', 'document_date', 'date', 'document_date_normalized', 'location', 'place_of_compilation', 'compilation_place', 'currency'];
        const processedDocKeys = new Set();

        // Обрабатываем поля в заданном порядке
        for (const key of docInfoFieldOrder) {
            if (key in data.document_info && !key.endsWith('_label')) {
                const value = data.document_info[key];
                // Пропускаем пустые поля
                if (value === null || value === undefined || value === '') continue;
                processedDocKeys.add(key);
                if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    html += createField(key, JSON.stringify(value, null, 2), null, data.document_info);
                } else if (Array.isArray(value)) {
                    html += createField(key, JSON.stringify(value, null, 2), null, data.document_info);
                } else {
                    html += createField(key, value, null, data.document_info);
                }
            }
        }

        // Остальные поля document_info (только непустые)
        for (const [key, value] of Object.entries(data.document_info)) {
            if (key.endsWith('_label') || processedDocKeys.has(key)) continue;
            // Пропускаем пустые поля
            if (value === null || value === undefined || value === '') continue;
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                html += createField(key, JSON.stringify(value, null, 2), null, data.document_info);
            } else if (Array.isArray(value)) {
                html += createField(key, JSON.stringify(value, null, 2), null, data.document_info);
            } else {
                html += createField(key, value, null, data.document_info);
            }
        }
        html += '</div>';
    }

    // Process parties - обрабатываем все роли динамически
    if (data.parties) {
        // Маппинг ролей на иконки (без фиксированных текстов)
        const roleIconMapping = {
            'supplier': 'fa-building',
            'buyer': 'fa-user',
            'customer': 'fa-user',
            'supplier_representative': 'fa-user-tie',
            'recipient': 'fa-hand-holding',
            'performer': 'fa-user-cog'
        };

        // Обрабатываем все роли в parties
        for (const [roleKey, roleData] of Object.entries(data.parties)) {
            if (typeof roleData === 'object' && roleData !== null && !Array.isArray(roleData)) {
                const icon = roleIconMapping[roleKey] || 'fa-user';
                // Используем _label из данных, если есть, иначе используем ключ роли
                const roleTitle = roleData._label ? roleData._label.replace(':', '').trim() : roleKey;

                html += '<div class="editable-group">';
                html += `<div class="editable-group-title"><i class="fas ${icon}"></i> ${escapeHtml(roleTitle)}</div>`;

                // Определяем порядок полей:
                // 1. Название компании (name)
                // 2. Данные компании (edrpou, ipn, tax_id, vat_id, address, phone и другие)
                // 3. Название банка (bank)
                // 4. Данные банка (bank_edrpou, bank_ipn, bank_address, bank_phone и другие)
                // 5. Номер рахунку (account_number)

                const companyDataFields = ['edrpou', 'ipn', 'tax_id', 'vat_id', 'address', 'phone', 'email', 'website', 'contact_person'];
                const bankDataFields = ['bank_edrpou', 'bank_ipn', 'bank_address', 'bank_phone', 'bank_email', 'bank_contact'];

                const processedKeys = new Set();

                // 1. Название компании (только если не пустое)
                if ('name' in roleData && roleData.name !== '_label') {
                    const nameValue = roleData.name;
                    if (nameValue !== null && nameValue !== undefined && nameValue !== '') {
                        processedKeys.add('name');
                        html += createField('name', nameValue, null, roleData);
                    }
                }

                // 2. Данные компании (все поля кроме name, bank, account_number, phone и банковских)
                // Сначала обрабатываем поля в определенном порядке: edrpou, ipn, tax_id, vat_id, address
                const companyFieldOrder = ['edrpou', 'ipn', 'tax_id', 'vat_id', 'address'];
                for (const key of companyFieldOrder) {
                    if (key in roleData && key !== '_label' && !processedKeys.has(key)) {
                        processedKeys.add(key);
                        const value = roleData[key];
                        // Пропускаем пустые поля
                        if (value === null || value === undefined || value === '') continue;
                        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                            html += createField(key, JSON.stringify(value, null, 2), null, roleData);
                        } else if (Array.isArray(value)) {
                            html += createField(key, JSON.stringify(value, null, 2), null, roleData);
                        } else {
                            html += createField(key, value, null, roleData);
                        }
                    }
                }

                // Телефон всегда после адреса
                if ('phone' in roleData && !processedKeys.has('phone')) {
                    const phoneValue = roleData.phone;
                    // Пропускаем пустые поля
                    if (phoneValue !== null && phoneValue !== undefined && phoneValue !== '') {
                        processedKeys.add('phone');
                        html += createField('phone', phoneValue, null, roleData);
                    }
                }

                // Остальные поля компании (кроме name, bank, account_number, phone и банковских)
                for (const [key, value] of Object.entries(roleData)) {
                    if (key === '_label' || processedKeys.has(key)) continue;
                    if (key === 'name' || key === 'bank' || key === 'account_number' || key === 'phone') continue;
                    if (key.startsWith('bank_')) continue; // Банковские поля обработаем позже
                    // Пропускаем пустые поля
                    if (value === null || value === undefined || value === '') continue;

                    processedKeys.add(key);
                    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                        html += createField(key, JSON.stringify(value, null, 2), null, roleData);
                    } else if (Array.isArray(value)) {
                        html += createField(key, JSON.stringify(value, null, 2), null, roleData);
                    } else {
                        html += createField(key, value, null, roleData);
                    }
                }

                // 3. Название банка (только если не пустое)
                if ('bank' in roleData) {
                    const bankValue = roleData.bank;
                    if (bankValue !== null && bankValue !== undefined && bankValue !== '') {
                        processedKeys.add('bank');
                        html += createField('bank', bankValue, null, roleData);
                    }
                }

                // 4. Данные банка (поля начинающиеся с bank_, только непустые)
                for (const [key, value] of Object.entries(roleData)) {
                    if (key.startsWith('bank_') && !processedKeys.has(key)) {
                        // Пропускаем пустые поля
                        if (value === null || value === undefined || value === '') continue;
                        processedKeys.add(key);
                        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                            html += createField(key, JSON.stringify(value, null, 2), null, roleData);
                        } else if (Array.isArray(value)) {
                            html += createField(key, JSON.stringify(value, null, 2), null, roleData);
                        } else {
                            html += createField(key, value, null, roleData);
                        }
                    }
                }

                // 5. Номер рахунку (только если не пустое)
                if ('account_number' in roleData) {
                    const accountValue = roleData.account_number;
                    if (accountValue !== null && accountValue !== undefined && accountValue !== '') {
                        processedKeys.add('account_number');
                        html += createField('account_number', accountValue, null, roleData);
                    }
                }

                // Остальные поля (если есть какие-то необработанные, только непустые)
                for (const [key, value] of Object.entries(roleData)) {
                    if (key === '_label' || processedKeys.has(key)) continue;
                    // Пропускаем пустые поля
                    if (value === null || value === undefined || value === '') continue;
                    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                        html += createField(key, JSON.stringify(value, null, 2), null, roleData);
                    } else if (Array.isArray(value)) {
                        html += createField(key, JSON.stringify(value, null, 2), null, roleData);
                    } else {
                        html += createField(key, value, null, roleData);
                    }
                }
                html += '</div>';
            }
        }
    }

    // Process totals - вставляем в grid, чтобы могло быть рядом с buyer
    if (data.totals) {
        html += '<div class="editable-group">';
        // Используем _label из данных, если есть, иначе только иконку
        const totalsTitle = data.totals._label || data._label || '';
        html += `<div class="editable-group-title"><i class="fas fa-calculator"></i> ${escapeHtml(totalsTitle)}</div>`;
        for (const [key, value] of Object.entries(data.totals)) {
            let numericValue = null;
            let displayLabel = null;

            // Если значение - объект с полями label и value, показываем только value с label из объекта
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                if ('value' in value && 'label' in value) {
                    // Используем label из объекта, если есть, иначе украинское название
                    displayLabel = value.label || value._label || key;
                    numericValue = value.value;
                } else if ('value' in value) {
                    // Только value, используем _label или украинское название
                    displayLabel = value._label || key;
                    numericValue = value.value;
                } else {
                    // Обычный объект - показываем как JSON
                    html += createField(key, JSON.stringify(value, null, 2), null, data.totals);
                    continue;
                }
            } else if (Array.isArray(value)) {
                html += createField(key, JSON.stringify(value, null, 2), null, data.totals);
                continue;
            } else {
                // Простое значение - показываем с украинским названием
                displayLabel = null;
                numericValue = value;
            }

            // Показываем числовое поле
            if (numericValue !== null) {
                html += createField(key, numericValue, displayLabel, data.totals);

                // Под числовым полем добавляем поле прописью
                let amountInWords = null;

                // Ищем соответствующее значение прописью в amounts_in_words
                if (data.amounts_in_words) {
                    // Универсальный поиск по ключам (без хардкода)
                    const keyLower = key.toLowerCase();

                    // Пробуем найти по точному совпадению ключа
                    if (data.amounts_in_words[key]) {
                        const amountObj = data.amounts_in_words[key];
                        if (typeof amountObj === 'object' && amountObj !== null && 'value' in amountObj) {
                            amountInWords = amountObj.value;
                        } else if (typeof amountObj === 'string') {
                            amountInWords = amountObj;
                        }
                    }

                    // Если не нашли, ищем по частичному совпадению ключей
                    if (!amountInWords) {
                        // Перебираем все ключи в amounts_in_words
                        for (const [amountKey, amountValue] of Object.entries(data.amounts_in_words)) {
                            if (typeof amountValue === 'object' && amountValue !== null && amountValue !== undefined) {
                                // Универсальное сопоставление по ключам (без хардкода языков)
                                const labelKey = amountKey.toLowerCase();
                                const currentKey = key.toLowerCase();

                                // Проверяем совпадение ключей (total, vat, subtotal и их варианты)
                                const keyMatches = (
                                    (currentKey.includes('total') && labelKey.includes('total')) ||
                                    (currentKey.includes('vat') && labelKey.includes('vat')) ||
                                    (currentKey.includes('tax') && labelKey.includes('tax')) ||
                                    (currentKey.includes('subtotal') && labelKey.includes('subtotal'))
                                );

                                if (keyMatches && 'value' in amountValue) {
                                    amountInWords = amountValue.value;
                                    break;
                                }
                            } else if (typeof amountValue === 'string' && amountValue) {
                                // Если значение - строка, проверяем ключ
                                const labelKey = amountKey.toLowerCase();
                                const currentKey = key.toLowerCase();

                                // Универсальное сопоставление по ключам
                                const keyMatches = (
                                    (currentKey.includes('total') && labelKey.includes('total')) ||
                                    (currentKey.includes('vat') && labelKey.includes('vat')) ||
                                    (currentKey.includes('tax') && labelKey.includes('tax')) ||
                                    (currentKey.includes('subtotal') && labelKey.includes('subtotal'))
                                );

                                if (keyMatches) {
                                    amountInWords = amountValue;
                                    break;
                                }
                            }
                        }
                    }
                }

                // Всегда показываем поле для ввода прописью, даже если значение не найдено
                // Используем тот же ключ для сохранения, но с суффиксом _in_words
                html += createField(`${key}_in_words`, amountInWords || '', '', data.totals);
            }
        }
        html += '</div>';
    }

    // amounts_in_words теперь отображаются внутри totals, блок удален


    // Process other_fields - в grid
    if (data.other_fields) {
        html += '<div class="editable-group">';
        // Используем _label из данных, если есть, иначе только иконку
        const otherFieldsTitle = (typeof data.other_fields === 'object' && data.other_fields._label) ? data.other_fields._label : (data._label || '');
        html += `<div class="editable-group-title"><i class="fas fa-info-circle"></i> ${escapeHtml(otherFieldsTitle)}</div>`;
        // other_fields может быть массивом или объектом
        if (Array.isArray(data.other_fields)) {
            data.other_fields.forEach((field, index) => {
                if (typeof field === 'object' && field !== null) {
                    // Объединяем label, value, key в одно поле
                    let displayValue = '';
                    let displayLabel = '';

                    // Поддержка структуры {label, value, key}
                    if ('label' in field && 'value' in field) {
                        displayLabel = field.label || field.label_raw || `Field ${index + 1}`;
                        const value = field.value !== null && field.value !== undefined ? field.value : (field.value_raw || '');
                        // Объединяем все в одно значение
                        displayValue = value;
                        // Не показываем key отдельно
                    }
                    // Поддержка структуры {label_raw, value_raw, type}
                    else if ('label_raw' in field || 'value_raw' in field) {
                        displayLabel = field.label_raw || field.type || `Field ${index + 1}`;
                        displayValue = field.value_raw !== null && field.value_raw !== undefined ? field.value_raw : '';
                        // Не показываем type отдельно
                    }
                    // Если другая структура, обрабатываем все поля
                    else {
                        // Собираем все значения в одно
                        const parts = [];
                        for (const [key, value] of Object.entries(field)) {
                            if (key !== '_label' && value !== null && value !== undefined) {
                                parts.push(`${key}: ${value}`);
                            }
                        }
                        displayValue = parts.join('; ');
                        displayLabel = `Field ${index + 1}`;
                    }

                    if (displayLabel) {
                        html += createField(`other_field_${index}_combined`, displayValue, displayLabel, field);
                    }
                }
            });
        } else if (typeof data.other_fields === 'object' && data.other_fields !== null) {
            for (const [key, value] of Object.entries(data.other_fields)) {
                if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    html += createField(key, JSON.stringify(value, null, 2), null, data.other_fields);
                } else if (Array.isArray(value)) {
                    html += createField(key, JSON.stringify(value, null, 2), null, data.other_fields);
                } else {
                    html += createField(key, value, null, data.other_fields);
                }
            }
        }
        html += '</div>';
    }

    // Process additional top-level fields (for simpler invoice structures)
    // references не обрабатываем - секция удалена по запросу пользователя
    // _meta и test_results - техническая информация, не показываем пользователю
    const processedSections = ['document_info', 'parties', 'references', 'totals', 'amounts_in_words',
                                'other_fields', 'line_items', 'items', 'column_mapping', 'table_data',
                                '_meta', 'test_results'];  // Исключаем техническую информацию
    const remainingFields = Object.entries(data).filter(([key]) =>
        !processedSections.includes(key) &&
        !key.startsWith('_') &&  // Исключаем все служебные поля, начинающиеся с _
        key !== 'test_results'   // Исключаем результаты тестирования
    );

    if (remainingFields.length > 0) {
        html += '<div class="editable-group">';
        // Используем _label из данных, если есть, иначе только иконку
        const additionalTitle = data._label || '';
        html += `<div class="editable-group-title"><i class="fas fa-info-circle"></i> ${escapeHtml(additionalTitle)}</div>`;
        for (const [key, value] of remainingFields) {
            if (key.endsWith('_label')) continue;
            // Показываем все поля, включая объекты и массивы
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                html += createField(key, JSON.stringify(value, null, 2), null, data);
            } else if (Array.isArray(value)) {
                html += createField(key, JSON.stringify(value, null, 2), null, data);
            } else {
                html += createField(key, value, null, data);
            }
        }
        html += '</div>';
    }

    // Закрываем grid после всех секций
    html += '</div>';

    // Process line_items as table (поддержка разных структур)
    let items = data.line_items || data.items || [];
    let column_mapping = data.column_mapping || {};

    // Если товары в table_data
    if (data.table_data) {
        items = data.table_data.line_items || data.table_data.items || items;
        column_mapping = data.table_data.column_mapping || column_mapping;
    }

    if (items.length > 0) {
        html += '<div class="editable-group" style="grid-column: 1 / -1;">';
        // Используем _label из table_data или данных, если есть, иначе только иконку
        const tableTitle = (data.table_data && data.table_data._label) ? data.table_data._label :
                          (data._label || '');
        html += `<div class="editable-group-title"><i class="fas fa-list"></i> ${escapeHtml(tableTitle)}</div>`;
        html += '<div class="table-container">';
        html += '<table class="editable-items-table">';

        // Table header
        const firstItem = items[0];
        if (!firstItem) {
            console.warn('No items in line_items, skipping table rendering');
            // Не прерываем выполнение функции, просто не рендерим таблицу
            // HTML уже собран для других секций, он будет установлен в конце функции
        } else {

        // Функция для анализа содержимого колонки (без хардкода)
        const analyzeColumn = (key, items) => {
            const values = items.map(item => {
                const val = item[key];
                if (val === null || val === undefined) return '';
                if (typeof val === 'object') return JSON.stringify(val);
                return String(val).trim();
            }).filter(v => v.length > 0);

            if (values.length === 0) {
                return { isEmpty: true };
            }

            const lengths = values.map(v => v.length);
            const avgLength = lengths.reduce((a, b) => a + b, 0) / lengths.length;
            const maxLength = Math.max(...lengths);
            const minLength = Math.min(...lengths);

            // Проверяем, являются ли значения числовыми
            const numericCount = values.filter(v => {
                const cleaned = v.replace(/[\s,]/g, '');
                const num = parseFloat(cleaned);
                return !isNaN(num) && !/[a-zA-Zа-яА-ЯёЁіІїЇєЄґҐ]/.test(v);
            }).length;
            const numericRatio = numericCount / values.length;

            // Подсчитываем слова
            const wordCounts = values.map(v => {
                const words = v.split(/\s+/).filter(w => w.length > 0);
                return words.length;
            });
            const avgWords = wordCounts.reduce((a, b) => a + b, 0) / wordCounts.length;

            // Проверяем повторяемость значений
            const valueCounts = {};
            values.forEach(v => {
                valueCounts[v] = (valueCounts[v] || 0) + 1;
            });
            const maxRepetitions = Math.max(...Object.values(valueCounts));
            const repetitionRatio = maxRepetitions / values.length;

            const uniqueCount = Object.keys(valueCounts).length;
            const uniqueRatio = uniqueCount / values.length;

            return {
                isEmpty: false,
                totalValues: values.length,
                avgLength: Math.round(avgLength * 10) / 10,
                maxLength,
                minLength,
                numericRatio: Math.round(numericRatio * 100) / 100,
                avgWords: Math.round(avgWords * 10) / 10,
                repetitionRatio: Math.round(repetitionRatio * 100) / 100,
                uniqueRatio: Math.round(uniqueRatio * 100) / 100,
                uniqueCount
            };
        };

        // Функция для определения типа и стилей колонки на основе анализа (без хардкода)
        const determineColumnType = (analysis, label) => {
            if (analysis.isEmpty) {
                return {
                    type: 'empty',
                    minWidth: 80,
                    maxWidth: 120,
                    textAlign: 'left',
                    whiteSpace: 'nowrap',
                    useTextarea: false
                };
            }

            // Колонка номера строки - очень короткие значения (1-3 символа), обычно последовательные числа
            if (analysis.maxLength <= 3 && analysis.avgLength <= 2 && analysis.numericRatio > 0.9) {
                return {
                    type: 'line-number',
                    minWidth: 40,
                    maxWidth: 50,
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                    useTextarea: false
                };
            }

            // Числовые колонки - высокий процент числовых значений, средняя длина
            if (analysis.numericRatio > 0.8 && analysis.avgLength < 20) {
                return {
                    type: 'numeric',
                    minWidth: Math.max(100, Math.min(analysis.maxLength * 8, 150)),
                    maxWidth: Math.max(120, Math.min(analysis.maxLength * 10, 200)),
                    textAlign: 'right',
                    whiteSpace: 'nowrap',
                    useTextarea: false
                };
            }

            // Очень короткие повторяющиеся значения (единицы измерения, статусы)
            if (analysis.avgLength < 8 && analysis.repetitionRatio > 0.3 && analysis.avgWords <= 1.5) {
                return {
                    type: 'short-repetitive',
                    minWidth: Math.max(60, Math.min(analysis.maxLength * 10, 100)),
                    maxWidth: Math.max(80, Math.min(analysis.maxLength * 12, 120)),
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                    useTextarea: false
                };
            }

            // Длинные описательные колонки (товары, описания)
            if (analysis.avgLength > 35 || analysis.maxLength > 80 || analysis.avgWords > 3) {
                return {
                    type: 'long-descriptive',
                    minWidth: 200,
                    maxWidth: 400,
                    textAlign: 'left',
                    whiteSpace: 'normal',
                    useTextarea: true,
                    wordWrap: 'break-word'
                };
            }

            // Средние колонки (коды, артикулы, средние тексты)
            const calculatedMinWidth = Math.max(100, Math.min(analysis.avgLength * 8, 180));
            const calculatedMaxWidth = Math.max(120, Math.min(analysis.maxLength * 7, 250));

            return {
                type: 'medium',
                minWidth: calculatedMinWidth,
                maxWidth: calculatedMaxWidth,
                textAlign: 'left',
                whiteSpace: 'nowrap',
                useTextarea: false
            };
        };

        // Используем порядок колонок СТРОГО из column_mapping (порядок из оригинального документа)
        let allKeys;
        if (column_mapping && Object.keys(column_mapping).length > 0) {
            // Используем ТОЛЬКО колонки из column_mapping, в том порядке, в котором они там указаны
            allKeys = Object.keys(column_mapping);

            // Проверяем, есть ли в данных ключи, которых нет в column_mapping (для отладки)
            if (firstItem && typeof firstItem === 'object') {
                const itemKeys = Object.keys(firstItem).filter(key => !key.endsWith('_label') && key !== 'raw');
                const missingKeys = itemKeys.filter(k => !allKeys.includes(k));

                if (missingKeys.length > 0) {
                    console.warn('Keys in items but not in column_mapping (will be ignored):', missingKeys);
                }
            }
        } else {
            // Fallback: используем порядок из firstItem
            if (firstItem && typeof firstItem === 'object') {
                allKeys = Object.keys(firstItem).filter(key => !key.endsWith('_label') && key !== 'raw');
            } else {
                allKeys = [];
            }
        }

        // Убираем служебные поля, которые не должны отображаться (например, raw)
        allKeys = allKeys.filter(k => k !== 'raw');

        // Debug: log column mapping and keys for troubleshooting (temporary)
        console.log('table_data.column_mapping:', column_mapping);
        console.log('line_items sample keys:', firstItem ? Object.keys(firstItem) : []);

        // Анализируем все колонки и определяем их типы динамически
        const columnAnalyses = {};
        const columnTypes = {};
        for (const key of allKeys) {
            const analysis = analyzeColumn(key, items);
            columnAnalyses[key] = analysis;
            const label = (column_mapping && column_mapping[key]) || (firstItem ? getLabel(firstItem, key) : null) || key;
            columnTypes[key] = determineColumnType(analysis, label);
        }

        html += '<thead><tr>';
        for (const key of allKeys) {
            if (!key) continue; // Пропускаем пустые ключи
            const label = (column_mapping && column_mapping[key]) || (firstItem ? getLabel(firstItem, key) : null) || key;
            const safeLabel = label || key; // Защита от null/undefined
            const colType = columnTypes[key];

            // Определяем стили для заголовка на основе типа колонки
            // Заголовки переносим только если они не помещаются (определяется через CSS)
            const headerStyle = `min-width: ${colType.minWidth}px; max-width: ${colType.maxWidth}px; text-align: ${colType.textAlign}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;`;
            html += `<th class="col-${colType.type}" style="${headerStyle}">${escapeHtml(safeLabel)}</th>`;
        }
        html += '</tr></thead>';

        // Table body
        html += '<tbody>';
        items.forEach((item, index) => {
            if (!item || typeof item !== 'object') return; // Пропускаем некорректные элементы
            html += '<tr>';
            for (const key of allKeys) {
                if (!key) continue; // Пропускаем пустые ключи
                const value = item[key];
                const fieldId = `item_${index}_${key}`;
                const colType = columnTypes[key];

                // Показываем все значения, включая объекты и массивы
                let displayValue = '';
                if (value === null || value === undefined) {
                    displayValue = '';
                } else if (typeof value === 'object' || Array.isArray(value)) {
                    displayValue = JSON.stringify(value, null, 2);
                } else {
                    displayValue = String(value);
                }

                // Определяем стили для ячейки на основе типа колонки
                const cellStyle = `min-width: ${colType.minWidth}px; max-width: ${colType.maxWidth}px; text-align: ${colType.textAlign}; white-space: ${colType.whiteSpace};`;

                // Используем textarea для длинных описательных колонок или если значение длинное
                if (colType.useTextarea || (displayValue.length > 50 && colType.type === 'long-descriptive')) {
                    html += `<td class="col-${colType.type}" style="${cellStyle}"><textarea id="${fieldId}" class="item-input" data-index="${index}" data-key="${key}" title="${escapeHtml(displayValue)}">${escapeHtml(displayValue)}</textarea></td>`;
                } else {
                    html += `<td class="col-${colType.type}" style="${cellStyle}"><input type="text" id="${fieldId}" class="item-input" data-index="${index}" data-key="${key}" value="${escapeHtml(displayValue)}" title="${escapeHtml(displayValue)}"></td>`;
                }
            }
            html += '</tr>';
        });
        html += '</tbody>';
        html += '</table>';
        html += '</div>';
        html += '</div>';
        }
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


        // Обработка полей _in_words (формат: total_in_words, vat_in_words и т.д.)
        // Эти поля теперь отображаются внутри totals, под числовыми значениями
        if (key.endsWith('_in_words')) {
            const baseKey = key.replace('_in_words', ''); // Извлекаем базовый ключ (total, vat и т.д.)

            // Сохраняем в amounts_in_words с соответствующим ключом
            if (!editedData.amounts_in_words) {
                editedData.amounts_in_words = {};
            }

            // Определяем ключ для amounts_in_words
            let amountKey = baseKey;
            if (baseKey === 'total' || baseKey === 'total_with_vat' || baseKey === 'total_amount') {
                amountKey = 'total';
            } else if (baseKey === 'vat' || baseKey === 'vat_amount' || baseKey === 'tax_amount') {
                amountKey = 'vat';
            } else if (baseKey === 'subtotal' || baseKey === 'total_no_vat' || baseKey === 'total_without_vat') {
                amountKey = 'subtotal';
            }

            // Сохраняем структуру объекта
            if (!editedData.amounts_in_words[amountKey]) {
                editedData.amounts_in_words[amountKey] = {};
            }

            // Сохраняем оригинальные поля, если они есть
            if (state.parsedData && state.parsedData.data && state.parsedData.data.amounts_in_words &&
                state.parsedData.data.amounts_in_words[amountKey] &&
                typeof state.parsedData.data.amounts_in_words[amountKey] === 'object') {
                const original = state.parsedData.data.amounts_in_words[amountKey];
                if (original._label) editedData.amounts_in_words[amountKey]._label = original._label;
                if (original.label) editedData.amounts_in_words[amountKey].label = original.label;
            }

            // Сохраняем новое значение
            editedData.amounts_in_words[amountKey].value = value;
            return;
        }

        // Обработка полей amounts_in_words (формат: amounts_in_words_total или amounts_in_words_total_value)
        if (key.startsWith('amounts_in_words_')) {
            const parts = key.split('_');
            // Поддержка двух форматов: amounts_in_words_total и amounts_in_words_total_value
            if (parts.length >= 3) {
                let amountKey;
                let subKey = 'value'; // По умолчанию сохраняем в value

                if (parts[parts.length - 1] === 'value' && parts.length >= 4) {
                    // Формат: amounts_in_words_total_value
                    amountKey = parts.slice(2, -1).join('_'); // Извлекаем "total" из "amounts_in_words_total_value"
                    subKey = 'value';
                } else {
                    // Формат: amounts_in_words_total (без _value)
                    amountKey = parts.slice(2).join('_'); // Извлекаем "total" из "amounts_in_words_total"
                    subKey = 'value';
                }

                if (!editedData.amounts_in_words) {
                    editedData.amounts_in_words = {};
                }
                // Если оригинальная структура была объектом с value, сохраняем как объект
                if (state.parsedData && state.parsedData.data && state.parsedData.data.amounts_in_words &&
                    state.parsedData.data.amounts_in_words[amountKey] &&
                    typeof state.parsedData.data.amounts_in_words[amountKey] === 'object') {
                    // Сохраняем структуру объекта
                    if (!editedData.amounts_in_words[amountKey]) {
                        editedData.amounts_in_words[amountKey] = {};
                    }
                    // Сохраняем оригинальные поля, если они есть
                    const original = state.parsedData.data.amounts_in_words[amountKey];
                    if (original._label) editedData.amounts_in_words[amountKey]._label = original._label;
                    if (original.label) editedData.amounts_in_words[amountKey].label = original.label;
                    // Сохраняем новое значение
                    editedData.amounts_in_words[amountKey].value = value;
                } else {
                    // Простое значение или создаем объект с value
                    if (!editedData.amounts_in_words[amountKey]) {
                        editedData.amounts_in_words[amountKey] = {};
                    }
                    editedData.amounts_in_words[amountKey].value = value;
                }
                return;
            } else if (parts.length >= 4) {
                // Формат: amounts_in_words_total_other_field
                const amountKey = parts.slice(2, -1).join('_');
                const subKey = parts[parts.length - 1];

                if (!editedData.amounts_in_words) {
                    editedData.amounts_in_words = {};
                }
                if (!editedData.amounts_in_words[amountKey]) {
                    editedData.amounts_in_words[amountKey] = {};
                }

                // Парсим JSON если нужно
                if (value.trim() !== '' && (value.trim().startsWith('{') || value.trim().startsWith('['))) {
                    try {
                        value = JSON.parse(value);
                    } catch (e) {
                        // Оставляем как строку
                    }
                }

                editedData.amounts_in_words[amountKey][subKey] = value;
                return;
            }
        }

        // Обработка объединенных полей other_fields (формат: other_field_0_combined)
        if (key.startsWith('other_field_') && key.endsWith('_combined')) {
            const parts = key.split('_');
            const index = parseInt(parts[2]);

            if (!editedData.other_fields) {
                editedData.other_fields = [];
            }
            if (!editedData.other_fields[index]) {
                editedData.other_fields[index] = {};
            }

            // Сохраняем значение в value
            editedData.other_fields[index].value = value;
            // Пытаемся сохранить label и key из оригинальных данных, если они есть
            if (state.parsedData && state.parsedData.data && state.parsedData.data.other_fields && state.parsedData.data.other_fields[index]) {
                const original = state.parsedData.data.other_fields[index];
                if (original.label) editedData.other_fields[index].label = original.label;
                if (original.key) editedData.other_fields[index].key = original.key;
                if (original.label_raw) editedData.other_fields[index].label_raw = original.label_raw;
                if (original.value_raw) editedData.other_fields[index].value_raw = original.value_raw;
                if (original.type) editedData.other_fields[index].type = original.type;
            }
            return;
        }

        // Convert value types
        if (input.tagName === 'SELECT') {
            value = value === 'true';
        } else if (value.trim() !== '' && (value.trim().startsWith('{') || value.trim().startsWith('['))) {
            // Try to parse JSON strings
            try {
                value = JSON.parse(value);
            } catch (e) {
                // If parsing fails, keep as string
                value = value;
            }
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
        if (isNaN(index)) {
            console.warn('Invalid index in item input:', input.dataset.index);
            return;
        }
        const key = input.dataset.key;
        let value = input.value;

        // Try to parse JSON strings
        if (value.trim() !== '' && (value.trim().startsWith('{') || value.trim().startsWith('['))) {
            try {
                value = JSON.parse(value);
            } catch (e) {
                // If parsing fails, keep as string
                value = value;
            }
        } else {
            // Try to preserve number types
            if (editedData.line_items && editedData.line_items[index]) {
                const originalValue = editedData.line_items[index][key];
                if (typeof originalValue === 'number' && !isNaN(value) && value !== '') {
                    value = parseFloat(value);
                }
            } else if (editedData.items && editedData.items[index]) {
                const originalValue = editedData.items[index][key];
                if (typeof originalValue === 'number' && !isNaN(value) && value !== '') {
                    value = parseFloat(value);
                }
            }
        }

        // Update the value
        if (editedData.line_items && editedData.line_items[index]) {
            editedData.line_items[index][key] = value;
        } else if (editedData.items && editedData.items[index]) {
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
        showToast('No data to save', true);
        return;
    }

    if (!state.authToken) {
                window.location.href = '/login.html';
        return;
    }

    try {
        // Collect edited data
        const editedData = collectEditedData();
        state.editedData = editedData;

        // Show loading state
        if (elements.saveAndContinueBtn) {
            elements.saveAndContinueBtn.disabled = true;
            elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
        }

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
            throw new Error(errorData.message || 'Failed to save data');
        }

        const result = await response.json();

        // Show success message
        showToast(`✅ ${result.message || 'Data saved successfully!'}`);

        // Reset button
        if (elements.saveAndContinueBtn) {
            elements.saveAndContinueBtn.disabled = false;
            elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-save"></i> Save and Continue';
        }

        // Optional: reset to upload new document
        setTimeout(() => {
            if (confirm('Do you want to upload a new document?')) {
                resetApp();
            }
        }, 1500);

    } catch (error) {
        console.error('Save error:', error);
        showToast('❌ ' + error.message, true);

        // Reset button
        if (elements.saveAndContinueBtn) {
            elements.saveAndContinueBtn.disabled = false;
            elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-save"></i> Save and Continue';
        }
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
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

