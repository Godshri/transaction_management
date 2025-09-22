// Функции для управления вкладками
function openTab(tabName) {
    const tabContents = document.getElementsByClassName('tab-content');
    for (let i = 0; i < tabContents.length; i++) {
        tabContents[i].classList.remove('active');
    }

    const tabButtons = document.getElementsByClassName('tab-btn');
    for (let i = 0; i < tabButtons.length; i++) {
        tabButtons[i].classList.remove('active');
    }

    document.getElementById(tabName).classList.add('active');
    event.currentTarget.classList.add('active');

    // Если открываем вкладку истории, загружаем данные
    if (tabName === 'history') {
        loadHistory();
    }
}

// Обработка формы импорта
document.getElementById('importForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);

    // Показываем прогресс
    document.getElementById('importProgress').style.display = 'block';
    document.getElementById('importStatus').textContent = 'Начинаем импорт...';

    fetch('/contacts/import/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('importStatus').textContent = 'Импорт завершен успешно!';
            // Обновляем историю
            loadHistory();
        } else {
            document.getElementById('importStatus').textContent = 'Ошибка: ' + data.error;
        }
    })
    .catch(error => {
        console.error('Ошибка:', error);
        document.getElementById('importStatus').textContent = 'Ошибка импорта: ' + error.message;
    });
});

// Обработка формы экспорта
document.getElementById('exportForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

    // Показываем прогресс
    document.getElementById('exportProgress').style.display = 'block';
    document.getElementById('exportStatus').textContent = 'Начинаем экспорт...';

    fetch('/contacts/export/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('exportStatus').textContent = 'Экспорт завершен успешно!';
            // Скачиваем файл
            window.location.href = `/contacts/download/${data.job_id}/`;
            // Обновляем историю
            loadHistory();
        } else {
            document.getElementById('exportStatus').textContent = 'Ошибка: ' + data.error;
        }
    })
    .catch(error => {
        console.error('Ошибка:', error);
        document.getElementById('exportStatus').textContent = 'Ошибка экспорта: ' + error.message;
    });
});

// Функция для загрузки истории операций
function loadHistory() {
    fetch('/contacts/history/')
    .then(response => response.json())
    .then(data => {
        const historyTable = document.getElementById('historyTable');
        historyTable.innerHTML = '';

        if (data.length === 0) {
            historyTable.innerHTML = '<tr><td colspan="6">Нет данных об операциях</td></tr>';
            return;
        }

        data.forEach(operation => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${operation.type_display}</td>
                <td>${operation.format.toUpperCase()}</td>
                <td>${operation.status_display}</td>
                <td>${operation.processed_records}/${operation.total_records}</td>
                <td>${new Date(operation.created_at).toLocaleString('ru-RU')}</td>
                <td>
                    ${operation.job_type === 'export' && operation.status === 'completed' ?
                        `<a href="/contacts/download/${operation.id}/" class="download-link">Скачать</a>` :
                        '—'
                    }
                </td>
            `;
            historyTable.appendChild(row);
        });
    })
    .catch(error => {
        console.error('Ошибка загрузки истории:', error);
        document.getElementById('historyTable').innerHTML = '<tr><td colspan="6">Ошибка загрузки истории</td></tr>';
    });
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Загружаем историю если открыта соответствующая вкладка
    if (document.getElementById('history').classList.contains('active')) {
        loadHistory();
    }
});