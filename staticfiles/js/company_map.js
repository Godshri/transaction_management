function initMap() {
    if (typeof ymaps === 'undefined') {
        console.error('Yandex Maps API не загружена');
        return;
    }

    ymaps.ready(function() {
        var map = new ymaps.Map('map', {
            center: [55.76, 37.64],
            zoom: 10,
            controls: ['zoomControl', 'fullscreenControl', 'typeSelector']
        });

        var points = window.points || [];

        console.log('Загружено точек:', points.length);
        console.log('Точки:', points);

        if (points.length === 0) {
            var noDataControl = new ymaps.Control({
                content: '<div style="padding: 10px; background: white; border-radius: 5px; border: 1px solid #ddd;">' +
                         '<p>Нет данных для отображения на карте</p>' +
                         '<button onclick="refreshMap()" style="padding: 5px 10px; background: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer; margin-top: 5px;">Обновить карту</button>' +
                         '</div>',
                position: {top: 10, left: 10}
            });
            map.controls.add(noDataControl);
            return;
        }

        var objectCollection = new ymaps.GeoObjectCollection(null, {
            preset: 'islands#blueIcon',
            clusterize: true,
            gridSize: 64,
            clusterDisableClickZoom: true
        });

        points.forEach(function(point, index) {
            if (!point.GEOCODE || !Array.isArray(point.GEOCODE) || point.GEOCODE.length !== 2) {
                console.warn('Пропущена точка без координат:', point);
                return;
            }

            var iconContent = point.LogoURL ?
                '<img src="' + point.LogoURL + '" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">' :
                '<div style="width: 40px; height: 40px; border-radius: 50%; background: #007bff; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">' +
                (point.TITLE ? point.TITLE.charAt(0).toUpperCase() : 'C') +
                '</div>';

            var placemark = new ymaps.Placemark(point.GEOCODE, {
                    balloonContentHeader: '<div class="company-name">' + (point.TITLE || 'Без названия') + '</div>',
                    balloonContentBody: `
                        <div class="company-balloon">
                            ${point.DESCRIPTION ?
                                '<div class="company-description" style="margin-bottom: 10px; font-size: 13px; color: #666;">' +
                                point.DESCRIPTION +
                                '</div>' :
                                ''}
                            ${point.ADDRESS ?
                                '<div class="company-address" style="font-size: 12px; color: #888; border-top: 1px solid #eee; padding-top: 8px; margin-top: 8px;">' +
                                '<strong>Адрес:</strong> ' + point.ADDRESS +
                                '</div>' :
                                ''}
                            ${point.LogoURL ?
                                `<img src="${point.LogoURL}" alt="Логотип" class="company-logo"
                                      onerror="this.style.display='none'" style="margin-top: 10px;">` :
                                ''}
                        </div>
                    `,
                    hintContent: point.TITLE || 'Компания'
                }, {
                iconLayout: 'default#imageWithContent',
                iconImageHref: '',
                iconImageSize: [50, 50],
                iconImageOffset: [-25, -25],

                iconContentLayout: ymaps.templateLayoutFactory.createClass(
                    '<div style="background: transparent; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center;">' +
                    iconContent +
                    '</div>'
                ),
                iconContentOffset: [0, 0],
                iconContentSize: [50, 50],

                balloonCloseButton: true,
                balloonPanelMaxMapArea: 0
            });

            objectCollection.add(placemark);
        });

        map.geoObjects.add(objectCollection);

        if (objectCollection.getLength() > 0) {
            var bounds = objectCollection.getBounds();
            if (bounds) {
                map.setBounds(bounds, {
                    checkZoomRange: true,
                    zoomMargin: 50
                });
            }
        }

        var searchControl = new ymaps.control.SearchControl({
            options: {
                float: 'right',
                floatIndex: 200,
                noPlacemark: true,
                placeholder: 'Поиск компаний...'
            }
        });
        map.controls.add(searchControl);

        searchControl.events.add('resultselect', function (e) {
            var index = e.get('index');
            searchControl.getResult(index).then(function (res) {
                map.setCenter(res.geometry.getCoordinates(), 15);
            });
        });

        map.behaviors.enable('scrollZoom');
    });
}

function refreshMap() {
    location.reload();
}

function updateStats() {
    var points = window.points || [];
    var validPoints = points.filter(function(point) {
        return point.GEOCODE && Array.isArray(point.GEOCODE) && point.GEOCODE.length === 2;
    });

    document.getElementById('companies-count').textContent = points.length;
    document.getElementById('geocoded-count').textContent = validPoints.length;
}

document.addEventListener('DOMContentLoaded', function() {
    updateStats();

    if (document.getElementById('map')) {
        setTimeout(initMap, 100);
    }
});