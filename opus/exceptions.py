from opus.api.info import strerror


class OpusError(Exception):

    def __init__(self, code):
        self.code = code

    def __str__(self):
        err_msg = strerror(self.code)
        # 确保返回str类型（兼容Python 3）
        if isinstance(err_msg, bytes):
            return err_msg.decode('utf-8')
        return err_msg