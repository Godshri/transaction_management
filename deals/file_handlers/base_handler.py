import abc
import csv
import io
from django.http import HttpResponse
import openpyxl


class BaseFileHandler(abc.ABC):
    """Базовый класс для обработки файлов"""

    @abc.abstractmethod
    def read_records(self, file):
        """Чтение записей из файла"""
        pass

    @abc.abstractmethod
    def write_records(self, records):
        """Запись записей в файл"""
        pass


class CSVHandler(BaseFileHandler):
    """Обработчик CSV файлов"""

    def read_records(self, file):
        """Чтение CSV файла с поддержкой русской кодировки"""
        try:
            # Пытаемся прочитать в UTF-8
            decoded_file = file.read().decode('utf-8')
        except UnicodeDecodeError:
            # Если не получается, пробуем Windows-1251 (кириллица)
            file.seek(0)
            decoded_file = file.read().decode('cp1251')

        io_string = io.StringIO(decoded_file)

        # Определяем разделитель (запятая или точка с запятой)
        sample = decoded_file[:1024]
        if ';' in sample and sample.count(';') > sample.count(','):
            delimiter = ';'
        else:
            delimiter = ','

        reader = csv.DictReader(io_string, delimiter=delimiter)

        records = []
        for row in reader:
            # Нормализуем названия колонок (приводим к нижнему регистру и убираем пробелы)
            normalized_row = {}
            for key, value in row.items():
                normalized_key = key.strip().lower()
                normalized_row[normalized_key] = value.strip() if value else ''

            records.append({
                'first_name': normalized_row.get('имя', ''),
                'last_name': normalized_row.get('фамилия', ''),
                'phone': normalized_row.get('номер телефона', ''),
                'email': normalized_row.get('почта', ''),
                'company_name': normalized_row.get('компания', '')
            })

        return records

    def write_records(self, records):
        """Создание CSV файла с русскими заголовками"""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="contacts_export.csv"'

        # Добавляем BOM для правильного отображения кириллицы в Excel
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['имя', 'фамилия', 'номер телефона', 'почта', 'компания'])

        for record in records:
            writer.writerow([
                record.get('first_name', ''),
                record.get('last_name', ''),
                record.get('phone', ''),
                record.get('email', ''),
                record.get('company_name', '')
            ])

        return response


class XLSXHandler(BaseFileHandler):
    """Обработчик XLSX файлов"""

    def read_records(self, file):
        """Чтение XLSX файла"""
        workbook = openpyxl.load_workbook(file)
        sheet = workbook.active

        records = []
        headers = []

        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                # Нормализуем заголовки
                headers = []
                for cell in row:
                    if cell:
                        header_text = str(cell).strip().lower()
                        headers.append(header_text)
                    else:
                        headers.append('')
                continue

            record = {}
            for j, cell in enumerate(row):
                if j < len(headers):
                    cell_value = str(cell) if cell is not None else ''
                    record[headers[j]] = cell_value.strip()

            # Маппинг полей с учетом возможных вариантов названий
            first_name = (record.get('имя') or record.get('name') or
                          record.get('first name') or record.get('firstname') or '')

            last_name = (record.get('фамилия') or record.get('last name') or
                         record.get('lastname') or record.get('surname') or '')

            phone = (record.get('номер телефона') or record.get('телефон') or
                     record.get('phone') or record.get('номер') or '')

            email = (record.get('почта') or record.get('email') or
                     record.get('e-mail') or record.get('mail') or '')

            company_name = (record.get('компания') or record.get('company') or
                            record.get('организация') or record.get('фирма') or '')

            records.append({
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
                'email': email,
                'company_name': company_name
            })

        return records

    def write_records(self, records):
        """Создание XLSX файла"""
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Контакты"

        # Заголовки на русском
        sheet.append(['имя', 'фамилия', 'номер телефона', 'почта', 'компания'])

        # Данные
        for record in records:
            sheet.append([
                record.get('first_name', ''),
                record.get('last_name', ''),
                record.get('phone', ''),
                record.get('email', ''),
                record.get('company_name', '')
            ])

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="contacts_export.xlsx"'

        workbook.save(response)
        return response


class FileHandlerFactory:
    """Фабрика для получения обработчиков файлов"""

    @staticmethod
    def get_handler(file_format):
        if file_format == 'csv':
            return CSVHandler()
        elif file_format == 'xlsx':
            return XLSXHandler()
        else:
            raise ValueError(f"Unsupported file format: {file_format}")