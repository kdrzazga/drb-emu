class DrbError(Exception):

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class ResourceNotFound(DrbError):
    pass


class ResourceAlreadyExists(DrbError):
    pass


class ResourceNotEmpty(DrbError):
    pass


class InvalidParameterValue(DrbError):
    pass


class UnsupportedStatement(DrbError):
    pass
