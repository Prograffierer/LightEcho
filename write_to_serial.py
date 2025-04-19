def write_to_file(fname):
    field = input(fname + ": ")
    if field == "":
        return
    else:
        with open(fname + ".txt", "w") as f:
            f.write(str(int(field)))

while True:
    write_to_file("COM5")
    write_to_file("COM7")