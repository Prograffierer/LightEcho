import socket
from config import IP_ADDR

class SerialSocket(socket.socket):
    def __init__(self):
        super().__init__()
        self.connect((IP_ADDR, 8888))
        self.last_field = None
        self._was_right_anyways = False
        self.setblocking(False)

    def reset(self):
        self.update()
        self.last_field = None
        # self.send(bytes((37,)))

    def update(self):
        try:
            while True:
                res = self.recv(1)
                if res[0] == 9:
                    self._was_right_anyways = True
                else:
                    self.last_field = res[0]
        except BlockingIOError:
            pass
        # except Exception as e:
        #     print(e.__class__.__name__)
        except IndexError:
            raise ConnectionAbortedError("Connection closed (probably by remote host)")

    @property
    def is_available(self):
        self.update()
        return self.last_field is not None

    def get_field(self):
        """Can only be called if is_available is true"""
        self.update()
        assert self.last_field is not None, RuntimeError("No step was recognised when SerialSocket.get_field() was called")
        lf = self.last_field
        self.last_field = None
        return lf

    def was_right(self):
        self.update()
        if self._was_right_anyways:
            self._was_right_anyways = False
            return True
        return False
