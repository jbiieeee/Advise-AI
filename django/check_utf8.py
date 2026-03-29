import sys
try:
    with open(r'c:\Users\longa\Documents\websys_copy\django\core\templates\core\adviser.html', 'rb') as f:
        content = f.read()
    content.decode('utf-8')
    print('OK')
except UnicodeDecodeError as e:
    offset = e.start
    line_num = content[:offset].count(b'\n') + 1
    print(f'Error at line {line_num}, offset {offset}')
    print(content[max(0, offset-50):offset+50])
