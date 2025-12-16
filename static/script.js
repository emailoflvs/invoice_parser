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

// Элементы DOM
const elements = {
    uploadArea: document.getElementById('uploadArea'),
    fileInput: document.getElementById('fileInput'),
    fileInfo: document.getElementById('fileInfo'),
    fileName: document.getElementById('fileName'),
    fileSize: document.getElementById('fileSize'),
    removeFile: document.getElementById('removeFile'),
    parseButtons: document.getElementById('parseButtons'),
    parseFastBtn: document.getElementById('parseFastBtn'),
    parseDetailedBtn: document.getElementById('parseDetailedBtn'),

    uploadSection: document.getElementById('uploadSection'),
    progressSection: document.getElementById('progressSection'),
    resultsSection: document.getElementById('resultsSection'),
    errorSection: document.getElementById('errorSection'),

    progressFill: document.getElementById('progressFill'),
    progressPercentage: document.getElementById('progressPercentage'),

    editableData: document.getElementById('editableData'),

    errorMessage: document.getElementById('errorMessage'),

    newParseBtn: document.getElementById('newParseBtn'),
    retryBtn: document.getElementById('retryBtn'),
    backBtn: document.getElementById('backBtn'),
    saveAndContinueBtn: document.getElementById('saveAndContinueBtn'),

    logoutBtn: document.getElementById('logoutBtn'),
    authWarning: document.getElementById('authWarning')
};

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

// Инициализация
async function init() {
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
        setProgress(10, 'Загрузка документа...');

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
                // Токен истек, перенаправляем на страницу входа
                localStorage.removeItem('authToken');
                window.location.href = '/login.html';
                return;
            }
            throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        setProgress(50, 'Обработка данных...');
        const result = await response.json();

        if (result.success && result.data) {
            setProgress(90, 'Отображение формы...');

            // Устанавливаем данные для редактирования
            state.parsedData = {
                success: true,
                data: result.data,
                processed_at: new Date().toISOString()
            };

            // Устанавливаем original_filename из данных или используем дефолтное значение
            state.originalFilename = result.data.original_filename || `document_${documentId}`;

            // Показываем форму редактирования
            hideProgress();

            // Показываем секцию результатов
            showSection('results');

            // Отображаем данные
            displayEditableData(result.data);

            setProgress(100, 'Готово');
            setTimeout(() => hideProgress(), 500);
        } else {
            throw new Error('Документ не найден или данные недоступны');
        }
    } catch (error) {
        console.error('Error loading document:', error);
        hideProgress();
        showError(`Не удалось загрузить документ: ${error.message}`);
    }
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Upload area
    elements.uploadArea.addEventListener('click', () => {
        // Проверяем авторизацию перед открытием диалога выбора файла
        if (!state.authToken) {
            showAuthRequiredMessage();
            return;
        }
        elements.fileInput.click();
    });
    elements.uploadArea.addEventListener('dragover', handleDragOver);
    elements.uploadArea.addEventListener('dragleave', handleDragLeave);
    elements.uploadArea.addEventListener('drop', handleDrop);

    // File input
    elements.fileInput.addEventListener('change', handleFileSelect);
    elements.removeFile.addEventListener('click', removeFile);

    // Parse buttons
    if (elements.parseFastBtn) {
        elements.parseFastBtn.addEventListener('click', () => parseDocument('fast'));
    }
    if (elements.parseDetailedBtn) {
        elements.parseDetailedBtn.addEventListener('click', () => parseDocument('detailed'));
    }

    // Action buttons
    elements.newParseBtn.addEventListener('click', resetApp);
    elements.retryBtn.addEventListener('click', resetApp);
    elements.backBtn.addEventListener('click', resetApp);
    elements.saveAndContinueBtn.addEventListener('click', saveAndContinue);

    // Logout
    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener('click', handleLogout);
    }
}


