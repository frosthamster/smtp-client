# SMTP

Консольная утилита, позволяющая отправлять email письма при помощи протокола smtp

## Возможности
- указание конкретного smtp сервера
- поддержка вложений
- поддержка html

## Примеры запуска
`python ./main.py -l pythonsmtptask@gmail.com -r frosthamster@gmail.com < message.txt`

`python ./main.py -l pythonsmtptask@gmail.com -r frosthamster@gmail.com --debug -s test -rc 10 -eh --server smtp.gmail.com -bcc pythonsmtptask@gmail.com -a ./mail.py ./smtp.py -as 10 --password pythontask -m ./README.md`

## Зависимости
- Python 3.6

### Коды выхода
- 1 - ошибка валидации email адреса
- 2 - ошибка 4хх / 5xx smtp сервера
- 3 - ошибка подключения к серверу
- 4 - не найден файл письма или вложения