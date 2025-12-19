// Login Page Script

// State
const state = {
    authToken: localStorage.getItem('authToken') || ''
};

// Elements
const elements = {
    loginForm: document.getElementById('loginForm'),
    username: document.getElementById('username'),
    password: document.getElementById('password'),
    rememberMe: document.getElementById('rememberMe'),
    togglePassword: document.getElementById('togglePassword'),
    loginButton: document.getElementById('loginButton'),
    loginMessage: document.getElementById('loginMessage'),
    loginMessageIcon: document.getElementById('loginMessageIcon'),
    loginMessageText: document.getElementById('loginMessageText'),

    // Registration
    registerLink: document.getElementById('registerLink'),
    registerModal: document.getElementById('registerModal'),
    closeRegisterModal: document.getElementById('closeRegisterModal'),
    cancelRegister: document.getElementById('cancelRegister'),
    saveRegister: document.getElementById('saveRegister'),
    registerUsername: document.getElementById('registerUsername'),
    registerEmail: document.getElementById('registerEmail'),
    registerPassword: document.getElementById('registerPassword'),
    toggleRegisterPassword: document.getElementById('toggleRegisterPassword'),
    registerMessage: document.getElementById('registerMessage'),
    registerMessageIcon: document.getElementById('registerMessageIcon'),
    registerMessageText: document.getElementById('registerMessageText'),

    // Forgot Password
    forgotPasswordLink: document.getElementById('forgotPasswordLink'),
    forgotPasswordModal: document.getElementById('forgotPasswordModal'),
    closeForgotPasswordModal: document.getElementById('closeForgotPasswordModal'),
    cancelForgotPassword: document.getElementById('cancelForgotPassword'),
    sendResetPassword: document.getElementById('sendResetPassword'),
    forgotPasswordInput: document.getElementById('forgotPasswordInput'),
    forgotPasswordMessage: document.getElementById('forgotPasswordMessage'),
    forgotPasswordMessageIcon: document.getElementById('forgotPasswordMessageIcon'),
    forgotPasswordMessageText: document.getElementById('forgotPasswordMessageText')
};

// Check if already logged in
// ВАЖНО: Не проверяем токен при загрузке страницы, так как сервер сам решает,
// что показывать на основе cookie. Это предотвращает бесконечные редиректы.
// Если пользователь уже авторизован, сервер вернет index.html вместо login.html.
// Проверка токена выполняется только после успешного логина.

// Initialize
function init() {
    setupEventListeners();
}

// Setup event listeners
function setupEventListeners() {
    // Login form
    elements.loginForm.addEventListener('submit', handleLogin);

    // Toggle password visibility
    elements.togglePassword.addEventListener('click', () => {
        togglePasswordVisibility(elements.password, elements.togglePassword);
    });

    // Registration
    elements.registerLink.addEventListener('click', (e) => {
        e.preventDefault();
        showRegisterModal();
    });

    elements.closeRegisterModal.addEventListener('click', hideRegisterModal);
    elements.cancelRegister.addEventListener('click', hideRegisterModal);
    elements.saveRegister.addEventListener('click', handleRegister);

    if (elements.toggleRegisterPassword) {
        elements.toggleRegisterPassword.addEventListener('click', () => {
            togglePasswordVisibility(elements.registerPassword, elements.toggleRegisterPassword);
        });
    }

    // Forgot Password
    elements.forgotPasswordLink.addEventListener('click', (e) => {
        e.preventDefault();
        showForgotPasswordModal();
    });

    elements.closeForgotPasswordModal.addEventListener('click', hideForgotPasswordModal);
    elements.cancelForgotPassword.addEventListener('click', hideForgotPasswordModal);
    elements.sendResetPassword.addEventListener('click', handleForgotPassword);

    // Modal backdrop clicks
    elements.registerModal.addEventListener('click', (e) => {
        if (e.target === elements.registerModal) {
            hideRegisterModal();
        }
    });

    elements.forgotPasswordModal.addEventListener('click', (e) => {
        if (e.target === elements.forgotPasswordModal) {
            hideForgotPasswordModal();
        }
    });

    // Enter key handlers
    elements.password.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            elements.loginForm.dispatchEvent(new Event('submit'));
        }
    });
}

// Toggle password visibility
function togglePasswordVisibility(input, button) {
    const type = input.type === 'password' ? 'text' : 'password';
    input.type = type;
    const icon = button.querySelector('i');
    icon.classList.toggle('fa-eye');
    icon.classList.toggle('fa-eye-slash');
}

// Handle login
async function handleLogin(e) {
    e.preventDefault();

    const username = elements.username.value.trim();
    const password = elements.password.value.trim();

    if (!username || !password) {
        showLoginMessage('Будь ласка, введіть ім\'я користувача та пароль', true);
        return;
    }

    // Disable button
    elements.loginButton.disabled = true;
    elements.loginButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Вхід...';
    clearLoginMessage();

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
            throw new Error(data.detail || 'Помилка входу');
        }

        // Save token
        const token = data.access_token;
        state.authToken = token;
        localStorage.setItem('authToken', token);

        // Remember me
        if (elements.rememberMe.checked) {
            localStorage.setItem('rememberMe', 'true');
        } else {
            localStorage.removeItem('rememberMe');
        }

        // Show success message
        showLoginMessage('Успішний вхід! Перенаправлення...', false);

        // Check for redirect parameter
        const urlParams = new URLSearchParams(window.location.search);
        const redirect = urlParams.get('redirect');

        // Redirect to main page or to the redirect URL
        setTimeout(() => {
            if (redirect) {
                window.location.href = redirect;
            } else {
                window.location.href = '/';
            }
        }, 1000);

    } catch (error) {
        showLoginMessage(error.message || 'Помилка входу. Перевірте ім\'я користувача та пароль', true);
        elements.loginButton.disabled = false;
        elements.loginButton.innerHTML = '<i class="fas fa-sign-in-alt"></i> Увійти';
    }
}