// File handling
function handleDragOver(e) {
    e.preventDefault();
    // Проверяем авторизацию перед drag over
    if (!state.authToken) {
        showAuthRequiredMessage();
        return;
    }
    elements.uploadArea.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    elements.uploadArea.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    elements.uploadArea.classList.remove('drag-over');

    // Проверяем авторизацию перед drop
    if (!state.authToken) {
        showAuthRequiredMessage();
        return;
    }

    const files = e.dataTransfer.files;
    if (files.length > 0) {
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
        showError('📄 Непідтримуваний формат файлу. Завантажте PDF, JPG, PNG, TIFF або BMP.');
        return;
    }

    // Проверка размера файла
    const maxSize = state.config.maxFileSizeMB * 1024 * 1024;
    if (file.size > maxSize) {
        const sizeMB = (file.size / 1024 / 1024).toFixed(1);
        showError(`📄 Файл занадто великий (${sizeMB}МБ). Максимальний розмір: ${state.config.maxFileSizeMB}МБ.`);
        return;
    }

    state.selectedFile = file;
    state.originalFilename = file.name;
    displayFileInfo(file);
}

// Показать сообщение о необходимости авторизации
function showAuthRequiredMessage() {
    showToast('Будь ласка, спочатку увійдіть в систему', true);
    // Автоматически открываем модальное окно авторизации
    setTimeout(() => {
                window.location.href = '/login.html';
    }, 500);
}

