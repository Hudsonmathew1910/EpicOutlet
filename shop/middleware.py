from django.middleware.gzip import GZipMiddleware


class StreamingSafeGZipMiddleware(GZipMiddleware):
    """GZip everything except live event streams.

    Django's streaming gzip does not flush per chunk, so small progress events would sit in
    the compressor until the response ends. NDJSON streams (EpicBot progress) skip compression.
    """

    def process_response(self, request, response):
        if response.get('Content-Type', '').startswith('application/x-ndjson'):
            return response
        return super().process_response(request, response)
