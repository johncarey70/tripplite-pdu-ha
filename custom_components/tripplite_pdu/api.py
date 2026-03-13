"""API client for the Tripp Lite PDU."""

import logging
import time

import aiohttp

from .const import API_ACCEPT_VERSION, API_CONTENT_TYPE, DEFAULT_DEVICE_ID

_LOGGER = logging.getLogger(__name__)


class TrippliteError(Exception):
    """Base exception for the Tripp Lite PDU integration."""


class TrippliteConnectionError(TrippliteError):
    """Raised when the PDU cannot be reached or authenticated."""


class TrippliteResponseError(TrippliteError):
    """Raised when the PDU returns an invalid response."""


class TrippliteApiClient:
    """Client for communicating with the Tripp Lite PDU."""

    def __init__(self, host: str, username: str, password: str) -> None:
        """Initialize API client."""

        self.host = host
        self.username = username
        self.password = password

        self.base_url = f"https://{host}"

        self.token: str | None = None
        self.token_expire: int = 0

        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))

    async def login(self) -> str:
        """Authenticate and obtain access token."""

        url = f"{self.base_url}/api/oauth/token"

        headers = {
            "Content-Type": API_CONTENT_TYPE,
            "Accept-Version": API_ACCEPT_VERSION,
        }

        payload = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }

        async with self.session.post(url, headers=headers, json=payload) as resp:
            text = await resp.text()

            if resp.status >= 400:
                raise TrippliteConnectionError(
                    f"Login failed: HTTP {resp.status}: {text}"
                )

            data = await resp.json(content_type=None)

        self.token = data["access_token"]
        self.token_expire = time.time() + 800

        return self.token

    async def get_token(self) -> str:
        """Return a valid access token."""

        if self.token and time.time() < self.token_expire:
            return self.token

        return await self.login()

    async def _parse_response(self, resp) -> dict | str | None:
        """Parse HTTP response body."""
        text = await resp.text()

        if not text.strip():
            return None

        try:
            return await resp.json(content_type=None)
        except aiohttp.ContentTypeError:
            return text
        except ValueError:
            return text

    async def request(self, method: str, path: str, json: dict | None = None):
        """Execute API request."""

        token = await self.get_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept-Version": API_ACCEPT_VERSION,
        }

        if json is not None:
            headers["Content-Type"] = API_CONTENT_TYPE

        url = f"{self.base_url}{path}"

        async with self.session.request(
            method, url, headers=headers, json=json
        ) as resp:
            if resp.status == 401:
                self.token = None
                self.token_expire = 0

                token = await self.get_token()
                headers["Authorization"] = f"Bearer {token}"

                async with self.session.request(
                    method, url, headers=headers, json=json
                ) as retry_resp:
                    if retry_resp.status >= 400:
                        raise TrippliteConnectionError(
                            f"HTTP {retry_resp.status} calling {path}: {await retry_resp.text()}"
                        )

                    return await self._parse_response(retry_resp)

            if resp.status >= 400:
                raise TrippliteConnectionError(
                    f"HTTP {resp.status} calling {path}: {await resp.text()}"
                )

            return await self._parse_response(resp)

    async def async_test_auth(self):
        """Validate credentials."""

        await self.request("GET", "/api/loads")

    async def get_loads(self):
        """Fetch outlet and main load states."""

        data = await self.request("GET", "/api/loads")

        if not isinstance(data, dict):
            raise TrippliteResponseError(f"Unexpected /api/loads response: {data}")

        if "data" not in data:
            raise TrippliteResponseError(f"Malformed /api/loads response: {data}")

        result = {}

        for load in data["data"]:
            result[int(load["id"])] = load["attributes"]["state"]

        main = await self.request("GET", f"/api/loads/main/{DEFAULT_DEVICE_ID}")

        if not isinstance(main, dict):
            raise TrippliteResponseError(f"Unexpected /api/loads/main response: {main}")

        if "data" not in main:
            raise TrippliteResponseError(f"Malformed /api/loads/main response: {main}")

        result["main_load"] = main["data"]["attributes"]["state"]
        return result

    async def set_load(self, load_id: int, turn_on: bool) -> None:
        """Set outlet state."""

        action = "LOAD_ACTION_ON" if turn_on else "LOAD_ACTION_OFF"

        payload = {
            "data": {
                "type": "loads_execute",
                "attributes": {
                    "device_id": DEFAULT_DEVICE_ID,
                    "load_action": action,
                },
            }
        }

        await self.request(
            "PATCH",
            f"/api/loads_execute/{load_id}",
            json=payload,
        )

    async def set_main_load(self, turn_on: bool) -> None:
        """Set main load state."""

        action = "LOAD_ACTION_ON" if turn_on else "LOAD_ACTION_OFF"

        payload = {
            "data": {
                "type": "loads_execute_main",
                "attributes": {
                    "load_action": action,
                },
            }
        }

        await self.request(
            "PATCH",
            f"/api/loads_execute/main/{DEFAULT_DEVICE_ID}",
            json=payload,
        )
