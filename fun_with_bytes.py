def decode(msg):
    code = int(msg)

def encode(field, value):
    code = (field << 12) + (value << 2)
    print(code)
    assert code < 2 ** 16
    return bytes((code // 256, code % 256))