// Show login message
function showLoginMessage(text, isError = false) {
    elements.loginMessage.style.display = 'flex';
    elements.loginMessageIcon.className = `fas ${isError ? 'fa-exclamation-circle' : 'fa-check-circle'}`;
    elements.loginMessageText.textContent = text;
    elements.loginMessage.className = `login-message ${isError ? 'error' : 'success'}`;
}

function clearLoginMessage() {
    elements.loginMessage.style.display = 'none';
    elements.loginMessageText.textContent = '';
}

// Registration
function showRegisterModal() {
    elements.registerModal.classList.add('active');
    elements.registerUsername.focus();
}

function hideRegisterModal() {
    elements.registerModal.classList.remove('active');
    clearRegisterMessage();
    // Clear form
    elements.registerUsername.value = '';
    elements.registerEmail.value = '';
    elements.registerPassword.value = '';
}

async function handleRegister() {
    const username = elements.registerUsername.value.trim();
    const email = elements.registerEmail.value.trim();
    const password = elements.registerPassword.value.trim();

    if (!username || !password) {
        showRegisterMessage('Будь ласка, заповніть всі обов\'язкові поля', true);
        return;
    }

    elements.saveRegister.disabled = true;
    elements.saveRegister.textContent = 'Реєстрація...';
    clearRegisterMessage();

    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username,
                email: email || null,
                password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Помилка реєстрації');
        }

        showRegisterMessage('Реєстрація успішна! Виконується вхід...', false);

        // Auto login after registration
        setTimeout(async () => {
            try {
                const loginResponse = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username, password })
                });

                const loginData = await loginResponse.json();

                if (loginResponse.ok) {
                    state.authToken = loginData.access_token;
                    localStorage.setItem('authToken', loginData.access_token);
                    hideRegisterModal();
                    showLoginMessage('Реєстрація та вхід виконано успішно! Перенаправлення...', false);

                    // Check for redirect parameter
                    const urlParams = new URLSearchParams(window.location.search);
                    const redirect = urlParams.get('redirect');

                    setTimeout(() => {
                        if (redirect) {
                            window.location.href = redirect;
                        } else {
                            window.location.href = '/';
                        }
                    }, 1000);
                } else {
                    showRegisterMessage('Реєстрація успішна, але вхід не вдався. Спробуйте увійти вручну.', true);
                }
            } catch (error) {
                showRegisterMessage('Реєстрація успішна, але вхід не вдався. Спробуйте увійти вручну.', true);
            }
        }, 1000);

    } catch (error) {
        showRegisterMessage(error.message || 'Помилка реєстрації', true);
    } finally {
        elements.saveRegister.disabled = false;
        elements.saveRegister.textContent = 'Зареєструватися';
    }
}

function showRegisterMessage(text, isError = false) {
    elements.registerMessage.style.display = 'flex';
    elements.registerMessageIcon.className = `fas ${isError ? 'fa-exclamation-circle' : 'fa-check-circle'}`;
    elements.registerMessageText.textContent = text;
    elements.registerMessage.className = `register-message ${isError ? 'error' : 'success'}`;
}

function clearRegisterMessage() {
    elements.registerMessage.style.display = 'none';
    elements.registerMessageText.textContent = '';
}

// Forgot Password
function showForgotPasswordModal() {
    elements.forgotPasswordModal.classList.add('active');
    elements.forgotPasswordInput.focus();
}

function hideForgotPasswordModal() {
    elements.forgotPasswordModal.classList.remove('active');
    clearForgotPasswordMessage();
    elements.forgotPasswordInput.value = '';
}

async function handleForgotPassword() {
    const input = elements.forgotPasswordInput.value.trim();

    if (!input) {
        showForgotPasswordMessage('Будь ласка, введіть email або ім\'я користувача', true);
        return;
    }

    elements.sendResetPassword.disabled = true;
    elements.sendResetPassword.textContent = 'Відправка...';
    clearForgotPasswordMessage();

    // TODO: Implement password reset API endpoint
    // For now, just show a message
    setTimeout(() => {
        showForgotPasswordMessage('Функція відновлення пароля поки не реалізована. Зверніться до адміністратора.', true);
        elements.sendResetPassword.disabled = false;
        elements.sendResetPassword.textContent = 'Відправити';
    }, 1000);
}

function showForgotPasswordMessage(text, isError = false) {
    elements.forgotPasswordMessage.style.display = 'flex';
    elements.forgotPasswordMessageIcon.className = `fas ${isError ? 'fa-exclamation-circle' : 'fa-check-circle'}`;
    elements.forgotPasswordMessageText.textContent = text;
    elements.forgotPasswordMessage.className = `forgot-password-message ${isError ? 'error' : 'success'}`;
}

function clearForgotPasswordMessage() {
    elements.forgotPasswordMessage.style.display = 'none';
    elements.forgotPasswordMessageText.textContent = '';
}

// Initialize on load
init();

