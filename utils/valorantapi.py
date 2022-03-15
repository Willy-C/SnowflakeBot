import re
import json
import aiohttp
import asyncio
import datetime

from typing import Tuple, List


class MultiFactorCodeRequired(Exception):
    pass


class VALORANTAuth:
    USER_AGENT = 'RiotClient/43.0.1.4195386.4190634 rso-auth (Windows; 10;;Professional, x64)'

    AUTH_URL     = 'https://auth.riotgames.com/api/v1/authorization'
    TOKEN_URL    = 'https://entitlements.auth.riotgames.com/api/token/v1'
    USERINFO_URL = 'https://auth.riotgames.com/userinfo'

    def __init__(self, username, password, *, region='na') -> None:
        self.username: str = username
        self.password: str = password

        self.entitlements_token = None
        self.access_token = None
        self.puuid = None
        self.headers = {'User-Agent': self.USER_AGENT}
        self._expire_at = None
        self._2fa_code = None

        self.check_valid_region(region)
        self.region: str = region
        self.session = None
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self._lock.acquire()
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()

    async def close(self):
        await self.session.close()

    @staticmethod
    def check_valid_region(region: str) -> None:
        VALID_REGIONS = ('na', 'eu', 'ap', 'kr')
        if region not in VALID_REGIONS:
            raise ValueError(f'Invalid Region ({region}). Must be one of: {", ".join(VALID_REGIONS)}!')

    # Make this a decorator maybe
    async def ensure_authenticated(self):
        if self._expire_at is not None and datetime.datetime.utcnow() > self._expire_at:
            if self.access_token is not None and self.entitlements_token is not None and self.puuid is not None:
                return

        await self.authenticate()

    async def authenticate(self) -> Tuple[str, dict]:
        await self.prepare_cookies()

        self.access_token, expire_in = await self.get_access_token()

        self._expire_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expire_in)

        self.entitlements_token = await self.get_entitlement_token()

        self.puuid = await self.get_puuid()

        self.headers = {
            'Accept-Encoding': 'gzip, deflate, br',
            'User-Agent': self.USER_AGENT,
            'Authorization': f'Bearer {self.access_token}',
            'X-Riot-Entitlements-JWT':  self.entitlements_token
        }

        return self.puuid, self.headers

    async def prepare_cookies(self) -> None:
        payload = {
            'client_id': 'play-valorant-web-prod',
            'nonce': '1',
            'redirect_uri': 'https://playvalorant.com/opt_in',
            'response_type': 'token id_token',
        }
        await self.session.post(self.AUTH_URL, json=payload, headers=self.headers)

    async def _2fa_access_code(self):
        payload = {
            'type': 'multifactor',
            'code': self._2fa_code,
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
                print(f'Missing access_code: {data=}')
                raise MultiFactorCodeRequired
            else:
                return data

    async def get_access_token(self) -> Tuple[str, int]:
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
                data = await self._2fa_access_code()

        pattern = r'access_token=((?:[a-zA-Z]|\d|\.|-|_)*).*id_token=((?:[a-zA-Z]|\d|\.|-|_)*).*expires_in=(\d*)'
        data = re.findall(pattern, data['response']['parameters']['uri'])[0]
        access_token = data[0]
        expires_in = int(data[2])
        return access_token, expires_in

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

    async def get_store_items(self) -> List[str]:
        resp = await self.session.get(f'https://pd.{self.region}.a.pvp.net/store/v2/storefront/{self.puuid}',
                                      headers=self.headers)
        data = await resp.json()
        item_ids = data['SkinsPanelLayout']['SingleItemOffers']
        return item_ids

    async def get_skin_data(self):
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

    async def get_current_skin_names(self, skins: List[str]) -> List[dict]:
        try:
            with open('data/skin_data.json', 'r') as f:
                skin_data = json.load(f)
        except FileNotFoundError:
            skin_data = await self.get_skin_data()

        return [skin_data[skin] for skin in skins]

    async def check_store(self) -> List[dict]:
        await self.ensure_authenticated()
        item_ids = await self.get_store_items()
        return await self.get_current_skin_names(item_ids)

    async def get_skin_names(self):
        URL = 'https://valorant-api.com/v1/weapons/skins'
        async with aiohttp.ClientSession() as session:
            resp = await session.get(URL)
            resp.raise_for_status()

            data = await resp.json()

        names = [skin['displayName'] for skin in data['data']]
        with open('data/skin_names.json', 'w') as f:
            json.dump(names, f, indent=4)

    async def get_username(self):
        await self.ensure_authenticated()
        payload = [self.puuid]

        resp = await self.session.put('https://pd.NA.a.pvp.net/name-service/v2/players',
                                      headers=self.headers,
                                      json=payload)
        data = await resp.json(content_type=None)
        user = data[0]
        riotid = f'{user["GameName"]}#{user["TagLine"]}'

        return riotid


