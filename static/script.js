// Состояние приложения
const state = {
    selectedFile: null,
    authToken: localStorage.getItem('authToken') || '',
    parsedData: null,
    originalFilename: null,
    editedData: null,
    interfaceRules: null,  // Правила интерфейса из interface-rules.json
    config: {
        maxFileSizeMB: 50,  // Default value, loaded from API
        columnTypeKeys: {
            lineNumber: [],
            product: [],
            price: [],
            quantity: [],
            code: []
        },
        columnAnalysis: {} // Loaded from server config - no hardcoded defaults
    },
    loginModalShown: false,  // Флаг, чтобы избежать повторного показа модального окна
    initialized: false  // Флаг, чтобы избежать повторной инициализации
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

// Load configuration from server
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const config = await response.json();
            state.config.maxFileSizeMB = config.max_file_size_mb || 50;
            // Load column type detection keys
            if (config.column_type_line_number_keys) {
                state.config.columnTypeKeys.lineNumber = config.column_type_line_number_keys;
            }
            if (config.column_type_product_keys) {
                state.config.columnTypeKeys.product = config.column_type_product_keys;
            }
            if (config.column_type_price_keys) {
                state.config.columnTypeKeys.price = config.column_type_price_keys;
            }
            if (config.column_type_quantity_keys) {
                state.config.columnTypeKeys.quantity = config.column_type_quantity_keys;
            }
            if (config.column_type_code_keys) {
                state.config.columnTypeKeys.code = config.column_type_code_keys;
            }
            // Load column analysis thresholds
            if (config.column_analysis_very_short_multiplier !== undefined) {
                state.config.columnAnalysis = {
                    veryShortMultiplier: config.column_analysis_very_short_multiplier,
                    numericRatioThreshold: config.column_analysis_numeric_ratio_threshold,
                    longTextAvgThreshold: config.column_analysis_long_text_avg_threshold,
                    longTextWordsThreshold: config.column_analysis_long_text_words_threshold,
                    shortRepetitiveRatio: config.column_analysis_short_repetitive_ratio,
                    shortRepetitiveAvgThreshold: config.column_analysis_short_repetitive_avg_threshold,
                    codeNumericMin: config.column_analysis_code_numeric_min,
                    codeNumericMax: config.column_analysis_code_numeric_max,
                    codeUniqueMin: config.column_analysis_code_unique_min,
                    codeWrapMultiplier: config.column_analysis_code_wrap_multiplier,
                    universalShortThreshold: config.column_analysis_universal_short_threshold,
                    universalVariationThreshold: config.column_analysis_universal_variation_threshold,
                    textareaWordMultiplier: config.column_analysis_textarea_word_multiplier,
                    codeMinLengthMultiplier: config.column_analysis_code_min_length_multiplier,
                    wordsDivisor: config.column_analysis_words_divisor
                };
            } else {
                // Fallback defaults if config not loaded (should not happen in production)
                state.config.columnAnalysis = {
                    veryShortMultiplier: 1.5,
                    numericRatioThreshold: 0.5,
                    longTextAvgThreshold: 0.5,
                    longTextWordsThreshold: 1.0,
                    shortRepetitiveRatio: 1.0,
                    shortRepetitiveAvgThreshold: 0.5,
                    codeNumericMin: 0.2,
                    codeNumericMax: 0.8,
                    codeUniqueMin: 0.3,
                    codeWrapMultiplier: 1.5,
                    universalShortThreshold: 0.3,
                    universalVariationThreshold: 0.5,
                    textareaWordMultiplier: 15.0,
                    codeMinLengthMultiplier: 2.0,
                    wordsDivisor: 2.0
                };
            }
            console.log('Config loaded:', state.config);
            console.log('Column analysis thresholds:', state.config.columnAnalysis);
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

    // Login modal elements
    elements.loginModal = document.getElementById('loginModal');
    elements.inlineLoginForm = document.getElementById('inlineLoginForm');
    elements.inlineUsername = document.getElementById('inlineUsername');
    elements.inlinePassword = document.getElementById('inlinePassword');
    elements.toggleInlinePassword = document.getElementById('toggleInlinePassword');
    elements.inlineLoginButton = document.getElementById('inlineLoginButton');
    elements.inlineLoginMessage = document.getElementById('inlineLoginMessage');
    elements.inlineLoginMessageIcon = document.getElementById('inlineLoginMessageIcon');
    elements.inlineLoginMessageText = document.getElementById('inlineLoginMessageText');
}

// Инициализация
async function init() {
    // Защита от повторного вызова
    if (state.initialized) {
        return;
    }
    state.initialized = true;

    // Инициализируем элементы DOM
    initElements();

    // Load config FIRST - before any other operations
    console.log('Loading configuration from server...');
    await loadConfig();
    console.log('Configuration loaded. Column analysis thresholds:', state.config.columnAnalysis);

    // Обновляем токен из localStorage (на случай, если он был сохранен на странице входа)
    state.authToken = localStorage.getItem('authToken') || '';

    // Проверяем авторизацию - если нет токена, показываем модальное окно
    // ВАЖНО: Не делаем редирект на /login.html, так как сервер сам решает, что показывать
    // Если пользователь не авторизован, сервер вернет login.html вместо index.html
    // Если мы видим index.html, значит пользователь авторизован или сервер разрешил доступ
    if (!state.authToken) {
        // Проверяем, есть ли модальное окно на странице (только на index.html)
        if (elements.loginModal) {
            // Если модальное окно есть, показываем его (для обратной совместимости)
            showLoginModal();
        }
        // Если модального окна нет, значит это не index.html - ничего не делаем,
        // сервер сам вернул нужную страницу
    }

    // Загружаем конфигурацию и правила интерфейса
    await Promise.all([loadConfig(), loadInterfaceRules()]);

    setupEventListeners();

    // Токен есть, разрешаем загрузку файлов
    enableFileUpload();

    // Проверяем, есть ли document_id в URL для загрузки документа
    const urlParams = new URLSearchParams(window.location.search);
    let documentId = urlParams.get('document_id');

    // If no document_id in URL, try to load from localStorage (auto-reload after page refresh)
    if (!documentId) {
        documentId = localStorage.getItem('lastDocumentId');
        if (documentId) {
            console.log(`Found saved document_id ${documentId} in localStorage, loading...`);
            // Update URL to include document_id for better UX
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('document_id', documentId);
            window.history.replaceState({}, '', newUrl);
        }
    }

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
            console.error('No auth token, showing login form...');
            showLoginModal();
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
                // Token expired, show login form
                localStorage.removeItem('authToken');
                state.authToken = '';
                showLoginModal();
                return;
            }
            throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        setProgress(50, 'Processing data...');
        const result = await response.json();

        if (result.success && result.data) {
            setProgress(90, 'Displaying form...'); // Final step before completion

            // Set data for editing
            state.parsedData = {
                success: true,
                data: result.data,
                processed_at: new Date().toISOString()
            };

            // Set original_filename from data or use default value
            state.originalFilename = result.data.original_filename || `document_${documentId}`;

            // Save document_id to localStorage for auto-reload on page refresh
            localStorage.setItem('lastDocumentId', String(documentId));
            console.log(`Saved document_id ${documentId} to localStorage for auto-reload`);

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

// Handle inline login (определяем перед setupEventListeners)
async function handleInlineLogin(e) {
    e.preventDefault();

    const username = elements.inlineUsername.value.trim();
    const password = elements.inlinePassword.value.trim();

    if (!username || !password) {
        showInlineLoginMessage('Please enter username and password', true);
        return;
    }

    // Disable button
    elements.inlineLoginButton.disabled = true;
    elements.inlineLoginButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging in...';
    clearInlineLoginMessage();

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }

        // Save token
        const token = data.access_token;
        state.authToken = token;
        localStorage.setItem('authToken', token);

        // Show success message
        showInlineLoginMessage('Login successful!', false);

        // Hide modal and reload page state
        setTimeout(() => {
            hideLoginModal();
            enableFileUpload();

            // Check if we need to load a document
            const urlParams = new URLSearchParams(window.location.search);
            const documentId = urlParams.get('document_id');
            if (documentId) {
                loadDocumentForEditing(parseInt(documentId));
            }
        }, 500);

    } catch (error) {
        showInlineLoginMessage(error.message || 'Login failed. Please check your credentials', true);
        elements.inlineLoginButton.disabled = false;
        elements.inlineLoginButton.innerHTML = '<i class="fas fa-sign-in-alt"></i> Log In';
    }
}

