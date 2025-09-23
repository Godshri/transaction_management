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

    if (tabName === 'history') {
        loadHistory();
    }
}

document.getElementById('importForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);

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

document.getElementById('exportForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

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
            window.location.href = `/contacts/download/${data.job_id}/`;
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

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('history').classList.contains('active')) {
        loadHistory();
    }
});