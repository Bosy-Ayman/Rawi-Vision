import httpx
from ..utils.redis import redis_client
import json

class SubscriptionService:
    def __init__(self):
        self.developer_app_server_url = "http://localhost:8001"
    
    async def get_subscription_status(self, installation_uuid):
        url = f"{self.developer_app_server_url}/subscriptions/check-in/{installation_uuid}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        subscription_data = response.json()
        redis_client.set(f"{installation_uuid}", json.dumps(subscription_data))
        return subscription_data
    
    
