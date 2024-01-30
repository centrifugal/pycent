import asyncio

from cent import AsyncClient, Client

BASE_URL = "http://localhost:8000/api"
API_KEY = "api_key"

async_client = AsyncClient(BASE_URL, API_KEY)
sync_client = Client(BASE_URL, API_KEY)


async def main() -> None:
    response = await async_client.publish(
        channel="example:123",
        data={"message": "Hello world!"},
    )
    print(response)
    response = sync_client.publish(
        channel="example:123",
        data={"message": "Hello world!"},
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
