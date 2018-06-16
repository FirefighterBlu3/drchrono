class sqliteSettings(object):
    def __init__(self, get_response=None):
        # django 2 expects middleware to accept a get_response callable
        self.get_response = get_response
        super().__init__()

    def __call__(self, request):
        if hasattr(self, 'process_request'):
            response = self.process_request(request)
        if not response:
            response = self.get_response(request)
        if hasattr(self, 'process_response'):
            response = self.process_response(request, response)
        return response

    def process_request(self, request):
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute('PRAGMA temp_store = MEMORY;')
        cursor.execute('PRAGMA synchronous=OFF')
