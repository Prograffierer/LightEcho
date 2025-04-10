def decode(msg):
    code = int(msg)
    field = code >> 12
    value = (code >> 2) % 1024
    return field, value

def encode(field, value):
    code = (field << 12) + (value << 2)
    print(code)
    assert code < 2 ** 16
    return bytes((code // 256, code % 256))
