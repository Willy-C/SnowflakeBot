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
    # USER_AGENT = 'RiotClient/43.0.1.4195386.4190634 rso-auth (Windows; 10;;Professional, x64)'
    USER_AGENT = 'RiotClient/51.0.0.4429735.4381201 rso-auth (Windows;10;;Professional, x64)'

    AUTH_URL     = 'https://auth.riotgames.com/api/v1/authorization'
    TOKEN_URL    = 'https://entitlements.auth.riotgames.com/api/token/v1'
    USERINFO_URL = 'https://auth.riotgames.com/userinfo'

    def __init__(self, *, username=None, password=None, puuid=None, riotid=None, region='na') -> None:
        self.username: Optional[str] = username
        self.password: Optional[str] = password
        self.region: Optional[str] = region
        self.riotid: Optional[str] = riotid
        self.puuid: Optional[str] = puuid

        self.headers: dict[str, str] = {
            'User-Agent': self.USER_AGENT,
            'Accept-Language ': 'en-US,en;q=0.9'
        }
        self.entitlements_token: Optional[str] = None
        self.access_token: Optional[str] = None
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
        try:
            await self.ensure_authenticated()
        except Exception:
            self._lock.release()
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._lock.release()

    async def close(self) -> None:
        log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | closing')
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

    def parse_access_token(self, data) -> Tuple[str, str, int]:
        pattern = r'access_token=((?:[a-zA-Z]|\d|\.|-|_)*).*id_token=((?:[a-zA-Z]|\d|\.|-|_)*).*expires_in=(\d*)'
        try:
            uri = data['response']['parameters']['uri']
        except KeyError:
            raise InvalidCredentials
        data = re.findall(pattern, uri)[0]
        self.access_token = data[0]
        self.id_token = data[1]
        expires_in = int(data[2])
        self.expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
        return self.access_token, self.id_token, expires_in


    # Auth stuff


    async def ensure_authenticated(self):
        if self.is_expired:
            log.info(f'auth puuid={self.puuid} | riotid={self.riotid} |{self.session._cookie_jar.filter_cookies("https://auth.riotgames.com/api/v1/authorization")=}')
            if self._loaded_cookies:
                try:
                    log.info(f'auth puuid={self.puuid} | riotid={self.riotid}: reauthing with cookie')
                    await self.reauthenticate()
                    self.update_headers()
                    log.info(f'auth puuid={self.puuid} | riotid={self.riotid}: reauthing with cookie success')
                except InvalidCredentials:
                    log.info(f'auth puuid={self.puuid} | riotid={self.riotid}: reauthing with cookie failed, authing with password')
                    await self.authenticate_from_password()
                    log.info(f'auth puuid={self.puuid} | riotid={self.riotid}: authing with password success')
            else:
                try:
                    log.info(f'auth puuid={self.puuid} | riotid={self.riotid}: authing from cookie file')
                    await self.authenticate_from_cookies()
                    log.info(f'auth puuid={self.puuid} | riotid={self.riotid}: authing from cookie file success')
                except (InvalidCredentials, FileNotFoundError):
                    log.info(f'auth puuid={self.puuid} | riotid={self.riotid}: authing from cookie file failed, authing with password')
                    await self.authenticate_from_password()
                    log.info(f'auth puuid={self.puuid} | riotid={self.riotid}: authing with password success')

    async def authenticate_from_password(self, username=None, password=None):
        self.username = username or self.username
        self.password = password or self.password

        if self.username is None or self.password is None:
            raise MissingCredentials

        await self.prepare_cookies()

        await self.get_access_token()

        self._loaded_cookies = True

        await self.get_entitlement_token()

        await self.get_puuid()

        self.update_headers()

        self.save_cookies()
        return self.puuid, self.headers

    async def authenticate_from_cookies(self, puuid=None):
        self.puuid = puuid or self.puuid
        self.load_cookies()

        # log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | after load: {self.session._cookie_jar.filter_cookies("https://auth.riotgames.com/api/v1/authorization")=}')

        await self.reauthenticate()

        await self.get_entitlement_token()

        self.update_headers()

        self.save_cookies()
        return self.puuid, self.headers

    async def authenticate_from_2fa(self, _2fa_code=None):
        data = await self.send_2fa_code(_2fa_code)
        self.parse_access_token(data)

        self._loaded_cookies = True

        await self.get_entitlement_token()

        await self.get_puuid()

        self.update_headers()

        self.save_cookies()
        return self.puuid, self.headers

    def update_headers(self):
        if self.access_token is None or self.entitlements_token is None:
            raise MissingCredentials

        headers = {
            'Accept-Encoding': 'gzip, deflate, br',
            'User-Agent': self.USER_AGENT,
            'Authorization': f'Bearer {self.access_token}',
            'X-Riot-Entitlements-JWT':  self.entitlements_token,
            'Accept-Language ': 'en-US,en;q=0.9'
        }
        self.headers = headers
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
        self.save_cookies()

    async def get_access_token(self) -> Tuple[str, str, int]:
        payload = {
            'type': 'auth',
            'username': self.username,
            'password': self.password,
            'remember': True
        }
        resp = await self.session.put(self.AUTH_URL,
                                      json=payload,
                                      headers=self.headers)
        data = await resp.json()
        if data['type'] == 'multifactor':
            if self._2fa_code is None:
                raise MultiFactorCodeRequired(auth_client=self)
            else:
                data = await self.send_2fa_code()
        log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | get_access_token: {data=}')
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
        log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | send_2fa_code: {data=}')
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
        log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | get_entitlement_token: {data=}')
        entitlements_token = data['entitlements_token']
        self.entitlements_token = entitlements_token
        return entitlements_token

    async def get_puuid(self) -> str:
        if self.puuid is not None:
            return self.puuid
        headers = {
            'Accept-Encoding': 'gzip, deflate, br',
            'Host': "auth.riotgames.com",
            'User-Agent': self.USER_AGENT,
            'Authorization': f'Bearer {self.access_token}',
        }
        resp = await self.session.post(self.USERINFO_URL, headers=headers, json={})
        data = await resp.json()
        log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | get_puuid: {data=}')
        puuid = data['sub']
        self.puuid = puuid
        return puuid

    async def reauthenticate(self) -> Tuple[str, str, int]:
        payload = {
            'client_id': 'play-valorant-web-prod',
            'nonce': '1',
            'redirect_uri': 'https://playvalorant.com/opt_in',
            'response_type': 'token id_token',
        }
        resp = await self.session.post(self.AUTH_URL, json=payload, headers=self.headers)
        try:
            data = await resp.json()
        except Exception:
            raise RuntimeError(await resp.text())
        log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | reauthenticate: {data=}')

        ret = self.parse_access_token(data)
        self.save_cookies()
        return ret

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

    async def get_store_items(self) -> List:
        resp = await self.session.get(f'https://pd.{self.region}.a.pvp.net/store/v2/storefront/{self.puuid}',
                                      headers=self.headers)
        data = await resp.json()
        log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | get_store_item: {data=}')
        item_ids = data['SkinsPanelLayout']['SingleItemOffers']
        return item_ids

    async def get_nightmarket_items(self) -> List[dict]:
        resp = await self.session.get(f'https://pd.{self.region}.a.pvp.net/store/v2/storefront/{self.puuid}',
                                      headers=self.headers)
        data = await resp.json()
        log.info(f'auth puuid={self.puuid} | riotid={self.riotid} | get_nightmarket_items: {data=}')

        return data.get('BonusStore', {}).get('BonusStoreOffers')

    # Other stuff

    async def check_store(self) -> List[dict]:
        item_ids = await self.get_store_items()
        return await get_current_skin_data(item_ids)

    async def check_night_market(self) -> Optional[List[dict]]:
        item_data = await self.get_nightmarket_items()
        if item_data:
            try:
                item_ids = [item["Offer"]["Rewards"][0]["ItemID"] for item in item_data]
            except (KeyError, IndexError, TypeError):
                return
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
                                        weights=(1, 10, 10),
                                        score_cutoff=10)
