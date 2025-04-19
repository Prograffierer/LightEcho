import os

class Serial:
    def __init__(self, com, **kwargs):
        self.fname = com + ".txt"
        if not os.path.exists(self.fname):
            with open(self.fname, "x"):
                pass
        self.already_read = []

    # def _num(self):
    #     with open(self.fname) as f:
    #         def opt_int(line):
    #             try:
    #                 return int(line)
    #             ex
    #         return list(map(lambda line: line[:-1] if line.endswith("\n") else line, f.readlines()))

    def reset_input_buffer(self) -> None:
        with open(self.fname, "w"):
            pass

    def read_all(self) -> bytes:
        with open(self.fname) as f:
            content = f.read(1)
            if content == "":
                return bytes()
            try:
                field = int(content)
            except ValueError:
                print(f"Invalid read {content}")
                return bytes()
        self.reset_input_buffer()
        return bytes((field, 255))
    
    @property
    def in_waiting(self) -> int:
        with open(self.fname) as f:
            try:
                int(f.read(1))
                return 2
            except ValueError:
                return 0
            
    def write(self, bstr):
        with open(self.fname + "_out", "a") as f:
            f.write(f"{bstr[0]}\n")
