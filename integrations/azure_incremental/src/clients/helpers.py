import asyncio
import time
from datetime import datetime
from typing import cast
from azure.core.exceptions import HttpResponseError
from azure.core.rest import AsyncHttpResponse


class AzureRequestThrottled(HttpResponseError):
    async def handle_delay(self) -> None:
        if not self.response:
            return
        response = cast(AsyncHttpResponse, self.response)
        remaining_quota = response.headers["x-ms-user-quota-remaining"]
        resets_after = response.headers["x-ms-user-quota-resets-after"]
        if int(remaining_quota) < 1:
            time_obj = datetime.strptime(resets_after, "%H:%M:%S").time()
            sleep_duration = (
                time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second
            )
            await asyncio.sleep(sleep_duration)
