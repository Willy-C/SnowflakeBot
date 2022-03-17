from __future__ import annotations
import re
import json
import aiohttp
import asyncio
import logging
import datetime
import rapidfuzz

from typing import Tuple, List, Optional
from utils.errors import MultiFactorCodeRequired, InvalidCredentials, Invalid2FACode, NotAuthenticated, MissingCredentials

log = logging.getLogger(__name__)


class VALORANTAuth:
    USER_AGENT = 'RiotClient/43.0.1.4195386.4190634 rso-auth (Windows; 10;;Professional, x64)'

    AUTH_URL     = 'https://auth.riotgames.com/api/v1/authorization'
    TOKEN_URL    = 'https://entitlements.auth.riotgames.com/api/token/v1'
    USERINFO_URL = 'https://auth.riotgames.com/userinfo'

    def __init__(self, *, username=None, password=None, puuid=None, riotid=None) -> None:
        self.username: Optional[str] = username
        self.password: Optional[str] = password
        self.region: Optional[str] = 'na'
        self.riotid: Optional[str] = riotid

        self.headers: dict[str, str] = {'User-Agent': self.USER_AGENT}
        self.entitlements_token: Optional[str] = None
        self.access_token: Optional[str] = None
        self.puuid: Optional[str] = puuid
        self.id_token: Optional[str] = None
        self._2fa_code: Optional[str] = None

        self.expires_at: Optional[datetime.datetime] = None
        self.session: Optional[aiohttp.ClientSession] = aiohttp.ClientSession()
        self._lock: asyncio.Lock = asyncio.Lock()
        self._loaded_cookies = False

    @classmethod
    def from_record(cls, data: dict):
        return cls(username=data.get('username'),
                   password=data.get('password'),
                   puuid=data.get('puuid'),
                   riotid=data.get('riotid'))

    async def __aenter__(self) -> VALORANTAuth:
        await self._lock.acquire()
        if self.session is None:
            self.session = aiohttp.ClientSession()
        await self.ensure_authenticated()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._lock.release()

    async def close(self) -> None:
        self.save_cookies()
        await self.session.close()

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return True
        return datetime.datetime.utcnow() >= self.expires_at

    @property
    def cookie_file(self) -> str:
        if self.puuid is None:
            raise MissingCredentials
        return f'data/{self.puuid}.pickle'

    def save_cookies(self):
        self.session.cookie_jar.save(self.cookie_file)

    def load_cookies(self):
        self.session.cookie_jar.load(self.cookie_file)
        self._loaded_cookies = True

    @staticmethod
    def check_valid_region(region: str) -> None:
        VALID_REGIONS = ('na', 'eu', 'ap', 'kr')
        if region not in VALID_REGIONS:
            raise ValueError(f'Invalid Region ({region}). Must be one of: {", ".join(VALID_REGIONS)}!')

    @staticmethod
    def parse_access_token(data) -> Tuple[str, str, int]:
        pattern = r'access_token=((?:[a-zA-Z]|\d|\.|-|_)*).*id_token=((?:[a-zA-Z]|\d|\.|-|_)*).*expires_in=(\d*)'
        try:
            uri = data['response']['parameters']['uri']
        except KeyError:
            raise InvalidCredentials
        data = re.findall(pattern, uri)[0]
        access_token = data[0]
        id_token = data[1]
        expires_in = int(data[2])
        return access_token, id_token, expires_in


    # Auth stuff


    async def ensure_authenticated(self):
        if self.is_expired:
            if self._loaded_cookies:
                try:
                    await self.reauthenticate()
                except InvalidCredentials:
                    await self.authenticate_from_password()
            else:
                await self.authenticate_from_password()

    async def authenticate_from_password(self, username=None, password=None):
        self.username = username or self.username
        self.password = password or self.password

        if self.username is None or self.password is None:
            raise MissingCredentials

        await self.prepare_cookies()

        self.access_token, self.id_token, expires_in = await self.get_access_token()

        self.expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
        self._loaded_cookies = True

        self.entitlements_token = await self.get_entitlement_token()

        self.puuid = await self.get_puuid()

        self.headers = self.final_headers()

        self.save_cookies()
        return self.puuid, self.headers

    async def authenticate_from_cookies(self, puuid=None):
        self.puuid = puuid or self.puuid
        self.load_cookies()

        self.access_token, self.id_token, expires_in = await self.reauthenticate()

        self.expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)

        self.entitlements_token = await self.get_entitlement_token()

        self.headers = self.final_headers()

        self.save_cookies()
        return self.puuid, self.headers

    async def authenticate_from_2fa(self, _2fa_code=None):
        data = await self.send_2fa_code(_2fa_code)
        self.access_token, self.id_token, expires_in = self.parse_access_token(data)

        self.expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
        self._loaded_cookies = True

        self.entitlements_token = await self.get_entitlement_token()

        self.puuid = await self.get_puuid()

        self.headers = self.final_headers()

        self.save_cookies()
        return self.puuid, self.headers


    def final_headers(self):
        if self.access_token is None or self.entitlements_token is None:
            raise MissingCredentials

        headers = {
            'Accept-Encoding': 'gzip, deflate, br',
            'User-Agent': self.USER_AGENT,
            'Authorization': f'Bearer {self.access_token}',
            'X-Riot-Entitlements-JWT':  self.entitlements_token
        }
        return headers

    # Auth requests

    async def prepare_cookies(self) -> None:
        payload = {
            'client_id': 'play-valorant-web-prod',
            'nonce': '1',
            'redirect_uri': 'https://playvalorant.com/opt_in',
            'response_type': 'token id_token',
        }
        await self.session.post(self.AUTH_URL, json=payload, headers=self.headers)

    async def get_access_token(self) -> Tuple[str, str, int]:
        payload = {
            'type': 'auth',
            'username': self.username,
            'password': self.password
        }
        resp = await self.session.put(self.AUTH_URL,
                                      json=payload,
                                      headers=self.headers)
        data = await resp.json()
        if data['type'] == 'multifactor':
            if self._2fa_code is None:
                raise MultiFactorCodeRequired
            else:
                data = await self.send_2fa_code()

        return self.parse_access_token(data)

    async def send_2fa_code(self, code: str = None):
        code = code or self._2fa_code
        payload = {
            'type': 'multifactor',
            'code': code,
            "rememberDevice": True
        }
        resp = await self.session.put(self.AUTH_URL,
                                      json=payload,
                                      headers=self.headers)
        data = await resp.json()
        if data['type'] == 'response':
            try:
                data['response']['parameters']['uri']
            except KeyError:
                log.error(f'Missing access_code: {data=}')
                raise Invalid2FACode
            else:
                return data

    async def get_entitlement_token(self) -> str:
        headers = {
            'Accept-Encoding': 'gzip, deflate, br',
            'Host': "entitlements.auth.riotgames.com",
            'User-Agent': self.USER_AGENT,
            'Authorization': f'Bearer {self.access_token}',
        }

        resp = await self.session.post(self.TOKEN_URL, headers=headers, json={})
        data = await resp.json()
        entitlements_token = data['entitlements_token']
        return entitlements_token

    async def get_puuid(self) -> str:
        headers = {
            'Accept-Encoding': 'gzip, deflate, br',
            'Host': "auth.riotgames.com",
            'User-Agent': self.USER_AGENT,
            'Authorization': f'Bearer {self.access_token}',
        }
        resp = await self.session.post(self.USERINFO_URL, headers=headers, json={})
        data = await resp.json()
        puuid = data['sub']
        return puuid

    async def reauthenticate(self) -> Tuple[str, str, int]:
        payload = {
            'client_id': 'play-valorant-web-prod',
            'nonce': '1',
            'redirect_uri': 'https://playvalorant.com/opt_in',
            'response_type': 'token id_token',
        }
        resp = await self.session.post(self.AUTH_URL, json=payload, headers=self.headers)
        data = await resp.json()
        return self.parse_access_token(data)

    # API Requests

    async def get_username(self) -> str:
        if self.riotid:
            return self.riotid

        payload = [self.puuid]
        resp = await self.session.put('https://pd.NA.a.pvp.net/name-service/v2/players',
                                      headers=self.headers,
                                      json=payload)
        data = await resp.json(content_type=None)
        user = data[0]

        riotid = f'{user["GameName"]}#{user["TagLine"]}'
        self.riotid = riotid
        return riotid

    async def get_store_items(self) -> List[str]:
        resp = await self.session.get(f'https://pd.{self.region}.a.pvp.net/store/v2/storefront/{self.puuid}',
                                      headers=self.headers)
        data = await resp.json()
        item_ids = data['SkinsPanelLayout']['SingleItemOffers']
        return item_ids

    # Other stuff

    async def check_store(self) -> List[dict]:
        item_ids = await self.get_store_items()
        return await get_current_skin_data(item_ids)