function displayFileInfo(file) {
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);
    elements.fileInfo.style.display = 'flex';
    elements.uploadArea.style.display = 'none';
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
    elements.fileInfo.style.display = 'none';
    elements.uploadArea.style.display = 'block';
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
        showError('📄 Будь ласка, виберіть файл');
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
                userMessage = '🔐 Невірна авторизація. Будь ласка, увійдіть знову.';
                // Перенаправляем на страницу входа
                setTimeout(() => {
                    window.location.href = '/login.html';
                }, 2000);
            } else if (errorInfo.error_code) {
                // Новый формат с кодами ошибок
                const code = errorInfo.error_code;
                const message = errorInfo.message || 'Невідома помилка';

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
                userMessage = `📄 ${errorInfo.message || 'Невірний формат файлу або занадто великий розмір'}`;
            } else if (response.status === 413) {
                userMessage = '📄 Файл занадто великий. Максимальний розмір: 50МБ.';
            } else {
                // Другие HTTP ошибки
                userMessage = errorInfo.message || `Не вдалося обробити запит. Спробуйте знову або зв'яжіться з підтримкою.`;
            }

            throw new Error(userMessage);
        }

        const data = await response.json();

        if (data.success) {
            state.parsedData = data;
            displayResults(data);
        } else {
            throw new Error(data.error || '❌ Не вдалося обробити документ. Спробуйте знову.');
        }

    } catch (error) {
        console.error('Parse error:', error);
        showError(error.message || '❌ Сталася помилка при обробці документа. Спробуйте знову або зв\'яжіться з підтримкою.');
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

// Кастомный диалог подтверждения в стиле проекта
function showConfirmDialog(message, title = 'Підтвердження') {
    return new Promise((resolve) => {
        // Создаем overlay
        const overlay = document.createElement('div');
        overlay.className = 'confirm-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            animation: fadeIn 0.2s ease-out;
        `;

        // Создаем диалог
        const dialog = document.createElement('div');
        dialog.className = 'confirm-dialog';
        dialog.style.cssText = `
            background: var(--card-background, #ffffff);
            border-radius: 12px;
            padding: 24px;
            max-width: 400px;
            width: 90%;
            box-shadow: var(--shadow-lg, 0 20px 25px -5px rgb(0 0 0 / 0.1));
            animation: slideUp 0.3s ease-out;
        `;

        // Заголовок
        const titleEl = document.createElement('div');
        titleEl.style.cssText = `
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary, #1e293b);
            margin-bottom: 12px;
        `;
        titleEl.textContent = title;

        // Сообщение
        const messageEl = document.createElement('div');
        messageEl.style.cssText = `
            color: var(--text-secondary, #64748b);
            margin-bottom: 24px;
            line-height: 1.5;
        `;
        messageEl.textContent = message;

        // Кнопки
        const buttonsEl = document.createElement('div');
        buttonsEl.style.cssText = `
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        `;

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Скасувати';
        cancelBtn.style.cssText = `
            padding: 10px 20px;
            border: 2px solid var(--border-color, #e2e8f0);
            border-radius: 8px;
            background: var(--card-background, #ffffff);
            color: var(--text-primary, #1e293b);
            cursor: pointer;
            font-size: 0.95rem;
            font-weight: 500;
            transition: all 0.2s;
        `;
        cancelBtn.onmouseover = () => {
            cancelBtn.style.background = 'var(--background, #f8fafc)';
        };
        cancelBtn.onmouseout = () => {
            cancelBtn.style.background = 'var(--card-background, #ffffff)';
        };
        cancelBtn.onclick = () => {
            document.body.removeChild(overlay);
            resolve(false);
        };

        const okBtn = document.createElement('button');
        okBtn.textContent = 'OK';
        okBtn.style.cssText = `
            padding: 10px 20px;
            border: 2px solid var(--secondary-color, #10b981);
            border-radius: 8px;
            background: var(--secondary-color, #10b981);
            color: white;
            cursor: pointer;
            font-size: 0.95rem;
            font-weight: 500;
            transition: all 0.2s;
        `;
        okBtn.onmouseover = () => {
            okBtn.style.background = '#059669';
            okBtn.style.borderColor = '#059669';
        };
        okBtn.onmouseout = () => {
            okBtn.style.background = 'var(--secondary-color, #10b981)';
            okBtn.style.borderColor = 'var(--secondary-color, #10b981)';
        };
        okBtn.onclick = () => {
            document.body.removeChild(overlay);
            resolve(true);
        };

        buttonsEl.appendChild(cancelBtn);
        buttonsEl.appendChild(okBtn);

        dialog.appendChild(titleEl);
        dialog.appendChild(messageEl);
        dialog.appendChild(buttonsEl);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        // Закрытие по клику на overlay
        overlay.onclick = (e) => {
            if (e.target === overlay) {
                document.body.removeChild(overlay);
                resolve(false);
            }
        };
    });
}

// Выход из системы
async function handleLogout() {
    const confirmed = await showConfirmDialog('Ви впевнені, що хочете вийти з системи?', 'Підтвердження виходу');
    if (confirmed) {
        // Удаляем токен
        state.authToken = '';
        localStorage.removeItem('authToken');
        localStorage.removeItem('rememberMe');

        // Перенаправляем на страницу входа
        window.location.href = '/login.html';
    }
}


// Field label mappings (Russian labels for fields)
const fieldLabels = {
    // Document Info
    'document_type': 'Тип документа',
    'document_number': 'Номер документа',
    'document_date': 'Дата документа',
    'document_date_normalized': 'Дата (нормалізована)',
    'location': 'Місце складання',
    'currency': 'Валюта',

    // Parties - Supplier
    'name': 'Назва',
    'account_number': 'Номер рахунку',
    'bank': 'Банк',
    'address': 'Адреса',
    'phone': 'Телефон',
    'tax_id': 'ЄДРПОУ',
    'vat_id': 'ІПН',
    'edrpou': 'ЄДРПОУ',
    'ipn': 'ІПН',

    // References
    'contract_number': 'Номер контракту',
    'basis_document': 'Підстава',

    // Totals
    'total': 'Всього',
    'vat': 'ПДВ',
    'vat_amount': 'ПДВ',
    'subtotal': 'Сума без ПДВ',
    'total_with_vat': 'Всього з ПДВ',
    'total_amount': 'Всього',

    // Amounts in words
    'total_in_words': 'Сума прописом',
    'vat_in_words': 'ПДВ прописом',

    // Line items
    'line_number': '№',
    'no': '№',
    'article': 'Артикул',
    'product_name': 'Товари (роботи, послуги)',
    'tovar': 'Товар',
    'description': 'Найменування',
    'application_mode': 'Режим полімерізації',
    'polymerization_mode_application_type': 'Режим полімерізації/ Тип нанесення',
    'ukt_zed': 'Код УКТЗЕД',
    'ukt_zed_code': 'Код УКТЗЕД',
    'quantity': 'Кількість',
    'kilkist': 'Кількість',
    'unit': 'Од. вим.',
    'price_excluding_vat': 'Ціна без ПДВ',
    'price_without_vat': 'Ціна без ПДВ',
    'tsina_bez_pdv': 'Ціна без ПДВ',
    'amount_excluding_vat': 'Сума без ПДВ',
    'amount_without_vat': 'Сума без ПДВ',
    'suma_bez_pdv': 'Сума без ПДВ',
    'unit_price': 'Ціна',
    'total_price': 'Сума',

    // Invoice fields (alternative)
    'invoice_number': 'Номер рахунку',
    'invoice_date': 'Дата рахунку',
    'supplier_name': 'Постачальник',
    'customer_name': 'Покупець',

    // Additional fields
    'label_raw': 'Мітка',
    'value_raw': 'Значення'
};

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

        // Fallback to predefined labels
        return fieldLabels[key] || key;
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
        // Приоритет: переданный label > getLabel (который ищет _label) > fieldLabels[key] > key
        let displayLabel = label;
        if (!displayLabel) {
            displayLabel = getLabel(parentObj, key);
        }
        if (!displayLabel || displayLabel === key) {
            displayLabel = fieldLabels[key] || key;
        }

        // Если label все еще равен ключу и нет fieldLabels, не показываем его
        if (displayLabel === key && !fieldLabels[key]) {
            return '';
        }
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
        // Если это JSON строка (начинается с { или [), всегда используем textarea
        const isJsonString = typeof fieldValue === 'string' && (fieldValue.trim().startsWith('{') || fieldValue.trim().startsWith('['));
        // Для поля name всегда используем textarea (чтобы было видно полностью)
        const isNameField = key === 'name';
        if (isJsonString || isNameField || (typeof fieldValue === 'string' && fieldValue.length > 60)) {
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
        html += '<div class="editable-group-title"><i class="fas fa-file-alt"></i> Інформація про документ</div>';

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
                    html += createField(key, JSON.stringify(value, null, 2), fieldLabels[key] || null, data.document_info);
                } else if (Array.isArray(value)) {
                    html += createField(key, JSON.stringify(value, null, 2), fieldLabels[key] || null, data.document_info);
                } else {
                    html += createField(key, value, fieldLabels[key] || null, data.document_info);
                }
            }
        }

        // Остальные поля document_info (только непустые)
        for (const [key, value] of Object.entries(data.document_info)) {
            if (key.endsWith('_label') || processedDocKeys.has(key)) continue;
            // Пропускаем пустые поля
            if (value === null || value === undefined || value === '') continue;
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                html += createField(key, JSON.stringify(value, null, 2), fieldLabels[key] || null, data.document_info);
            } else if (Array.isArray(value)) {
                html += createField(key, JSON.stringify(value, null, 2), fieldLabels[key] || null, data.document_info);
            } else {
                html += createField(key, value, fieldLabels[key] || null, data.document_info);
            }
        }
        html += '</div>';
    }

    // Process parties - обрабатываем все роли динамически
    if (data.parties) {
        // Маппинг ролей на иконки и названия (украинский)
        const roleMapping = {
            'supplier': { icon: 'fa-building', title: 'Постачальник' },
            'buyer': { icon: 'fa-user', title: 'Покупець' },
            'customer': { icon: 'fa-user', title: 'Покупець' },
            'supplier_representative': { icon: 'fa-user-tie', title: 'Представник постачальника' },
            'recipient': { icon: 'fa-hand-holding', title: 'Отримувач' },
            'performer': { icon: 'fa-user-cog', title: 'Виконавець' }
        };

        // Обрабатываем все роли в parties
        for (const [roleKey, roleData] of Object.entries(data.parties)) {
            if (typeof roleData === 'object' && roleData !== null && !Array.isArray(roleData)) {
                const roleInfo = roleMapping[roleKey] || { icon: 'fa-user', title: roleKey };
                // Используем _label из данных, если есть, иначе используем маппинг
                let roleTitle = roleData._label ? roleData._label.replace(':', '').trim() : roleInfo.title;
                // Переводим на украинский, если нужно
                if (roleTitle === 'Покупатель') roleTitle = 'Покупець';
                if (roleTitle === 'Представитель поставщика') roleTitle = 'Представник постачальника';
                if (roleTitle === 'Получатель') roleTitle = 'Отримувач';

                html += '<div class="editable-group">';
                html += `<div class="editable-group-title"><i class="fas ${roleInfo.icon}"></i> ${roleTitle}</div>`;

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
                        const ukrainianLabel = fieldLabels['name'] || null;
                        html += createField('name', nameValue, ukrainianLabel, roleData);
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
                        const ukrainianLabel = fieldLabels[key] || null;
                        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                            html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, roleData);
                        } else if (Array.isArray(value)) {
                            html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, roleData);
                        } else {
                            html += createField(key, value, ukrainianLabel, roleData);
                        }
                    }
                }

                // Телефон всегда после адреса
                if ('phone' in roleData && !processedKeys.has('phone')) {
                    const phoneValue = roleData.phone;
                    // Пропускаем пустые поля
                    if (phoneValue !== null && phoneValue !== undefined && phoneValue !== '') {
                        processedKeys.add('phone');
                        const ukrainianLabel = fieldLabels['phone'] || null;
                        html += createField('phone', phoneValue, ukrainianLabel, roleData);
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
                    const ukrainianLabel = fieldLabels[key] || null;
                    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                        html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, roleData);
                    } else if (Array.isArray(value)) {
                        html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, roleData);
                    } else {
                        html += createField(key, value, ukrainianLabel, roleData);
                    }
                }

                // 3. Название банка (только если не пустое)
                if ('bank' in roleData) {
                    const bankValue = roleData.bank;
                    if (bankValue !== null && bankValue !== undefined && bankValue !== '') {
                        processedKeys.add('bank');
                        const ukrainianLabel = fieldLabels['bank'] || null;
                        html += createField('bank', bankValue, ukrainianLabel, roleData);
                    }
                }

                // 4. Данные банка (поля начинающиеся с bank_, только непустые)
                for (const [key, value] of Object.entries(roleData)) {
                    if (key.startsWith('bank_') && !processedKeys.has(key)) {
                        // Пропускаем пустые поля
                        if (value === null || value === undefined || value === '') continue;
                        processedKeys.add(key);
                        const ukrainianLabel = fieldLabels[key] || fieldLabels[key.replace('bank_', '')] || null;
                        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                            html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, roleData);
                        } else if (Array.isArray(value)) {
                            html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, roleData);
                        } else {
                            html += createField(key, value, ukrainianLabel, roleData);
                        }
                    }
                }

                // 5. Номер рахунку (только если не пустое)
                if ('account_number' in roleData) {
                    const accountValue = roleData.account_number;
                    if (accountValue !== null && accountValue !== undefined && accountValue !== '') {
                        processedKeys.add('account_number');
                        const ukrainianLabel = fieldLabels['account_number'] || null;
                        html += createField('account_number', accountValue, ukrainianLabel, roleData);
                    }
                }

                // Остальные поля (если есть какие-то необработанные, только непустые)
                for (const [key, value] of Object.entries(roleData)) {
                    if (key === '_label' || processedKeys.has(key)) continue;
                    // Пропускаем пустые поля
                    if (value === null || value === undefined || value === '') continue;
                    const ukrainianLabel = fieldLabels[key] || null;
                    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                        html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, roleData);
                    } else if (Array.isArray(value)) {
                        html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, roleData);
                    } else {
                        html += createField(key, value, ukrainianLabel, roleData);
                    }
                }
                html += '</div>';
            }
        }
    }

    // Process totals - вставляем в grid, чтобы могло быть рядом с buyer
    if (data.totals) {
        html += '<div class="editable-group">';
        html += '<div class="editable-group-title"><i class="fas fa-calculator"></i> Підсумкові суми</div>';
        for (const [key, value] of Object.entries(data.totals)) {
            let numericValue = null;
            let displayLabel = null;

            // Если значение - объект с полями label и value, показываем только value с label из объекта
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                if ('value' in value && 'label' in value) {
                    // Используем label из объекта, если есть, иначе украинское название
                    displayLabel = value.label || value._label || fieldLabels[key] || key;
                    numericValue = value.value;
                } else if ('value' in value) {
                    // Только value, используем _label или украинское название
                    displayLabel = value._label || fieldLabels[key] || key;
                    numericValue = value.value;
                } else {
                    // Обычный объект - показываем как JSON
                    const ukrainianLabel = fieldLabels[key] || null;
                    html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, data.totals);
                    continue;
                }
            } else if (Array.isArray(value)) {
                const ukrainianLabel = fieldLabels[key] || null;
                html += createField(key, JSON.stringify(value, null, 2), ukrainianLabel, data.totals);
                continue;
            } else {
                // Простое значение - показываем с украинским названием
                displayLabel = fieldLabels[key] || null;
                numericValue = value;
            }

            // Показываем числовое поле
            if (numericValue !== null) {
                html += createField(key, numericValue, displayLabel, data.totals);

                // Под числовым полем добавляем поле прописью
                let amountInWords = null;

                // Ищем соответствующее значение прописью в amounts_in_words
                if (data.amounts_in_words) {
                    // Маппинг ключей totals на amounts_in_words - пробуем разные варианты
                    let possibleKeys = [];
                    if (key === 'total' || key === 'total_with_vat' || key === 'total_amount') {
                        possibleKeys = ['total', 'total_amount', 'total_with_vat', 'total_amount_in_words'];
                    } else if (key === 'vat' || key === 'vat_amount' || key === 'tax_amount') {
                        possibleKeys = ['vat', 'vat_amount', 'tax_amount', 'vat_amount_in_words'];
                    } else if (key === 'subtotal' || key === 'total_no_vat' || key === 'total_without_vat') {
                        possibleKeys = ['subtotal', 'total_no_vat', 'total_without_vat'];
                    }

                    // Ищем значение прописью по всем возможным ключам
                    for (const possibleKey of possibleKeys) {
                        if (data.amounts_in_words[possibleKey]) {
                            const amountObj = data.amounts_in_words[possibleKey];
                            if (typeof amountObj === 'object' && amountObj !== null && 'value' in amountObj) {
                                amountInWords = amountObj.value;
                                break;
                            } else if (typeof amountObj === 'string') {
                                amountInWords = amountObj;
                                break;
                            }
                        }
                    }

                    // Если не нашли по ключам, пробуем найти по структуре объекта с _label
                    // Или просто перебираем все ключи в amounts_in_words
                    if (!amountInWords) {
                        for (const [amountKey, amountValue] of Object.entries(data.amounts_in_words)) {
                            if (typeof amountValue === 'object' && amountValue !== null && amountValue !== undefined) {
                                // Проверяем _label на соответствие текущему полю
                                const label = (amountValue._label || amountValue.label || '').toLowerCase();
                                const labelKey = amountKey.toLowerCase();

                                // Для total
                                if ((key === 'total' || key === 'total_with_vat' || key === 'total_amount') &&
                                    (label.includes('всього') || label.includes('total') || labelKey.includes('total'))) {
                                    if ('value' in amountValue) {
                                        amountInWords = amountValue.value;
                                        break;
                                    }
                                }
                                // Для vat
                                else if ((key === 'vat' || key === 'vat_amount' || key === 'tax_amount') &&
                                         (label.includes('пдв') || label.includes('vat') || labelKey.includes('vat'))) {
                                    if ('value' in amountValue) {
                                        amountInWords = amountValue.value;
                                        break;
                                    }
                                }
                                // Для subtotal
                                else if ((key === 'subtotal' || key === 'total_no_vat' || key === 'total_without_vat') &&
                                         (label.includes('сума без') || label.includes('subtotal') || labelKey.includes('subtotal'))) {
                                    if ('value' in amountValue) {
                                        amountInWords = amountValue.value;
                                        break;
                                    }
                                }
                            } else if (typeof amountValue === 'string' && amountValue) {
                                // Если значение - строка, проверяем ключ
                                const labelKey = amountKey.toLowerCase();
                                if ((key === 'total' || key === 'total_with_vat' || key === 'total_amount') && labelKey.includes('total')) {
                                    amountInWords = amountValue;
                                    break;
                                } else if ((key === 'vat' || key === 'vat_amount' || key === 'tax_amount') && labelKey.includes('vat')) {
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
    // Переименовано в "Дополнительная информация" и объединяем label, value, key в одно поле
    if (data.other_fields) {
        html += '<div class="editable-group">';
        html += '<div class="editable-group-title"><i class="fas fa-info-circle"></i> Додаткова інформація</div>';
        // other_fields может быть массивом или объектом
        if (Array.isArray(data.other_fields)) {
            data.other_fields.forEach((field, index) => {
                if (typeof field === 'object' && field !== null) {
                    // Объединяем label, value, key в одно поле
                    let displayValue = '';
                    let displayLabel = '';

                    // Поддержка структуры {label, value, key}
                    if ('label' in field && 'value' in field) {
                        displayLabel = field.label || field.label_raw || `Поле ${index + 1}`;
                        const value = field.value !== null && field.value !== undefined ? field.value : (field.value_raw || '');
                        // Объединяем все в одно значение
                        displayValue = value;
                        // Не показываем key отдельно
                    }
                    // Поддержка структуры {label_raw, value_raw, type}
                    else if ('label_raw' in field || 'value_raw' in field) {
                        displayLabel = field.label_raw || field.type || `Поле ${index + 1}`;
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
                        displayLabel = `Поле ${index + 1}`;
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
        html += '<div class="editable-group-title"><i class="fas fa-info-circle"></i> Додаткова інформація</div>';
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
        html += '<div class="editable-group-title"><i class="fas fa-list"></i> Товари та послуги</div>';
        html += '<div class="table-container">';
        html += '<table class="editable-items-table">';

        // Определяем, какие колонки содержат цифры (узкие) и какая колонка - товар (широкая)
        const numericColumns = ['no', 'line_number', 'number', '№', 'кількість', 'quantity', 'kilkist', 'од. вим.', 'unit',
                                'ціна', 'price', 'tsina', 'сума', 'amount', 'suma', 'ukt_zed', 'ukt_zed_code', 'код', 'code',
                                'артикул', 'article', 'шк', 'barcode', 'sku', 'пдв', 'vat', 'vat_amount', 'од.вим'];
        const productColumns = ['product_name', 'description', 'tovar', 'товар', 'найменування', 'найменування товара',
                                'товари', 'товари (роботи, послуги)', 'goods', 'services', 'найменування товара'];

        // Table header
        const firstItem = items[0];
        const allKeys = Object.keys(firstItem).filter(key => !key.endsWith('_label') && key !== 'raw');

        // Функция для определения класса колонки
        const getColumnClass = (key, label) => {
            const keyLower = key.toLowerCase().trim();
            const labelLower = (label || '').toLowerCase().trim();

            // Проверяем, является ли колонка товаром
            if (productColumns.includes(keyLower) ||
                productColumns.some(pc => labelLower.includes(pc)) ||
                labelLower.includes('товар') || labelLower.includes('найменування')) {
                return 'col-product';
            }

            // Проверяем, является ли колонка числовой
            if (numericColumns.includes(keyLower) ||
                numericColumns.some(nc => labelLower.includes(nc)) ||
                labelLower.includes('№') || labelLower.includes('кількість') ||
                labelLower.includes('ціна') || labelLower.includes('сума') ||
                labelLower.includes('пдв') || labelLower.includes('кт') ||
                labelLower.includes('артикул') || labelLower.includes('код')) {
                return 'col-numeric';
            }

            return 'col-default';
        };

        html += '<thead><tr>';
        for (const key of allKeys) {
            const label = column_mapping?.[key] || getLabel(firstItem, key);
            const columnClass = getColumnClass(key, label);
            html += `<th class="${columnClass}">${label}</th>`;
        }
        html += '</tr></thead>';

        // Table body
        html += '<tbody>';
        items.forEach((item, index) => {
            html += '<tr>';
            for (const key of allKeys) {
                const value = item[key];
                const fieldId = `item_${index}_${key}`;
                const label = column_mapping?.[key] || getLabel(firstItem, key);
                const columnClass = getColumnClass(key, label);

                // Показываем все значения, включая объекты и массивы
                let displayValue = '';
                if (value === null || value === undefined) {
                    displayValue = '';
                } else if (typeof value === 'object' || Array.isArray(value)) {
                    displayValue = JSON.stringify(value, null, 2);
                } else {
                    displayValue = String(value);
                }

                // Для колонки товара используем textarea только если текст длинный (больше 50 символов)
                if (columnClass === 'col-product' && displayValue.length > 50) {
                    html += `<td class="${columnClass}"><textarea id="${fieldId}" class="item-input" data-index="${index}" data-key="${key}" title="${escapeHtml(displayValue)}">${escapeHtml(displayValue)}</textarea></td>`;
                } else {
                    html += `<td class="${columnClass}"><input type="text" id="${fieldId}" class="item-input" data-index="${index}" data-key="${key}" value="${escapeHtml(displayValue)}" title="${escapeHtml(displayValue)}"></td>`;
                }
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
        showToast('Немає даних для збереження', true);
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
        elements.saveAndContinueBtn.disabled = true;
        elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Збереження...';

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
            throw new Error(errorData.message || 'Не вдалося зберегти дані');
        }

        const result = await response.json();

        // Show success message
        showToast(`✅ ${result.message || 'Дані успішно збережено!'}`);

        // Reset button
        elements.saveAndContinueBtn.disabled = false;
        elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-save"></i> Зберегти та продовжити';

        // Optional: reset to upload new document
        setTimeout(async () => {
            const confirmed = await showConfirmDialog('Хочете завантажити новий документ?', 'doclogic.eu');
            if (confirmed) {
                resetApp();
            }
        }, 1500);

    } catch (error) {
        console.error('Save error:', error);
        showToast('❌ ' + error.message, true);

        // Reset button
        elements.saveAndContinueBtn.disabled = false;
        elements.saveAndContinueBtn.innerHTML = '<i class="fas fa-save"></i> Зберегти та продовжити';
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

