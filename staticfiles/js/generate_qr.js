document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('product-search');
    const productIdInput = document.getElementById('product_id');
    const resultsContainer = document.getElementById('search-results');
    const resultsList = document.getElementById('results-list');
    const productInfo = document.getElementById('product-info');
    const productName = document.getElementById('product-name');
    const priceValue = document.getElementById('price-value');
    const shortDescription = document.getElementById('short-description');
    const fullDescription = document.getElementById('full-description');
    const readMoreToggle = document.getElementById('read-more-toggle');
    const productImagePreview = document.getElementById('product-image-preview');
    const previewImage = document.getElementById('preview-image');

    let timeout = null;

    // Функция для обработки описания (удаление HTML тегов и ограничение слов)
    function processDescription(text) {
        if (!text) return { short: 'Не указано', full: 'Не указано', hasMore: false };

        const cleanText = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

        const words = cleanText.split(' ');

        if (words.length <= 10) {
            return { short: cleanText, full: cleanText, hasMore: false };
        }

        const shortText = words.slice(0, 10).join(' ') + '...';
        const fullText = cleanText;

        return { short: shortText, full: fullText, hasMore: true };
    }

    readMoreToggle.addEventListener('click', function() {
        if (shortDescription.style.display === 'none') {
            shortDescription.style.display = 'inline';
            fullDescription.style.display = 'none';
            readMoreToggle.textContent = 'читать дальше';
        } else {
            shortDescription.style.display = 'none';
            fullDescription.style.display = 'inline';
            readMoreToggle.textContent = 'свернуть';
        }
    });

    // Функция для загрузки полной информации о товаре
    function loadProductDetails(productId) {
        fetch(`/api/product-details/?id=${productId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.product) {
                    const product = data.product;

                    productName.textContent = product.name || 'Неизвестный товар';
                    priceValue.textContent = product.price || '0';

                    const description = processDescription(product.description);
                    shortDescription.textContent = description.short;
                    fullDescription.textContent = description.full;

                    if (description.hasMore) {
                        readMoreToggle.style.display = 'inline';
                    } else {
                        readMoreToggle.style.display = 'none';
                    }

                    if (product.image) {
                        previewImage.src = `https://b24-oyi9l4.bitrix24.ru${product.image}`;
                        previewImage.onerror = function() {
                            productImagePreview.style.display = 'none';
                        };
                        productImagePreview.style.display = 'block';
                    } else {
                        productImagePreview.style.display = 'none';
                    }

                    productInfo.style.display = 'block';
                }
            })
            .catch(error => {
                console.error('Error loading product details:', error);
                // Показываем базовую информацию
                productName.textContent = `Товар ID: ${productId}`;
                priceValue.textContent = 'Информация недоступна';
                shortDescription.textContent = 'Не указано';
                fullDescription.textContent = 'Не указано';
                readMoreToggle.style.display = 'none';
                productImagePreview.style.display = 'none';
                productInfo.style.display = 'block';
            });
    }

    // Поиск товаров при вводе
    searchInput.addEventListener('input', function() {
        clearTimeout(timeout);
        timeout = setTimeout(function() {
            const query = searchInput.value.trim();
            if (query.length < 2) {
                resultsContainer.style.display = 'none';
                return;
            }

            fetch(`/api/search-products/?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    resultsList.innerHTML = '';

                    if (data.results && data.results.length > 0) {
                        data.results.forEach(product => {
                            const li = document.createElement('li');
                            li.innerHTML = `
                                <div style="display: flex; align-items: center; gap: 10px; padding: 8px;">
                                    ${product.image ? `<img src="https://b24-oyi9l4.bitrix24.ru${product.image}"
                                        alt="${product.name}"
                                        style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;"
                                        onerror="this.style.display='none'">` : ''}
                                    <div>
                                        <strong>${product.name}</strong><br>
                                        <small>ID: ${product.id} | Цена: ${product.price} ₽</small>
                                    </div>
                                </div>
                            `;

                            li.addEventListener('click', function() {
                                productIdInput.value = product.id;
                                searchInput.value = product.name;
                                resultsContainer.style.display = 'none';

                                // Загружаем полную информацию о товаре
                                loadProductDetails(product.id);
                            });

                            resultsList.appendChild(li);
                        });
                        resultsContainer.style.display = 'block';
                    } else {
                        resultsContainer.style.display = 'none';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    resultsContainer.style.display = 'none';
                });
        }, 300);
    });

    // Получение информации о товаре по ID при ручном вводе
    productIdInput.addEventListener('blur', function() {
        const productId = this.value.trim();
        if (productId) {
            loadProductDetails(productId);
        }
    });

    // Скрытие результатов при клике вне области
    document.addEventListener('click', function(e) {
        if (!resultsContainer.contains(e.target) && e.target !== searchInput) {
            resultsContainer.style.display = 'none';
        }
    });
});