// Show inline login message
function showInlineLoginMessage(text, isError = false) {
    if (elements.inlineLoginMessage) {
        elements.inlineLoginMessage.style.display = 'flex';
        elements.inlineLoginMessageIcon.className = `fas ${isError ? 'fa-exclamation-circle' : 'fa-check-circle'}`;
        elements.inlineLoginMessageText.textContent = text;
        elements.inlineLoginMessage.className = `login-form-message ${isError ? 'error' : 'success'}`;
    }
}

// Clear inline login message
function clearInlineLoginMessage() {
    if (elements.inlineLoginMessage) {
        elements.inlineLoginMessage.style.display = 'none';
        elements.inlineLoginMessageText.textContent = '';
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

    // Inline login form
    if (elements.inlineLoginForm) {
        elements.inlineLoginForm.addEventListener('submit', handleInlineLogin);
    }
    if (elements.toggleInlinePassword) {
        elements.toggleInlinePassword.addEventListener('click', () => {
            const type = elements.inlinePassword.getAttribute('type') === 'password' ? 'text' : 'password';
            elements.inlinePassword.setAttribute('type', type);
            elements.toggleInlinePassword.querySelector('i').classList.toggle('fa-eye');
            elements.toggleInlinePassword.querySelector('i').classList.toggle('fa-eye-slash');
        });
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
    showLoginModal();
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
        showLoginModal();
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

            // Check authorization errors (401, 403)
            if (response.status === 401 || response.status === 403) {
                userMessage = '🔐 Authorization required. Please log in.';
                // Show login form
                localStorage.removeItem('authToken');
                state.authToken = '';
                showLoginModal();
                // Don't show error, as we already showed login form
                return;
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

            // Save document_id to localStorage if available (for auto-reload on page refresh)
            // Check in data.data._meta.document_id or data.data.document_id
            const documentId = data.data?._meta?.document_id || data.data?.document_id;
            if (documentId) {
                localStorage.setItem('lastDocumentId', String(documentId));
                console.log(`Saved document_id ${documentId} to localStorage for auto-reload`);
            }

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
        // Progress slowly grows with small random jumps
        const maxProgress = 90; // Keep under 90% until actually complete
        const increment = Math.random() * (maxProgress / 6);
        progress += increment;
        if (progress > maxProgress) {
            progress = maxProgress;
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
    // Проверяем, является ли ошибка ошибкой авторизации
    const authErrorPatterns = [
        /401/i,
        /403/i,
        /unauthorized/i,
        /authentication required/i,
        /authentication failed/i,
        /invalid.*token/i,
        /token.*expired/i,
        /token.*invalid/i,
        /авторизац/i,
        /не авторизован/i,
        /требуется.*авторизац/i
    ];

    const isAuthError = authErrorPatterns.some(pattern => pattern.test(message));

    if (isAuthError) {
        // Если это ошибка авторизации, показываем форму логина вместо ошибки
        console.log('Authorization error detected, showing login form');

        // Очищаем токен
        localStorage.removeItem('authToken');
        state.authToken = '';

        // Показываем модальное окно логина
        if (elements.loginModal) {
            showLoginModal();
        } else {
            // Если модального окна нет, перенаправляем на страницу логина
            window.location.href = '/login.html';
        }

        // Скрываем секцию ошибки
        if (elements.errorSection) {
            elements.errorSection.style.display = 'none';
        }

        return;
    }

    // Для обычных ошибок показываем их как обычно
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
    // Clear saved document_id when user explicitly resets
    localStorage.removeItem('lastDocumentId');
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

        // Показываем форму логина
        showLoginModal();
    }
}

// Show login modal
function showLoginModal() {
    if (elements.loginModal) {
        // Проверяем, не показано ли уже модальное окно, чтобы избежать мигания
        const isVisible = elements.loginModal.style.display === 'flex' ||
                         window.getComputedStyle(elements.loginModal).display === 'flex';
        if (isVisible || state.loginModalShown) {
            return; // Уже показано, не делаем ничего
        }

        state.loginModalShown = true;
        elements.loginModal.style.display = 'flex';
        // Focus on username field
        if (elements.inlineUsername) {
            setTimeout(() => elements.inlineUsername.focus(), 100);
        }
    }
}

// Hide login modal
function hideLoginModal() {
    if (elements.loginModal) {
        elements.loginModal.style.display = 'none';
        state.loginModalShown = false; // Сбрасываем флаг при скрытии
        // Clear form
        if (elements.inlineLoginForm) {
            elements.inlineLoginForm.reset();
        }
        clearInlineLoginMessage();
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

        // НЕ используем ключ как fallback - возвращаем null
        // Это позволит createField использовать более умный fallback или оставить пустым
        return null;
    };

    // Helper function to extract value from object with _label/value structure
    const extractValue = (val) => {
        if (val === null || val === undefined) return null;
        if (typeof val === 'object' && !Array.isArray(val) && val !== null) {
            // New structure: { "_label": ..., "value": ... }
            if ('value' in val) {
                return val.value;
            }
        }
        return val;
    };

    // Helper function to extract label from object with _label/value structure
    const extractLabel = (val, fallbackKey) => {
        if (val === null || val === undefined) return null;
        if (typeof val === 'object' && !Array.isArray(val) && val !== null) {
            // New structure: { "_label": ..., "value": ... }
            if ('_label' in val) {
                return val._label;
            }
        }
        return null;
    };

    // Helper function to create editable field
    const createField = (key, value, label, parentObj) => {
        // Skip _label fields themselves
        if (key.endsWith('_label')) return '';

        // Extract value from object structure if needed (recursively)
        let fieldValue = extractValue(value);

        // Рекурсивно извлекаем значение, если оно все еще объект
        while (typeof fieldValue === 'object' && fieldValue !== null && !Array.isArray(fieldValue)) {
            if ('value' in fieldValue) {
                fieldValue = fieldValue.value;
            } else {
                break; // Если нет 'value', это не наша структура
            }
        }

        let fieldLabel = label || extractLabel(value, key);

        // Skip empty values ONLY for handwritten/stamp fields
        // Fields that should be hidden if empty: handwritten_date, stamp_content
        const hiddenIfEmptyFields = ['handwritten_date', 'stamp_content'];
        const isHiddenField = hiddenIfEmptyFields.some(field => key.includes(field));

        if (isHiddenField && (fieldValue === null || fieldValue === undefined || fieldValue === '')) {
            return '';
        }

        // For all other fields, show them even if empty (but keep boolean false as it's a valid value)

        const fieldId = `edit_${key}_${Math.random().toString(36).substr(2, 9)}`;
        // Используем _label из данных, если есть
        // Приоритет: переданный label > extractLabel из value > getLabel (который ищет _label) > пустая строка
        // Полностью мультиязычное решение - используем только данные из документа
        let displayLabel = fieldLabel;
        if (!displayLabel) {
            displayLabel = getLabel(parentObj, key);
        }
        // Если все еще нет метки, проверяем тип поля
        if (!displayLabel) {
            // Для полей signatures (flat структура без _label/value) форматируем ключ
            if (key.startsWith('signature_')) {
                // Извлекаем последнюю часть ключа: signature_0_role -> role
                const parts = key.split('_');
                const fieldName = parts.slice(2).join('_'); // Убираем "signature_N_"
                // Форматируем: is_signed -> is signed, stamp_content -> stamp content
                displayLabel = fieldName.replace(/_/g, ' ');
            } else {
                // Для остальных полей: если нет оригинальной метки из документа, оставляем пустым
                displayLabel = null;
            }
        }

        // Если label равен ключу и это служебное поле, не показываем его
        if (displayLabel === key && key.startsWith('_')) {
            return '';
        }

        // For boolean values (проверяем ДО конвертации в строку)
        if (typeof fieldValue === 'boolean') {
            // Используем значения из данных, если они есть в структуре
            let trueLabel = 'true';
            let falseLabel = 'false';
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                if ('true_label' in value) trueLabel = value.true_label;
                if ('false_label' in value) falseLabel = value.false_label;
            }
            return `
                <div class="editable-field">
                    <label class="editable-label" for="${fieldId}">${escapeHtml(displayLabel || '')}</label>
                    <select id="${fieldId}" class="editable-input" data-key="${key}">
                        <option value="true" ${fieldValue ? 'selected' : ''}>${escapeHtml(trueLabel)}</option>
                        <option value="false" ${!fieldValue ? 'selected' : ''}>${escapeHtml(falseLabel)}</option>
                    </select>
                </div>
            `;
        }

        // Use extracted value (после рекурсивного извлечения и обработки boolean)
        // For arrays and objects, serialize to JSON
        if (Array.isArray(fieldValue)) {
            fieldValue = JSON.stringify(fieldValue, null, 2);
        } else if (typeof fieldValue === 'object' && fieldValue !== null) {
            // Если после рекурсивного извлечения все еще объект (не наша структура), сериализуем
            fieldValue = JSON.stringify(fieldValue, null, 2);
        } else {
            // Примитивные значения (string, number) - конвертируем в строку
            fieldValue = fieldValue !== null && fieldValue !== undefined ? String(fieldValue) : '';
        }

        // For string/number values
        // Если это JSON строка (начинается с { или [), всегда используем textarea
        const isJsonString = typeof fieldValue === 'string' && (fieldValue.trim().startsWith('{') || fieldValue.trim().startsWith('['));
        // Для поля name всегда используем textarea (чтобы было видно полностью)
        const isNameField = key === 'name';
        // Если в ключе есть слово "address" (например, "address", "bank_address", "edit_address_xxx"), используем textarea
        const isAddressField = key.toLowerCase().includes('address');
        // Determine if field needs multiline textarea based on content analysis
        const avgWordLength = typeof fieldValue === 'string' ? fieldValue.split(/\s+/).filter(w => w.length > 0).length : 0;
        const textareaMultiplier = state.config.columnAnalysis?.textareaWordMultiplier || 15.0;
        const needsTextarea = isJsonString || isNameField || isAddressField ||
                             (typeof fieldValue === 'string' && avgWordLength > 0 && fieldValue.length > avgWordLength * textareaMultiplier);

        if (needsTextarea) {
            return `
                <div class="editable-field">
                    <label class="editable-label" for="${fieldId}">${escapeHtml(displayLabel || '')}</label>
                    <textarea id="${fieldId}" class="editable-textarea" data-key="${key}" ${isJsonString ? 'style="font-family: monospace; font-size: 0.9rem;"' : ''}>${escapeHtml(fieldValue)}</textarea>
                </div>
            `;
        } else {
            return `
                <div class="editable-field">
                    <label class="editable-label" for="${fieldId}">${escapeHtml(displayLabel || '')}</label>
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
                // Пропускаем пустые поля (но проверяем value внутри объекта)
                const extractedValue = extractValue(value);
                if (extractedValue === null || extractedValue === undefined || extractedValue === '') continue;
                processedDocKeys.add(key);
                // Передаем объект как есть - createField сам извлечет value и _label
                html += createField(key, value, null, data.document_info);
            }
        }

        // Остальные поля document_info (только непустые)
        for (const [key, value] of Object.entries(data.document_info)) {
            if (key.endsWith('_label') || processedDocKeys.has(key)) continue;
            // Пропускаем пустые поля (но проверяем value внутри объекта)
            const extractedValue = extractValue(value);
            if (extractedValue === null || extractedValue === undefined || extractedValue === '') continue;
            // Передаем объект как есть - createField сам извлечет value и _label
            html += createField(key, value, null, data.document_info);
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
                // Use _label from data if available, otherwise use role key (displays original label from document)
                const roleTitle = (roleData._label && roleData._label !== 'null') ? roleData._label.replace(':', '').trim() : roleKey;

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
                    const extractedName = extractValue(nameValue);
                    if (extractedName !== null && extractedName !== undefined && extractedName !== '') {
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
                        // Пропускаем пустые поля (но проверяем value внутри объекта)
                        const extractedValue = extractValue(value);
                        if (extractedValue === null || extractedValue === undefined || extractedValue === '') continue;
                        // Передаем объект как есть - createField сам извлечет value и _label
                        html += createField(key, value, null, roleData);
                    }
                }

                // Телефон всегда после адреса
                if ('phone' in roleData && !processedKeys.has('phone')) {
                    const phoneValue = roleData.phone;
                    // Пропускаем пустые поля (но проверяем value внутри объекта)
                    const extractedPhone = extractValue(phoneValue);
                    if (extractedPhone !== null && extractedPhone !== undefined && extractedPhone !== '') {
                        processedKeys.add('phone');
                        html += createField('phone', phoneValue, null, roleData);
                    }
                }

                // Остальные поля компании (кроме name, bank, account_number, phone и банковских)
                for (const [key, value] of Object.entries(roleData)) {
                    if (key === '_label' || processedKeys.has(key)) continue;
                    if (key === 'name' || key === 'bank' || key === 'account_number' || key === 'phone') continue;
                    if (key.startsWith('bank_')) continue; // Банковские поля обработаем позже
                    // Пропускаем пустые поля (но проверяем value внутри объекта)
                    const extractedValue = extractValue(value);
                    if (extractedValue === null || extractedValue === undefined || extractedValue === '') continue;

                    processedKeys.add(key);
                    // Передаем объект как есть - createField сам извлечет value и _label
                    html += createField(key, value, null, roleData);
                }

                // 3. Название банка (только если не пустое)
                if ('bank' in roleData) {
                    const bankValue = roleData.bank;
                    const extractedBank = extractValue(bankValue);
                    if (extractedBank !== null && extractedBank !== undefined && extractedBank !== '') {
                        processedKeys.add('bank');
                        html += createField('bank', bankValue, null, roleData);
                    }
                }

                // 4. Данные банка (поля начинающиеся с bank_, только непустые)
                for (const [key, value] of Object.entries(roleData)) {
                    if (key.startsWith('bank_') && !processedKeys.has(key)) {
                        // Пропускаем пустые поля (но проверяем value внутри объекта)
                        const extractedValue = extractValue(value);
                        if (extractedValue === null || extractedValue === undefined || extractedValue === '') continue;
                        processedKeys.add(key);
                        // Передаем объект как есть - createField сам извлечет value и _label
                        html += createField(key, value, null, roleData);
                    }
                }

                // 5. Номер рахунку (только если не пустое)
                if ('account_number' in roleData) {
                    const accountValue = roleData.account_number;
                    const extractedAccount = extractValue(accountValue);
                    if (extractedAccount !== null && extractedAccount !== undefined && extractedAccount !== '') {
                        processedKeys.add('account_number');
                        html += createField('account_number', accountValue, null, roleData);
                    }
                }

                // Остальные поля (если есть какие-то необработанные, только непустые)
                for (const [key, value] of Object.entries(roleData)) {
                    if (key === '_label' || processedKeys.has(key)) continue;
                    // Пропускаем пустые поля (но проверяем value внутри объекта)
                    const extractedValue = extractValue(value);
                    if (extractedValue === null || extractedValue === undefined || extractedValue === '') continue;
                    // Передаем объект как есть - createField сам извлечет value и _label
                    html += createField(key, value, null, roleData);
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
                    // Используем label из объекта (оригинальная метка из документа)
                    displayLabel = value.label || value._label || null;
                    numericValue = value.value;
                } else if ('value' in value) {
                    // Только value, используем _label (оригинальная метка из документа)
                    displayLabel = value._label || null;
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
                // Простое значение - используем ключ как метку
                displayLabel = null;
                numericValue = value;
            }

            // Показываем числовое поле
            if (numericValue !== null) {
                html += createField(key, numericValue, displayLabel, data.totals);

                // Под числовым полем добавляем поле прописью (только если найдено и соответствует)
                let amountInWords = null;
                let amountInWordsValid = false;

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

                    // Проверяем соответствие числового значения и текстового представления
                    // Всегда проверяем соответствие, чтобы не показывать неверные данные
                    if (amountInWords && numericValue !== null) {
                        amountInWordsValid = validateAmountInWords(numericValue, amountInWords);
                        if (!amountInWordsValid) {
                            // Если не соответствует, не показываем текстовое представление
                            amountInWords = null;
                        }
                    }
                }

                // Показываем поле для ввода прописью только если значение найдено и соответствует числу
                if (amountInWords && amountInWordsValid) {
                    html += createField(`${key}_in_words`, amountInWords, '', data.totals);
                }
            }
        }
        html += '</div>';
    }

    // amounts_in_words теперь отображаются внутри totals, блок удален

    // Process references
    if (data.references) {
        html += '<div class="editable-group">';
        // Используем _label из данных, если есть, иначе только иконку
        const referencesTitle = (typeof data.references === 'object' && data.references._label) ? data.references._label : '';
        html += `<div class="editable-group-title"><i class="fas fa-link"></i> ${escapeHtml(referencesTitle)}</div>`;
        for (const [key, value] of Object.entries(data.references)) {
            if (key.endsWith('_label')) continue;
            // Передаем объект как есть - createField сам извлечет value и _label
            const extractedValue = extractValue(value);
            if (extractedValue !== null && extractedValue !== undefined && extractedValue !== '') {
                html += createField(key, value, null, data.references);
            }
        }
        html += '</div>';
    }

    // Process signatures
    // ЗАКОММЕНТИРОВАНО: раздел будет исправлен в другом релизе
    /*
    if (data.signatures && Array.isArray(data.signatures) && data.signatures.length > 0) {
        html += '<div class="editable-group">';
        // Используем _label из данных, если есть, иначе только иконку
        const signaturesTitle = (typeof data.signatures === 'object' && data.signatures._label) ? data.signatures._label : '';
        html += `<div class="editable-group-title"><i class="fas fa-signature"></i> ${escapeHtml(signaturesTitle)}</div>`;
        data.signatures.forEach((sig, index) => {
            if (typeof sig === 'object' && sig !== null) {
                // Обрабатываем каждое поле подписи отдельно
                for (const [key, value] of Object.entries(sig)) {
                    if (key === '_label') continue;

                    // Извлекаем значение (рекурсивно)
                    let extractedVal = extractValue(value);
                    while (typeof extractedVal === 'object' && extractedVal !== null && !Array.isArray(extractedVal)) {
                        if ('value' in extractedVal) {
                            extractedVal = extractedVal.value;
                        } else {
                            break;
                        }
                    }

                    // Скрываем пустые строковые поля (кроме boolean)
                    if (typeof extractedVal === 'string' && extractedVal.trim() === '') {
                        continue;
                    }

                    // Для технических полей (is_signed, is_stamped) показываем только если есть _label
                    // Это мультиязычное решение без хардкода
                    const technicalFields = ['is_signed', 'is_stamped'];
                    const isTechnicalField = technicalFields.includes(key);

                    if (isTechnicalField) {
                        // Показываем техническое поле только если есть _label (мультиязычная метка)
                        const fieldLabel = extractLabel(value, key);
                        if (!fieldLabel) {
                            // Если нет _label, не показываем техническое поле
                            continue;
                        }
                    }

                    const fieldKey = `signature_${index}_${key}`;
                    // Не используем key как fallback - только extractLabel или null
                    const fieldLabel = extractLabel(value, key) || null;
                    html += createField(fieldKey, value, fieldLabel, sig);
                }
            }
        });
        html += '</div>';
    }
    */

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

                    // Поддержка структуры {label, value, key} или {_label, value}
                    if (('label' in field && 'value' in field) || ('_label' in field && 'value' in field)) {
                        displayLabel = field._label || field.label || field.label_raw || null;
                        const value = field.value !== null && field.value !== undefined ? field.value : (field.value_raw || '');

                        // Проверяем, что метка и значение не одинаковые
                        if (displayLabel === value && value !== '') {
                            // Если одинаковые, возможно значение попало в метку
                            // Используем type как метку, если есть
                            displayLabel = field.type || null;
                        }

                        // Объединяем все в одно значение
                        displayValue = value;
                        // Не показываем key отдельно
                    }
                    // Поддержка структуры {label_raw, value_raw, type}
                    else if ('label_raw' in field || 'value_raw' in field) {
                        displayLabel = field.label_raw || field.type || null;
                        displayValue = field.value_raw !== null && field.value_raw !== undefined ? field.value_raw : '';
                        // Не показываем type отдельно
                    }
                    // Если другая структура, обрабатываем все поля
                    else {
                        // Собираем все значения в одно
                        const parts = [];
                        let foundLabel = null;
                        for (const [key, value] of Object.entries(field)) {
                            if (key === '_label') {
                                foundLabel = value;
                            } else if (key !== '_label' && value !== null && value !== undefined) {
                                // Если значение - объект с _label/value, извлекаем value
                                const extractedVal = extractValue(value);
                                if (extractedVal !== null && extractedVal !== undefined) {
                                    parts.push(`${key}: ${extractedVal}`);
                                }
                            }
                        }
                        displayValue = parts.join('; ');
                        displayLabel = foundLabel || null;
                    }

                    if (displayLabel) {
                        html += createField(`other_field_${index}_combined`, displayValue, displayLabel, field);
                    }
                }
            });
        } else if (typeof data.other_fields === 'object' && data.other_fields !== null) {
            for (const [key, value] of Object.entries(data.other_fields)) {
                if (key.endsWith('_label')) continue;
                // Передаем объект как есть - createField сам извлечет value и _label
                const extractedValue = extractValue(value);
                if (extractedValue !== null && extractedValue !== undefined && extractedValue !== '') {
                    html += createField(key, value, null, data.other_fields);
                }
            }
        }
        html += '</div>';
    }

    // Process additional top-level fields (for simpler invoice structures)
    // references не обрабатываем - секция удалена по запросу пользователя
    // _meta и test_results - техническая информация, не показываем пользователю
    const processedSections = ['document_info', 'parties', 'references', 'signatures', 'totals', 'amounts_in_words',
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
            // Если значение - массив, сериализуем в JSON для отображения
            if (Array.isArray(value)) {
                html += createField(key, JSON.stringify(value, null, 2), null, data);
            } else {
                // Передаем объект как есть - createField сам извлечет value и _label
                const extractedValue = extractValue(value);
                if (extractedValue !== null && extractedValue !== undefined && extractedValue !== '') {
                    html += createField(key, value, null, data);
                }
            }
        }
        html += '</div>';
    }

    // Закрываем grid после всех секций
    html += '</div>';

    // Process line_items as table (поддержка разных структур)
    let items = data.line_items || data.items || [];
    let column_mapping = data.column_mapping || {};

        // If items are in table_data
    if (data.table_data) {
        items = data.table_data.line_items || data.table_data.items || items;
        column_mapping = data.table_data.column_mapping || column_mapping;
    }

    if (items.length > 0) {
        html += '<div class="editable-group" style="grid-column: 1 / -1;">';
        // Use _label from table_data or data if available, otherwise only icon
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

        // Calculate column weight for proportional width distribution
        // Higher weight = wider column
        // Based on content analysis - NO HARDCODED VALUES
        const calculateColumnWeight = (analysis, colType) => {
            // Line numbers: minimal weight
            if (colType.type === 'line-number') {
                return 1;
            }

            // Short repetitive (quantity, units): minimal weight
            if (colType.type === 'short-repetitive') {
                return 2;
            }

            // Numeric (prices, amounts): proportional to max length
            if (colType.type === 'numeric') {
                // Weight based on max length of numbers
                return Math.max(2, Math.min(5, analysis.maxLength / 3));
            }

            // Codes (product codes, IDs): proportional to max length
            if (colType.type === 'code') {
                // Codes can be medium width
                return Math.max(3, Math.min(6, analysis.maxLength / 2.5));
            }

            // Text (descriptions, names): largest weight based on avg length
            if (colType.type === 'text') {
                // Text columns get the most space
                // Weight proportional to average text length
                const baseWeight = 10; // Minimum weight for text
                const lengthBonus = analysis.avgLength / 10; // Bonus based on content
                return Math.max(baseWeight, Math.min(30, baseWeight + lengthBonus));
            }

            // Default: medium weight
            return 5;
        };

        // UNIVERSAL column type determination - works with ANY columns, ANY data
        // No specific column types - just simple rules based on content analysis
        // All widths automatic - browser calculates based on content
        // Fully responsive - works on all devices (desktop, tablet, mobile)
        const determineColumnType = (analysis, label, key) => {
            if (analysis.isEmpty) {
                return {
                    type: 'empty',
                    width: 'auto',
                    textAlign: 'left',
                    whiteSpace: 'nowrap',
                    useTextarea: false
                };
            }

            // PURE CONTENT-BASED ANALYSIS - NO PREDEFINED KEYS
            // Works with ANY document structure, ANY language, ANY format
            // All thresholds MUST come from config - no hardcoded fallbacks
            const thresholds = state.config.columnAnalysis;
            if (!thresholds || Object.keys(thresholds).length === 0) {
                console.error('Column analysis thresholds not loaded from config!');
                // Return safe defaults (should not happen if config loaded properly)
                return {
                    type: 'universal',
                    width: 'auto',
                    textAlign: 'left',
                    whiteSpace: 'normal',
                    useTextarea: true
                };
            }

            // RULE 1: Line numbers
            // Very short, all numeric, highly unique (1, 2, 3, 4... or 1.0, 2.0, 3.0...)
            // Characteristics: 100% numeric, 100% unique, short values
            // Handle both integer (1, 2, 3) and decimal (1.0, 2.0, 3.0) formats
            const isLineNumber = analysis.numericRatio === 1.0 && // All values are numbers
                                analysis.uniqueRatio === 1.0 && // All values are unique (1, 2, 3...)
                                analysis.maxLength <= 5 && // Short (1-5 chars: "1" to "100.0")
                                analysis.avgLength <= 4; // Average also short

            if (isLineNumber) {
                return {
                    type: 'line-number',
                    width: 'max-content', // Always visible, never truncated
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                    useTextarea: false
                };
            }

            // RULE 2: Numeric fields (prices, amounts)
            // High numeric ratio but NOT line numbers
            const numericThreshold = 1 - thresholds.numericRatioThreshold; // e.g. 0.5 → threshold 0.5 (50%)
            const isMostlyNumeric = analysis.numericRatio >= numericThreshold && !isLineNumber;

            console.log(`  Rule 2 (Numeric): numericRatio=${analysis.numericRatio}, threshold=${numericThreshold}, isMostlyNumeric=${isMostlyNumeric}`);

            if (isMostlyNumeric) {
                return {
                    type: 'numeric',
                    width: 'max-content', // Always visible, never truncated
                    textAlign: 'right',
                    whiteSpace: 'nowrap',
                    useTextarea: false
                };
            }

            // RULE 3: Codes (mixed alphanumeric or pure numeric with sufficient length)
            // Medium to long length, high uniqueness
            const codeMinLength = 4; // Minimum 4 characters for codes
            const isCode = analysis.minLength >= codeMinLength &&
                          analysis.uniqueRatio > thresholds.codeUniqueMin &&
                          !isLineNumber;

            console.log(`  Rule 3 (Code): minLen=${analysis.minLength}>=${codeMinLength}, unique=${analysis.uniqueRatio}>${thresholds.codeUniqueMin}, isCode=${isCode}`);

            if (isCode) {
                const needsWrap = analysis.maxLength > analysis.avgLength * thresholds.codeWrapMultiplier;
                return {
                    type: 'code',
                    width: 'max-content', // Always visible, wraps if needed
                    textAlign: 'left',
                    whiteSpace: needsWrap ? 'normal' : 'nowrap',
                    useTextarea: needsWrap,
                    wordWrap: needsWrap ? 'break-word' : undefined
                };
            }

            // RULE 4: Short repetitive (units, statuses like "шт", "кг", etc.)
            const isShortRepetitive = analysis.repetitionRatio > analysis.uniqueRatio * thresholds.shortRepetitiveRatio &&
                                     analysis.avgLength < (analysis.minLength + analysis.maxLength) * thresholds.shortRepetitiveAvgThreshold;

            console.log(`  Rule 4 (Short repetitive): repetition=${analysis.repetitionRatio}>${analysis.uniqueRatio * thresholds.shortRepetitiveRatio}, avgLen=${analysis.avgLength}<${(analysis.minLength + analysis.maxLength) * thresholds.shortRepetitiveAvgThreshold}, isShortRep=${isShortRepetitive}`);

            if (isShortRepetitive) {
                return {
                    type: 'short-repetitive',
                    width: 'max-content', // Always visible, never truncated
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                    useTextarea: false
                };
            }

            // RULE 5: DEFAULT - Text columns (descriptions, notes, addresses, comments, etc.)
            // All remaining columns - any text content that didn't match above rules
            const relativeLength = analysis.avgLength / (analysis.maxLength || 1);
            const lengthVariation = (analysis.maxLength - analysis.minLength) / (analysis.maxLength || 1);

            // Determine alignment based on content characteristics
            let textAlign = 'left'; // Default for text
            if (relativeLength < thresholds.universalShortThreshold &&
                lengthVariation < thresholds.universalVariationThreshold) {
                textAlign = 'center'; // Short uniform values
            }

            // Determine if wrapping is needed
            const lengthMidpoint = (analysis.minLength + analysis.maxLength) * thresholds.longTextAvgThreshold;
            const wordsThreshold = analysis.totalValues / Math.max(analysis.uniqueCount, 1) * thresholds.longTextWordsThreshold;

            // Always use textarea for text columns with average length > 30 chars
            // This ensures better readability and prevents horizontal overflow
            const needsWrap = analysis.avgLength > 30 ||
                             analysis.avgLength > lengthMidpoint ||
                             analysis.avgWords > wordsThreshold;

            return {
                type: 'text', // Generic text type - browser distributes width
                width: 'auto', // Browser distributes space among all 'auto' columns
                textAlign: textAlign,
                whiteSpace: needsWrap ? 'normal' : 'nowrap',
                useTextarea: needsWrap, // Use textarea for better readability
                wordWrap: needsWrap ? 'break-word' : undefined
            };
        };

        // CRITICAL: Use column order STRICTLY from JSON (preserve exact order from document parsing)
        // Priority:
        // 1. data.table_data.column_order (explicit array preserving order)
        // 2. data.column_order (top-level fallback)
        // 3. Object.keys(column_mapping) (maintain insertion order, modern JS guarantee)
        // 4. Object.keys(firstItem) (last resort, may not reflect document order)

        let allKeys;
        let orderSource = 'unknown';

        // Priority 1: table_data.column_order (preferred)
        if (data.table_data && data.table_data.column_order && Array.isArray(data.table_data.column_order) && data.table_data.column_order.length > 0) {
            allKeys = [...data.table_data.column_order]; // Clone array to prevent mutations
            orderSource = 'table_data.column_order';
            console.log('✓ Using column order from table_data.column_order (explicit array):', allKeys);
        }
        // Priority 2: top-level column_order
        else if (data.column_order && Array.isArray(data.column_order) && data.column_order.length > 0) {
            allKeys = [...data.column_order]; // Clone array
            orderSource = 'data.column_order';
            console.log('✓ Using column order from data.column_order (explicit array):', allKeys);
        }
        // Priority 3: column_mapping keys (modern JS preserves insertion order)
        else if (column_mapping && Object.keys(column_mapping).length > 0) {
            allKeys = Object.keys(column_mapping);
            orderSource = 'Object.keys(column_mapping)';
            console.warn('⚠ column_order array not found, falling back to Object.keys(column_mapping):', allKeys);
            console.warn('⚠ Note: Object key order is preserved in modern JavaScript, but explicit column_order is preferred');

            // Validation: Check if there are keys in data that are not in column_mapping
            if (firstItem && typeof firstItem === 'object') {
                const itemKeys = Object.keys(firstItem).filter(key => !key.endsWith('_label') && key !== 'raw');
                const missingKeys = itemKeys.filter(k => !allKeys.includes(k));

                if (missingKeys.length > 0) {
                    console.error('❌ Keys in line_items but not in column_mapping (will be HIDDEN):', missingKeys);
                    console.error('❌ This may indicate a parsing issue or missing column mapping!');
                }
            }
        }
        // Priority 4: firstItem keys (last resort)
        else {
            if (firstItem && typeof firstItem === 'object') {
                allKeys = Object.keys(firstItem).filter(key => !key.endsWith('_label') && key !== 'raw');
                orderSource = 'Object.keys(firstItem)';
                console.error('❌ No column_order or column_mapping found, using Object.keys(firstItem):', allKeys);
                console.error('❌ This may not reflect the original document column order!');
            } else {
                allKeys = [];
                orderSource = 'empty (no data)';
                console.error('❌ No column data available - cannot render table');
            }
        }

        // Remove service fields that should not be displayed (e.g., raw)
        const serviceFields = ['raw', '_meta', '_label'];
        const beforeFilter = allKeys.length;
        const filteredOut = allKeys.filter(k => serviceFields.includes(k) || k.startsWith('_'));
        allKeys = allKeys.filter(k => !serviceFields.includes(k) && !k.startsWith('_'));
        const afterFilter = allKeys.length;

        if (beforeFilter !== afterFilter) {
            console.log(`🚫 Filtered out ${beforeFilter - afterFilter} service field(s):`, filteredOut);
        }

        // DEBUG: Check if "no" column exists
        if (allKeys.includes('no')) {
            console.log('✅ Column "no" found in allKeys');
        } else {
            console.warn('⚠️ Column "no" NOT found in allKeys!');
            console.warn('   Available keys:', allKeys);
            if (firstItem && typeof firstItem === 'object') {
                const itemKeys = Object.keys(firstItem);
                console.warn('   Keys in first item:', itemKeys);
                if (itemKeys.includes('no')) {
                    console.error('❌ "no" exists in item but was filtered out!');
                }
            }
        }

        // VALIDATION: Ensure all columns from line_items are mapped
        if (firstItem && typeof firstItem === 'object') {
            const itemKeys = Object.keys(firstItem).filter(key => !key.endsWith('_label') && !serviceFields.includes(key) && !key.startsWith('_'));
            const unmappedKeys = itemKeys.filter(k => !allKeys.includes(k));

            if (unmappedKeys.length > 0) {
                console.error('❌ CRITICAL: Unmapped columns found in line_items:', unmappedKeys);
                console.error('❌ These columns exist in data but will NOT be displayed!');
                console.error('❌ Please check column_mapping or column_order in the JSON');
            }
        }

        // Debug: Summary log for troubleshooting
        console.log('=== TABLE COLUMN ORDER SUMMARY ===');
        console.log(`Source: ${orderSource}`);
        console.log(`Total columns: ${allKeys.length}`);
        console.log(`Column order: [${allKeys.join(', ')}]`);
        console.log(`Column mapping:`, column_mapping);
        console.log(`First item keys:`, firstItem ? Object.keys(firstItem) : 'N/A');
        console.log('===================================');

        // Analyze all columns and determine their types dynamically
        console.log('Starting column analysis...');
        console.log('Available keys:', allKeys);
        console.log('Config state:', {
            columnTypeKeys: state.config.columnTypeKeys,
            columnAnalysis: state.config.columnAnalysis
        });
        const columnAnalyses = {};
        const columnTypes = {};
        const columnWeights = {};

        // Step 1: Analyze and determine types for all columns
        for (const key of allKeys) {
            const analysis = analyzeColumn(key, items);
            columnAnalyses[key] = analysis;
            const label = (column_mapping && column_mapping[key]) || (firstItem ? getLabel(firstItem, key) : null) || key;
            // Pass key (not label) for type detection - multilingual support
            const colType = determineColumnType(analysis, label, key);
            columnTypes[key] = colType;
            console.log(`Column "${key}" (label: "${label}"):`, {
                analysis: analysis,
                type: colType.type,
                width: colType.width,
                useTextarea: colType.useTextarea
            });
        }

        // Step 2: Calculate weights for proportional width distribution
        let totalWeight = 0;
        for (const key of allKeys) {
            const analysis = columnAnalyses[key];
            const colType = columnTypes[key];
            const weight = calculateColumnWeight(analysis, colType);
            columnWeights[key] = weight;
            totalWeight += weight;
            console.log(`Column "${key}" weight: ${weight.toFixed(2)}`);
        }

        console.log(`Total weight: ${totalWeight.toFixed(2)}`);

        // DEBUG: Show column types before rendering
        console.log('=== COLUMN TYPES FOR RENDERING ===');
        for (const key of allKeys) {
            if (!key) continue;
            const colType = columnTypes[key];
            console.log(`Key: "${key}" → Type: "${colType.type}" | Width: "${colType.width}" | Textarea: ${colType.useTextarea}`);
        }
        console.log('===================================');

        html += '<thead><tr>';
        for (const key of allKeys) {
            if (!key) continue; // Skip empty keys

            // Get column label from mapping, fallback to key
            const label = (column_mapping && column_mapping[key]) || (firstItem ? getLabel(firstItem, key) : null) || key;
            const safeLabel = label || key; // Protection from null/undefined
            const colType = columnTypes[key];
            const weight = columnWeights[key];
            const analysis = columnAnalyses[key];

            // Calculate min-width based on column type and content analysis
            // Use 'ch' units for dynamic sizing (1ch ≈ width of '0' character in current font)
            let minWidthCh = 0;

            if (colType.type === 'line-number') {
                // Line numbers: minimal width (№, N., etc.)
                minWidthCh = Math.max(3, analysis.maxLength + 1);
            } else if (colType.type === 'short-repetitive') {
                // Units, statuses (шт, кг, etc.): compact width
                minWidthCh = Math.max(5, analysis.maxLength + 2);
            } else if (colType.type === 'numeric') {
                // Prices, amounts: enough space for numbers + formatting
                // Consider header label length too
                const headerLength = safeLabel.length;
                minWidthCh = Math.max(8, Math.max(analysis.maxLength + 2, headerLength * 0.7));
            } else if (colType.type === 'code') {
                // Product codes, IDs: medium width
                const headerLength = safeLabel.length;
                minWidthCh = Math.max(10, Math.max(analysis.maxLength * 1.1, headerLength * 0.7));
            } else if (colType.type === 'text') {
                // Descriptions, names: balanced width
                // Limit max width to prevent one column from dominating
                const headerLength = safeLabel.length;
                minWidthCh = Math.max(25, Math.min(45, Math.max(analysis.avgLength * 0.6, headerLength * 0.8)));
            } else {
                // Default: reasonable width
                const headerLength = safeLabel.length;
                minWidthCh = Math.max(12, Math.max(analysis.maxLength * 0.9, headerLength * 0.7));
            }

            // Additional styles for specific column types
            const additionalStyles = [];
            if (colType.type === 'numeric') {
                // Numeric headers can wrap to 2 lines if needed (e.g., "Ціна без\nПДВ")
                additionalStyles.push('white-space: normal');
                additionalStyles.push('line-height: 1.3');
            }

            const style = `min-width: ${minWidthCh}ch; ${additionalStyles.join('; ')}`;

            // Add title attribute for long headers (helpful on hover)
            const titleAttr = safeLabel.length > 30 ? `title="${escapeHtml(safeLabel)}"` : '';

            html += `<th class="col-${colType.type}" style="${style}" ${titleAttr}>${escapeHtml(safeLabel)}</th>`;
        }
        html += '</tr></thead>';

        // Table body
        html += '<tbody>';
        items.forEach((item, index) => {
            if (!item || typeof item !== 'object') return; // Skip invalid items
            html += '<tr>';
            for (const key of allKeys) {
                if (!key) continue; // Skip empty keys
                const value = item[key];
                const fieldId = `item_${index}_${key}`;
                const colType = columnTypes[key];

                // Show all values, extracting from objects with _label/value structure
                let displayValue = '';

                // SPECIAL CASE: For "no" column, preserve original format from JSON (1.0 → "1.0", not "1")
                if (key === 'no') {
                    if (value === null || value === undefined) {
                        displayValue = '';
                    } else if (typeof value === 'object' && !Array.isArray(value) && value !== null && 'value' in value) {
                        // If it's an object with _label/value structure, extract value
                        const rawValue = value.value;
                        // For numbers, preserve .0 format using toFixed(1)
                        if (typeof rawValue === 'number') {
                            displayValue = rawValue.toFixed(1);
                        } else {
                            displayValue = String(rawValue);
                        }
                    } else if (typeof value === 'number') {
                        // For numbers, preserve .0 format (1.0 → "1.0", not "1")
                        displayValue = value.toFixed(1);
                    } else {
                        // For non-numbers, use as string
                        displayValue = String(value);
                    }
                    // DEBUG: Log for "no" column
                    console.log(`[DEBUG no] key="${key}", value=`, value, `→ displayValue="${displayValue}"`);
                } else if (value === null || value === undefined) {
                    displayValue = '';
                } else if (typeof value === 'object' && !Array.isArray(value) && value !== null) {
                    // Check if this is an object with _label/value structure
                    if ('value' in value) {
                        // Extract value from structure
                        const extractedVal = value.value;
                        // Format numbers properly to preserve precision
                        if (typeof extractedVal === 'number') {
                            // For integers, use as is. For floats, preserve decimals
                            if (Number.isInteger(extractedVal)) {
                                displayValue = String(extractedVal);
                            } else {
                                // Preserve up to 2 decimal places, but don't add unnecessary zeros
                                displayValue = extractedVal.toFixed(2).replace(/\.?0+$/, '');
                            }
                        } else {
                            displayValue = String(extractedVal !== null && extractedVal !== undefined ? extractedVal : '');
                        }
                    } else {
                        // This is another object - show as JSON
                        displayValue = JSON.stringify(value, null, 2);
                    }
                } else if (Array.isArray(value)) {
                    displayValue = JSON.stringify(value, null, 2);
                } else if (typeof value === 'number') {
                    // Format numbers properly to preserve precision
                    if (Number.isInteger(value)) {
                        // Integer values (including 1.0 which is technically an integer)
                        displayValue = String(value);
                    } else {
                        // Float values - preserve decimals but remove trailing zeros
                        displayValue = value.toFixed(2).replace(/\.?0+$/, '');
                    }
                } else {
                    displayValue = String(value);
                }

                // Determine if textarea is needed (automatic decision based on analysis)
                // Logic is determined by:
                // 1. Column type analysis (determineColumnType) → sets colType.useTextarea
                //    - Long text columns → useTextarea: true
                //    - Codes with wrapping → useTextarea: true
                //    - Universal columns with wrapping → useTextarea: true
                // 2. Column wrapping capability → whiteSpace === 'normal'
                //    - If column allows wrapping, it needs textarea to display properly
                // 3. Actual content → displayValue.includes('\n')
                //    - If data contains line breaks, must use textarea
                const shouldUseTextarea = colType.useTextarea || // From analysis
                    (colType.whiteSpace === 'normal') || // Column allows wrapping
                    (displayValue.includes('\n')); // Multi-line content in data

                if (shouldUseTextarea) {
                    // Textarea without specifying rows - auto-expands based on content
                    // Browser handles sizing automatically
                    html += `<td class="col-${colType.type}"><textarea id="${fieldId}" class="item-input" data-index="${index}" data-key="${key}" title="${escapeHtml(displayValue)}">${escapeHtml(displayValue)}</textarea></td>`;
                } else {
                    html += `<td class="col-${colType.type}"><input type="text" id="${fieldId}" class="item-input" data-index="${index}" data-key="${key}" value="${escapeHtml(displayValue)}" title="${escapeHtml(displayValue)}"></td>`;
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

        // Обработка полей signatures (формат: signature_0_role, signature_0_name и т.д.)
        if (key.startsWith('signature_')) {
            const parts = key.split('_');
            if (parts.length >= 3) {
                const index = parseInt(parts[1]);
                const fieldName = parts.slice(2).join('_'); // Может быть составным, например "handwritten_date"

                if (!isNaN(index) && editedData.signatures) {
                    if (!editedData.signatures[index]) {
                        editedData.signatures[index] = {};
                    }
                    // Сохраняем значение
                    editedData.signatures[index][fieldName] = value;
                }
            }
            return;
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

// Get original value from nested object (extracts value from {_label, value} structure if needed)
function getOriginalValue(obj, key) {
    for (const [k, v] of Object.entries(obj)) {
        if (k === key) {
            // If value is an object with _label/value structure, extract the value
            if (typeof v === 'object' && v !== null && !Array.isArray(v) && 'value' in v) {
                return v.value;
            }
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
            // If the original value was an object with _label/value structure, preserve it
            if (typeof v === 'object' && v !== null && !Array.isArray(v) && ('_label' in v || 'value' in v)) {
                // Preserve _label if it exists
                const label = v._label || null;
                obj[k] = { _label: label, value: value };
            } else {
                obj[k] = value;
            }
            return true;
        }
        // Recursively search in nested objects (document_info, parties, etc.)
        if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
            // Check if this is a party object (has _label at top level)
            if ('_label' in v && k in obj && typeof obj[k] === 'object') {
                // This is a party object, search in its fields
                for (const [fieldKey, fieldValue] of Object.entries(obj[k])) {
                    if (fieldKey === key) {
                        // Found the field in this party
                        if (typeof fieldValue === 'object' && fieldValue !== null && !Array.isArray(fieldValue) && ('_label' in fieldValue || 'value' in fieldValue)) {
                            const label = fieldValue._label || null;
                            obj[k][fieldKey] = { _label: label, value: value };
                        } else {
                            obj[k][fieldKey] = value;
                        }
                        return true;
                    }
                }
            }
            // Continue recursive search
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
        showLoginModal();
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

// Validate that amount in words corresponds to numeric value
// Проверяет соответствие числового значения и текстового представления
// Извлекает копейки из текста и сравнивает с числовым значением
function validateAmountInWords(numericValue, textValue) {
    if (!textValue || typeof textValue !== 'string') {
        return false;
    }

    try {
        // Преобразуем числовое значение в число
        const num = parseFloat(numericValue);
        if (isNaN(num)) {
            return false;
        }

        // Вычисляем копейки из числового значения
        const numericKopecks = Math.round((num - Math.floor(num)) * 100);
        const numericMain = Math.floor(num);

        // Извлекаем копейки из текста (ищем паттерны типа "97 копійок", "97 коп", "0.97" и т.д.)
        // Паттерны для украинского и русского языков
        const kopecksPatterns = [
            /(\d+)\s*(?:копійок|копійки|копійка|коп|копейки|копейка|копеек)/i,
            /(\d+)\s*(?:коп)/i,
            /\.(\d{2})\b/,  // Десятичная часть (например, .97)
            /,(\d{2})\b/    // Десятичная часть с запятой (например, ,97)
        ];

        let extractedKopecks = null;
        for (const pattern of kopecksPatterns) {
            const match = textValue.match(pattern);
            if (match) {
                extractedKopecks = parseInt(match[1], 10);
                break;
            }
        }

        // Если нашли копейки в тексте, сравниваем с числовым значением
        if (extractedKopecks !== null) {
            // Сравниваем копейки с допуском (может быть округление)
            const kopecksMatch = Math.abs(extractedKopecks - numericKopecks) <= 1;

            // Если копейки не совпадают, не показываем текстовое представление
            if (!kopecksMatch) {
                return false;
            }
        } else {
            // Если копейки не найдены в тексте, но числовое значение имеет дробную часть > 0.01,
            // значит текстовое представление неполное - не показываем
            if (numericKopecks > 1) {
                return false;
            }
        }

        // Дополнительная проверка: если числовое значение имеет значимую дробную часть,
        // но в тексте нет упоминания копеек - не показываем
        // (это означает, что текстовое представление относится к другому числу)
        if (numericKopecks > 0 && extractedKopecks === null) {
            // Проверяем, есть ли в тексте упоминание о копейках (может быть "0 копійок")
            const hasKopecksMention = /коп/i.test(textValue);
            if (!hasKopecksMention) {
                // Если копейки есть в числе, но не упомянуты в тексте - несоответствие
                return false;
            }
        }

        // Если все проверки пройдены, считаем валидным
        return true;
    } catch (e) {
        console.warn('Error validating amount in words:', e);
        return false;
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', init);

