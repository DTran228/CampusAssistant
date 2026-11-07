class DomainError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message

    def result(self):
        return {"status": "error", "error": {"code": self.code, "message": self.message}}