async def get_skin_data():
    URL = 'https://valorant-api.com/v1/weapons/skinlevels'
    async with aiohttp.ClientSession() as session:
        resp = await session.get(URL)
        resp.raise_for_status()

        data = await resp.json()
        skin_data = {
            s['uuid']: {'displayName': s['displayName'],
                        'displayIcon': s['displayIcon']}
            for s in data['data']
            if s['displayIcon']}

    with open('data/skin_data.json', 'w') as f:
        json.dump(skin_data, f, indent=4)
    return skin_data


async def get_skin_names():
    URL = 'https://valorant-api.com/v1/weapons/skins'
    async with aiohttp.ClientSession() as session:
        resp = await session.get(URL)
        resp.raise_for_status()

        data = await resp.json()

    names = [skin['displayName'] for skin in data['data']]
    with open('data/skin_names.json', 'w') as f:
        json.dump(names, f, indent=4)
    return names


async def get_current_skin_data(skins: List[str]) -> List[dict]:
    try:
        with open('data/skin_data.json', 'r') as f:
            skin_data = json.load(f)
    except FileNotFoundError:
        skin_data = await get_skin_data()
        updated = True
    else:
        updated = False

    try:
        return [skin_data[skin] for skin in skins]
    except KeyError:
        if updated:
            raise
        else:
            skin_data = await get_skin_data()
            return [skin_data[skin] for skin in skins]


async def update_skin_data():
    await get_skin_data()
    await get_skin_names()


async def get_closest_skin(name: str):
    try:
        with open('data/skin_names.json', 'r') as f:
            skin_names = json.load(f)
    except FileNotFoundError:
        skin_names = await get_skin_names()
    if name in skin_names:
        return skin_names

    return rapidfuzz.process.extractOne(name,
                                        skin_names,
                                        scorer=rapidfuzz.string_metric.levenshtein,
                                        score_cutoff=5)
