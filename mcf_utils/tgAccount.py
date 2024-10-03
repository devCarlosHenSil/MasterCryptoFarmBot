# Developed by: MasterkinG32
# Date: 2024
# Github: https://github.com/masterking32
# Telegram: https://t.me/MasterCryptoFarmBot

import asyncio
import os
import sys
import random
import string
import time

from pyrogram import Client
from pyrogram.raw.types import (
    InputBotAppShortName,
    InputNotifyPeer,
    InputPeerNotifySettings,
)
from pyrogram.raw import functions
from pyrogram.raw.functions.messages import RequestWebView, RequestAppWebView
from pyrogram.raw.functions.account import UpdateNotifySettings
from urllib.parse import unquote
from mcf_utils.utils import testProxy, parseProxy
from contextlib import asynccontextmanager


@asynccontextmanager
async def connect_pyrogram(log, bot_globals, accountName, proxy=None):
    tgClient = None
    try:
        log.info(
            f"<green>🌍 Connecting to Pyrogram <c>({accountName})</c> session ...</green>"
        )

        if proxy and not testProxy(proxy):
            log.info(
                f"<yellow>❌ Proxy is not working for <c>{accountName}</c> session!</yellow>"
            )
            yield None
            return

        tgClient = Client(
            name=accountName,
            api_id=bot_globals["telegram_api_id"],
            api_hash=bot_globals["telegram_api_hash"],
            workdir=bot_globals["mcf_dir"] + "/telegram_accounts",
            plugins=dict(root="bot/plugins"),
            proxy=parseProxy(proxy) if proxy else None,
        )

        isConnected = await tgClient.connect()

        if isConnected:
            log.info(
                f"<green>🌍 Pyrogram Session <c>{accountName}</c> connected successfully!</green>"
            )
            yield tgClient
        else:
            yield None
    except Exception as e:
        try:
            # If database is locked, retry after 3 seconds That means another instance is using the database
            if "database is locked" in str(e):
                await asyncio.sleep(3)
                async for client in connect_pyrogram(
                    log, bot_globals, accountName, proxy
                ):
                    yield client
                return
            else:
                log.info(
                    f"<yellow>❌ Pyrogram session <c>{accountName}</c> failed to connect!</yellow>"
                )
                log.error(f"<red>❌ {e}</red>")
            yield None
        except Exception as e:
            log.error(f"<red>❌ {e}</red>")
            yield None
    finally:
        try:
            if tgClient is not None and tgClient.is_connected:
                log.info(
                    f"<g>💻 Disconnecting Pyrogram session <c>{accountName}</c> ...</g>"
                )
                await tgClient.disconnect()
        except Exception as e:
            # self.log.error(f"<red>└─ ❌ {e}</red>")
            pass

        log.info(
            f"<green>✔️ Pyrogram session <c>{accountName}</c> has been disconnected successfully!</green>"
        )


