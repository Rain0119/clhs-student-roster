"""產生只有虛構 ASCII 姓名的小型文字 PDF，不依賴原始名單。"""


def text_pdf(lines, *, image_page=False):
    escaped = [line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') for line in lines]
    instructions = 'BT /F1 12 Tf 50 750 Td ' + ' 0 -18 Td '.join(f'({line}) Tj' for line in escaped) + ' ET'
    stream = instructions.encode('ascii')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length ' + str(len(stream)).encode('ascii') + b' >>\nstream\n' + stream + b'\nendstream',
    ]
    if image_page:
        objects[1] = b'<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>'
        image_stream = b'q 100 0 0 100 50 50 cm /Im1 Do Q'
        objects.extend([
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im1 8 0 R >> >> /Contents 7 0 R >>',
            b'<< /Length ' + str(len(image_stream)).encode('ascii') + b' >>\nstream\n' + image_stream + b'\nendstream',
            b'<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 3 >>\nstream\n\x00\x00\x00\nendstream',
        ])
    content = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f'{number} 0 obj\n'.encode('ascii') + obj + b'\nendobj\n')
    xref = len(content)
    content.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode('ascii'))
    for offset in offsets[1:]:
        content.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    content.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode('ascii'))
    return bytes(content)
