"""API client for the Tripp Lite PDU integration."""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

from .const import API_ACCEPT_VERSION, API_CONTENT_TYPE, DEFAULT_DEVICE_ID

_LOGGER = logging.getLogger(__name__)


class TrippliteError(Exception):
    """Base exception for the Tripp Lite PDU integration."""


class TrippliteConnectionError(TrippliteError):
    """Raised when the PDU cannot be reached."""


class TrippliteAuthError(TrippliteError):
    """Raised when authentication fails."""


class TrippliteResponseError(TrippliteError):
    """Raised when the PDU returns an invalid response."""


# pylint: disable=too-many-instance-attributes
class TrippliteApiClient:
    """Client for communicating with the Tripp Lite PDU."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize API client."""
        self.host = host
        self.username = username
        self.password = password
        self.session = session

        self.base_url = f"https://{host}"

        self.token: str | None = None
        self.token_expire: float = 0
        self._timeout = aiohttp.ClientTimeout(total=10)

    async def login(self) -> str:
        """Authenticate and obtain an access token."""
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

        try:
            async with self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            ) as resp:
                text = await resp.text()

                if resp.status == 401:
                    raise TrippliteAuthError("Authentication failed")

                if resp.status >= 400:
                    raise TrippliteConnectionError(
                        f"Login failed: HTTP {resp.status}: {text}"
                    )

                try:
                    data = await resp.json(content_type=None)
                except aiohttp.ContentTypeError as err:
                    raise TrippliteResponseError(
                        f"Invalid token response from {url}: {text}"
                    ) from err
                except ValueError as err:
                    raise TrippliteResponseError(
                        f"Invalid token response from {url}: {text}"
                    ) from err

        except aiohttp.ClientError as err:
            raise TrippliteConnectionError(
                f"Error communicating with {self.host}: {err}"
            ) from err
        except TimeoutError as err:
            raise TrippliteConnectionError(
                f"Error communicating with {self.host}: {err}"
            ) from err
        except OSError as err:
            raise TrippliteConnectionError(
                f"Error communicating with {self.host}: {err}"
            ) from err

        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise TrippliteResponseError(f"Token response missing access_token: {data}")

        self.token = access_token
        self.token_expire = time.time() + 800

        return self.token

    async def get_token(self) -> str:
        """Return a valid access token."""
        if self.token and time.time() < self.token_expire:
            return self.token

        return await self.login()

    async def _parse_response(
        self, resp: aiohttp.ClientResponse
    ) -> dict[str, Any] | str | None:
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

    async def _request_once(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json: dict[str, Any] | None = None,
    ) -> aiohttp.ClientResponse:
        """Execute a single HTTP request."""
        return await self.session.request(
            method,
            url,
            headers=headers,
            json=json,
            timeout=self._timeout,
        )

    async def request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | str | None:
        """Execute API request."""
        token = await self.get_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept-Version": API_ACCEPT_VERSION,
        }

        if json is not None:
            headers["Content-Type"] = API_CONTENT_TYPE

        url = f"{self.base_url}{path}"

        try:
            async with await self._request_once(
                method,
                url,
                headers,
                json=json,
            ) as resp:
                if resp.status == 401:
                    self.token = None
                    self.token_expire = 0

                    token = await self.get_token()
                    retry_headers = dict(headers)
                    retry_headers["Authorization"] = f"Bearer {token}"

                    async with await self._request_once(
                        method,
                        url,
                        retry_headers,
                        json=json,
                    ) as retry_resp:
                        if retry_resp.status == 401:
                            raise TrippliteAuthError("Authentication failed")

                        if retry_resp.status >= 400:
                            raise TrippliteConnectionError(
                                f"HTTP {retry_resp.status} calling {path}: "
                                f"{await retry_resp.text()}"
                            )

                        return await self._parse_response(retry_resp)

                if resp.status >= 400:
                    raise TrippliteConnectionError(
                        f"HTTP {resp.status} calling {path}: {await resp.text()}"
                    )

                return await self._parse_response(resp)

        except aiohttp.ClientError as err:
            raise TrippliteConnectionError(
                f"Error communicating with {self.host}: {err}"
            ) from err
        except TimeoutError as err:
            raise TrippliteConnectionError(
                f"Error communicating with {self.host}: {err}"
            ) from err
        except OSError as err:
            raise TrippliteConnectionError(
                f"Error communicating with {self.host}: {err}"
            ) from err

    async def async_test_auth(self) -> None:
        """Validate credentials."""
        await self.request("GET", "/api/loads")

    async def get_loads(self) -> dict[int | str, str]:
        """Fetch outlet and main load states."""
        data = await self.request("GET", "/api/loads")

        if not isinstance(data, dict):
            raise TrippliteResponseError(f"Unexpected /api/loads response: {data}")

        if "data" not in data:
            raise TrippliteResponseError(f"Malformed /api/loads response: {data}")

        result: dict[int | str, str] = {}

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

    async def get_device_info(self) -> dict[str, str | int | bool]:
        """Fetch device metadata."""
        data = await self.request("GET", f"/api/devices/{DEFAULT_DEVICE_ID}")

        if not isinstance(data, dict):
            raise TrippliteResponseError(f"Unexpected /api/devices response: {data}")

        device = data.get("data")
        if not isinstance(device, dict):
            raise TrippliteResponseError(f"Malformed /api/devices response: {data}")

        attributes = device.get("attributes")
        if not isinstance(attributes, dict):
            raise TrippliteResponseError(f"Malformed /api/devices attributes: {data}")

        return attributes

    async def get_variables(self) -> dict[int, dict[str, Any]]:
        """Fetch device variables keyed by variable id."""
        data = await self.request("GET", "/api/variables")

        if not isinstance(data, dict):
            raise TrippliteResponseError(f"Unexpected /api/variables response: {data}")

        items = data.get("data")
        if not isinstance(items, list):
            raise TrippliteResponseError(f"Malformed /api/variables response: {data}")

        result: dict[int, dict[str, Any]] = {}

        for item in items:
            if not isinstance(item, dict):
                continue

            item_id = item.get("id")
            attributes = item.get("attributes")

            if not isinstance(item_id, (str, int)) or not isinstance(attributes, dict):
                continue

            try:
                var_id = int(item_id)
            except TypeError:
                continue
            except ValueError:
                continue

            result[var_id] = attributes

        return result
