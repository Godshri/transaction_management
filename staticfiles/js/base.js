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

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close">&times;</button>
        </div>
    `;

    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#f8d7da' : type === 'success' ? '#d4edda' : '#d1ecf1'};
        color: ${type === 'error' ? '#721c24' : type === 'success' ? '#155724' : '#0c5460'};
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        z-index: 1000;
        max-width: 300px;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 5000);

    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.remove();
    });
}

function checkProgress(jobId, type = 'import') {
    const checkInterval = setInterval(() => {
        fetch(`/contacts/status/${jobId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const progress = data.total_records > 0 ?
                        (data.processed_records / data.total_records) * 100 : 0;

                    document.querySelector('.progress-bar').style.width = `${progress}%`;

                    if (type === 'import') {
                        document.getElementById('processed').textContent = data.processed_records;
                        document.getElementById('total').textContent = data.total_records;
                    } else {
                        document.getElementById('exportProcessed').textContent = data.processed_records;
                        document.getElementById('exportTotal').textContent = data.total_records;
                    }

                    if (data.status === 'completed') {
                        const statusElement = type === 'import' ?
                            document.getElementById('importStatus') :
                            document.getElementById('exportStatus');
                        statusElement.textContent = type === 'import' ? 'Импорт завершен!' : 'Экспорт завершен!';
                        clearInterval(checkInterval);
                        if (typeof loadHistory === 'function') loadHistory();
                    } else if (data.status === 'failed') {
                        const statusElement = type === 'import' ?
                            document.getElementById('importStatus') :
                            document.getElementById('exportStatus');
                        statusElement.textContent = 'Ошибка: ' + (data.error_message || 'Неизвестная ошибка');
                        clearInterval(checkInterval);
                    }
                }
            })
            .catch(error => {
                console.error('Ошибка проверки прогресса:', error);
            });
    }, 2000);
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Base JavaScript loaded');
});