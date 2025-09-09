import time
from datetime import datetime
from typing import cast
from azure.core.exceptions import HttpResponseError
from azure.core.rest import AsyncHttpResponse


class AzureRequestThrottled(HttpResponseError):
    def handle_delay(self):
        if not self.response:
            return
        response = cast(AsyncHttpResponse, self.response)
        remaining_quota = response.headers["x-ms-user-quota-remaining"]
        resets_after = response.headers["x-ms-user-quota-resets-after"]
        if int(remaining_quota) < 1:
            # AI! I want to sleep here until resets_after
            time_obj = ime_object = datetime.strptime(resets_after, "%H:%M:%S").time()
            time.sleep(time_obj)

        response.headers
        pass
