document.addEventListener('DOMContentLoaded', function() {
    // Инициализация BX24
    if (typeof BX24 !== 'undefined') {
        BX24.init(function() {
            console.log('BX24 SDK инициализирован');
        });
    }

    // Обработка кликов по сотрудникам и руководителям
    document.querySelectorAll('.employee-link, .manager-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const userId = this.getAttribute('data-user-id');
            openUserProfile(userId);
        });
    });

    // Генерация тестовых звонков
    document.getElementById('generate-test-calls').addEventListener('click', function() {
        const button = this;
        const status = document.getElementById('generate-status');

        button.disabled = true;
        status.textContent = 'Генерация тестовых данных...';

        fetch('/employees/generate-test-calls/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                status.textContent = data.message;
                // Обновляем страницу через 2 секунды
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                status.textContent = 'Ошибка: ' + data.error;
            }
        })
        .catch(error => {
            status.textContent = 'Ошибка сети';
            console.error('Error:', error);
        })
        .finally(() => {
            button.disabled = false;
        });
    });

    // Функция для открытия профиля пользователя
    function openUserProfile(userId) {
        if (typeof BX24 !== 'undefined' && BX24.openPath) {
            // Открываем в слайдере
            BX24.openPath(`/company/personal/user/${userId}/`, { slide: true });
        } else {
            // Fallback: открываем в новой вкладке
            window.open(`/company/personal/user/${userId}/`, '_blank');
        }
    }

    // Вспомогательная функция для получения CSRF токена
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});