class tgAccount:
    def __init__(
        self,
        bot_globals=None,
        log=None,
        accountName=None,
        proxy=None,
        BotID=None,
        ReferralToken=None,
        ShortAppName=None,
        AppURL=None,
    ):
        self.bot_globals = bot_globals
        self.log = log
        self.accountName = accountName
        self.proxy = proxy
        self.BotID = BotID
        self.ShortAppName = ShortAppName
        self.ReferralToken = ReferralToken
        self.AppURL = AppURL

    async def run(self):
        try:
            self.log.info(f"<green>🤖 Running {self.accountName} account ...</green>")
            async with connect_pyrogram(
                self.log, self.bot_globals, self.accountName, self.proxy
            ) as tgClient:
                if tgClient is None:
                    return None
                await self._account_setup(tgClient)
                return await self._get_web_view_data(tgClient)
        except Exception as e:
            self.log.info(
                f"<yellow>❌ Failed to run {self.accountName} account!</yellow>"
            )
            self.log.error(f"<red>❌ {e}</red>")
            return None

    async def getWebViewData(self):
        async with connect_pyrogram(
            self.log, self.bot_globals, self.accountName, self.proxy
        ) as tgClient:
            if tgClient is None:
                self.log.info(
                    f"<yellow>└─ ❌ Account {self.accountName} session is not connected!</yellow>"
                )
                return None
            return await self._get_web_view_data(tgClient)

    async def _get_bot_app_link(self, tgClient):
        try:
            BotID = self.BotID
            chatHistory = await tgClient.get_chat_history_count(BotID)
            if chatHistory < 1:
                await self.send_start_bot(tgClient)
                await asyncio.sleep(5)

            if self.AppURL:
                return self.AppURL

            if self.ShortAppName:
                return None

            async for message in tgClient.get_chat_history(BotID):
                if message is None:
                    continue

                isBot = message.from_user and message.from_user.is_bot
                if not isBot:
                    continue

                if not message.reply_markup:
                    continue

                webAppURL = None
                if message.reply_markup.__class__.__name__ == "InlineKeyboardMarkup":
                    for row in message.reply_markup.inline_keyboard:
                        for button in row:
                            if button.web_app is None or button.web_app.url is None:
                                continue

                            webAppURL = button.web_app.url
                elif message.reply_markup.__class__.__name__ == "ReplyKeyboardMarkup":
                    for row in message.reply_markup.keyboard:
                        for button in row:
                            if button.url is None:
                                continue

                            webAppURL = button.url

                if webAppURL is None:
                    continue

                message_date = int(message.date.timestamp())
                time_now = int(time.time())
                a_week = 60 * 60 * 24 * 7
                if time_now - message_date > a_week:
                    await asyncio.sleep(5)
                    await self.send_start_bot(tgClient)
                    return await self.get_app_web_link(tgClient)

                return webAppURL
        except Exception as e:
            self.log.error(f"<red>└─ ❌ {e}</red>")

        return None

    async def send_start_bot(self, tgClient):
        self.log.info(
            f"<green>└─ 🤖 Sending start bot for {self.accountName} ...</green>"
        )

        peer = await tgClient.resolve_peer(self.BotID)
        await tgClient.invoke(
            functions.messages.StartBot(
                bot=peer,
                peer=peer,
                random_id=random.randint(100000, 999999),
                start_param=self.ReferralToken,
            )
        )

        return True

    async def _get_web_view_data(self, tgClient=None):
        try:
            BotID = self.BotID

            app_url = await self._get_bot_app_link(tgClient)

            if not app_url and not self.ShortAppName:
                self.log.info(
                    f"<yellow>└─ ❌ {self.accountName} session failed to get app url!</yellow>"
                )
                return None
            peer = await tgClient.resolve_peer(BotID)
            bot_app = (
                InputBotAppShortName(bot_id=peer, short_name=self.ShortAppName)
                if self.ShortAppName
                else None
            )

            web_view = await tgClient.invoke(
                RequestAppWebView(
                    peer=peer,
                    app=bot_app,
                    platform="android",
                    write_allowed=True,
                    start_param=self.ReferralToken,
                )
                if bot_app
                else RequestWebView(
                    peer=peer,
                    bot=peer,
                    platform="android",
                    from_bot_menu=False,
                    url=app_url,
                )
            )

            if not web_view and "url" not in web_view:
                self.log.info(
                    f"<yellow>└─ ❌ {self.accountName} session failed to get web view data!</yellow>"
                )
                return None

            return web_view.url
        except Exception as e:
            self.log.info(
                f"<yellow>└─ ❌ {self.accountName} session failed to get web view data!</yellow>"
            )
            self.log.error(f"<red>❌ {e}</red>")
            return None

    async def accountSetup(self):
        async with connect_pyrogram(
            self.log, self.bot_globals, self.accountName, self.proxy
        ) as tgClient:
            if tgClient is None:
                self.log.info(
                    f"<y>└─ ❌ Account {self.accountName} session is not connected!</y>"
                )
                return None
            return await self._account_setup(tgClient)

    async def _account_setup(self, tgClient):
        try:
            await self._join_chat(tgClient, "MasterCryptoFarmBot", True, False)
            UserAccount = await tgClient.get_me()
            if not UserAccount.username:
                self.log.info(
                    f"<green>└─ 🗿 Account username is empty. Setting a username for the account...</green>"
                )
                await self._set_random_username(tgClient)
            self.log.info(
                f"<green>└─ ✅ Account {self.accountName} session is setup successfully!</green>"
            )
        except Exception as e:
            self.log.info(
                f"<y>└─ ❌ Account {self.accountName} session is not setup!</y>"
            )
            self.log.error(f"<red>└─ ❌ {e}</red>")
            return None

    async def _set_random_username(self, tgClient):
        setUsername = False
        maxTries = 5
        while not setUsername and maxTries > 0:
            RandomUsername = "".join(
                random.choices(string.ascii_lowercase, k=random.randint(15, 30))
            )
            self.log.info(
                f"<green>└─ 🗿 Setting username for {self.accountName} session, New username <cyan>{RandomUsername}</cyan></green>"
            )
            setUsername = await tgClient.set_username(RandomUsername)
            maxTries -= 1
            await asyncio.sleep(5)

    async def joinChat(self, url, noLog=False, mute=True):
        try:
            async with connect_pyrogram(
                self.log, self.bot_globals, self.accountName, self.proxy
            ) as tgClient:
                if tgClient is None:
                    return None
                return await self._join_chat(tgClient, url, noLog, mute)
        except Exception as e:
            self.log.info(
                f"<y>└─ ❌ Account {self.accountName} session is not connected!</y>"
            )
            self.log.error(f"<red>❌ {e}</red>")
            return None

    async def _join_chat(self, tgClient, url, noLog=False, mute=True):
        if not noLog:
            self.log.info(f"<green>└─ 📰 Joining <cyan>{url}</cyan> ...</green>")
        try:
            chatObj = await tgClient.join_chat(url)
            if chatObj and chatObj.id:
                if mute:
                    peer = InputNotifyPeer(peer=await tgClient.resolve_peer(chatObj.id))
                    settings = InputPeerNotifySettings(
                        silent=True,
                        mute_until=int(time.time() + 10 * 365 * 24 * 60 * 60),
                    )
                    await tgClient.invoke(
                        UpdateNotifySettings(peer=peer, settings=settings)
                    )
                if not noLog:
                    self.log.info(
                        f"<green>└─ ✅ <cyan>{url}</cyan> has been joined successfully!</green>"
                    )
                return True
        except Exception as e:
            if not noLog:
                self.log.info(f"<y>└─ ❌ </y><cyan>{url}</cyan><y> failed to join!</y>")
                self.log.error(f"<red>❌ {e}</red>")
        return False

    async def setName(self, firstName, lastName=None):
        async with connect_pyrogram(
            self.log, self.bot_globals, self.accountName, self.proxy
        ) as tgClient:
            if tgClient is None:
                self.log.info(
                    f"<y>└─ ❌ Account {self.accountName} session is not connected!</y>"
                )
                return None
            return await self._set_name(tgClient, firstName, lastName)

    async def _set_name(self, tgClient, firstName, lastName=None):
        try:
            tgMe = await tgClient.get_me()
            await tgClient.update_profile(
                first_name=firstName or tgMe.first_name,
                last_name=lastName or tgMe.last_name,
            )
            self.log.info(
                f"<green>└─ ✅ Account {self.accountName} session name is set successfully!</green>"
            )
            return True
        except Exception as e:
            self.log.info(
                f"<yellow>└─ ❌ Failed to set session {self.accountName} name!</yellow>"
            )
            return False

    async def getMe(self):
        async with connect_pyrogram(
            self.log, self.bot_globals, self.accountName, self.proxy
        ) as tgClient:
            if tgClient is None:
                self.log.info(
                    f"<yellow>└─ ❌ Account {self.accountName} session is not connected!</yellow>"
                )
                return None
            return await self._get_me(tgClient)

    async def _get_me(self, tgClient):
        try:
            return await tgClient.get_me()
        except Exception as e:
            self.log.info(
                f"<yellow>└─ ❌ Failed to get session {self.accountName} info!</yellow>"
            )
            return None

    def getTGWebQuery(self, url):
        if not url or "first_name" not in url:
            return None
        if "tgWebAppData=" not in url:
            return url
        return unquote(
            url.split("tgWebAppData=", maxsplit=1)[1].split(
                "&tgWebAppVersion", maxsplit=1
            )[0]
        )
