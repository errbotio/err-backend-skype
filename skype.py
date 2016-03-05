import logging
import sys
import time

from errbot.backends.base import Identifier, Message, ONLINE, RoomDoesNotExistError
from errbot.errBot import ErrBot
from errbot.rendering import text

# Can't use __name__ because of Yapsy
log = logging.getLogger('errbot.backends.skype')

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

try:
    import Skype4Py
except ImportError:
    log.exception("Could not start the Skype backend")
    log.fatal(
        "You need to install the skype4py package in order "
        "to use the Skype backend. "
        "You should be able to install this package using: "
        "pip install skype4py"
    )
    sys.exit(1)


class SkypeUser(Identifier):
    """
    This represents a user on Skype.
    """

    def __init__(self, user, bot):
        """
        :param user:
            A `Skype4Py.user.User` object to build the identifier from.
        :param bot:
            The backend class itself.
        """
        assert isinstance(user, Skype4Py.user.User)
        self._user = user
        self._bot = bot

    def __unicode__(self):
        return self._user.Handle

    __str__ = __unicode__

    @property
    def user(self):
        return self._user

    @property
    def fullname(self):
        return self._user.FullName

    @property
    def nick(self):
        return self._user.Handle

    handle = nick
    aclattr = nick
    person = nick
    client = None

    @property
    def displayname(self):
        return self._user.DisplayName


class SkypeChatroomOccupant(SkypeUser):
    """
    This represents a user inside a groupchat on Skype.
    """
    def __init__(self, user, room, bot):
        """
        :param chat:
            A `Skype4Py.chat.Chat` object to build the identifier from.
        :param room:
            The :class:`~SkypeChatroom` this user is in.
        :param bot:
            The backend class itself.
        """
        super(SkypeChatroomOccupant, self).__init__(user, bot=self)
        self._room = room

    @property
    def room(self):
        return self._room


class SkypeChatroom(object):
    """
    This represents a groupchat on Skype.

    .. note::
        Creating new groupchats is unsupported.
    """
    def __init__(self, chat, bot):
        """
        :param chat:
            A `Skype4Py.chat.Chat` object to build the identifier from.
        :param bot:
            The backend class itself.
        """
        assert isinstance(chat, Skype4Py.chat.Chat)
        self._chat = chat
        self._bot = bot

    @property
    def chat(self):
        return self._chat

    def __unicode__(self):
        return self._chat.Name

    __str__ = __unicode__
    person = None

    def join(self, username=None, password=None):
        """
        Join the room. Username and password are ignored but present for
        compatibility to the generic API.
        """
        self._chat.Join()

    def leave(self, reason=None):
        """
        Leave the room.

        :param reason:
            Parameter ignored but present for compatibility to the generic API.
        """
        self._chat.Leave()

    def create(self):
        """
        Dummy method. Creating rooms isn't supported on this backend.
        """

    def destroy(self):
        """
        Destroy the room.
        """
        self._chat.Disband()

    @property
    def exists(self):
        """
        Boolean indicating whether this room already exists or not.

        :getter:
            Returns `True` if the room exists, `False` otherwise.
        """
        # Always returns True because an instance of this class
        # can only be created for existing chats.
        return True

    @property
    def joined(self):
        """
        Boolean indicating whether this room has already been joined.

        :getter:
            Returns `True` if the room has been joined, `False` otherwise.
        """
        return self._chat.Status != "UNSUBSCRIBED"

    @property
    def topic(self):
        """
        The room topic.

        :getter:
            Returns the topic (a string) if one is set
        """
        return self._chat.Topic

    @topic.setter
    def topic(self, topic):
        """
        Set the room's topic.

        :param topic:
            The topic to set.
        """
        self._chat.Topic = topic

    @property
    def occupants(self):
        """
        The room's occupants.

        :getter:
            Returns a list of occupant identities.
        :raises:
            :class:`~MUCNotJoinedError` if the room has not yet been joined.
        """
        return [SkypeChatroomOccupant(user=member, room=self, bot=self._bot)
                for member in self._chat.Members]

    def invite(self, *args):
        """
        Invite one or more people into the room.

        :param args:
            One or more identifiers to invite into the room.
        """
        users = [str(self._bot.build_identifier(user)) for user in args]
        self._chat.AddMembers(users)


class SkypeBackend(ErrBot):
    def __init__(self, config):
        super(SkypeBackend, self).__init__(config)
        self.bot_config.SKYPE_ACCEPT_CONTACT_REQUESTS = getattr(config, 'SKYPE_ACCEPT_CONTACT_REQUESTS', True)
        self.skype = Skype4Py.Skype()
        self.skype.OnMessageStatus = self._message_event_handler
        self.skype.OnUserAuthorizationRequestReceived = self._contact_request_event_handler
        self.md_converter = text()

    def serve_forever(self):
        log.info("Attaching to Skype")
        self.skype.Attach()
        log.info("Successfully attached to Skype")
        self.connect_callback()
        self.bot_identifier = SkypeUser(self.skype.CurrentUser, bot=self)

        for user in self.skype.UsersWaitingAuthorization:
            self._process_contact_request(user)

        try:
            while True:
                time.sleep(1000)
        except KeyboardInterrupt:
            self.disconnect_callback()

    def _message_event_handler(self, skype_msg, status):
        """
        Event handler for chat messages.
        """
        if skype_msg.Status == 'RECEIVED':
            log.debug("Processing message with status %s and type %s", skype_msg.Status, skype_msg.Type)
            msg = self._make_message(skype_msg)
            self.callback_message(msg)
        else:
            log.debug("Ignoring message with status %s and type %s", skype_msg.Status, skype_msg.Type)

        try:
            skype_msg.MarkAsSeen()
        except Skype4Py.SkypeError:
            # MarkAsSeen() doesn't work on all types of messages.
            # It's pretty harmless when it fails.
            pass

    def _contact_request_event_handler(self, user):
        """
        Event handler for buddylist authorization requests.
        """
        self._process_contact_request(user)

    def _process_contact_request(self, user):
        """
        Process a contact request from a given user.
        """
        log.info(
            "Received buddylist authorization request from user %s: %s",
            user.Handle,
            user.ReceivedAuthRequest,
        )
        if self.bot_config.SKYPE_ACCEPT_CONTACT_REQUESTS :
            log.info("Accepting buddylist request from %s", user.Handle)
            user.SetBuddyStatusPendingAuthorization()
        else:
            log.info("Ignoring buddylist request from %s", user.Handle)

    def _make_message(self, skype_msg):
        """
        Build an errbot Message from a Skype4Py message.
        """
        assert isinstance(skype_msg, Skype4Py.chat.ChatMessage)

        # msg.Chat.Type always hangs and appears unusable so just consider a chat
        # a groupchat if it has more than 2 members in it.
        is_groupchat = len(skype_msg.Chat.Members) > 2

        if is_groupchat:
            skypechat = SkypeChatroom(skype_msg.Chat, bot=self)
            message = Message(
                body=skype_msg.Body,
                type_="groupchat",
                frm=SkypeChatroomOccupant(skype_msg.Sender, skypechat, bot=self),
                to=skypechat,
            )
        else:
            message = Message(
                body=skype_msg.Body,
                type_="chat",
                frm=SkypeUser(skype_msg.Sender, bot=self),
                to=self.bot_identifier,
            )
        return message

    def build_reply(self, mess, text=None, private=False):
        assert isinstance(mess, Message)
        message = mess
        message.to = mess.frm
        message.frm = self.bot_identifier
        message.body = text
        if private:
            message.type = "chat"
        return message

    def send_message(self, mess):
        super(SkypeBackend, self).send_message(mess)
        body = self.md_converter.convert(mess.body)
        if mess.type == "chat":
            self.skype.SendMessage(mess.to.handle, body)
        else:
            if hasattr(mess.to, 'room'):
                mess.to.room.chat.SendMessage(body)
            else:
                mess.to.chat.SendMessage(body)

    def change_presence(self, status=ONLINE, message=''):
        super(SkypeBackend, self).change_presence(status=status, message=message)

    def prefix_groupchat_reply(self, message, identifier):
        super(SkypeBackend, self).prefix_groupchat_reply(message=message, identifier=identifier)

    @lru_cache(maxsize=None)
    def build_identifier(self, text_representation):
        log.debug("Building an identifier from '%s'", text_representation)

        matches = [f for f in self.skype.Friends if f.Handle == text_representation]
        if len(matches) == 1:
            log.debug("Found a user on the buddylist matching %s", text_representation)
            return SkypeUser(matches[0], bot=self)

        try:
            return self.query_room(text_representation)
        except RoomDoesNotExistError:
            pass

        matches = [u for u in self.skype.SearchForUsers(text_representation)
                   if u.Handle == text_representation]
        if len(matches) == 1:
            log.debug("Found a user in the Skype directory matching %s", text_representation)
            return SkypeUser(matches[0], bot=self)

        raise ValueError(
            "Unable to build an identifier from %s. Maybe the user doesn't exist "
            "or there's no chat with that identifier"
        )

    def query_room(self, room):
        """
        Query a room for information.

        :param room:
            The room to query for.
        :returns:
            An instance of :class:`~SkypeChatroom`.
        """
        log.debug("Looking for a chat matching %s", room)
        chats = [c for c in self.skype.Chats if c.Name == room]
        if len(chats) == 1:
            log.debug("Found a chat matching %s", room)
            return SkypeChatroom(chats[0], bot=self)
        raise RoomDoesNotExistError("Couldn't find a room matching %s", room)

    def rooms(self):
        """
        Return a list of rooms the bot is currently in.

        :returns:
            A list of :class:`~errbot.backends.base.MUCRoom` instances.
        """
        return [SkypeChatroom(chat, bot=self) for chat in self.skype.Chats]

    def __hash__(self):
        return id(self)

    @property
    def mode(self):
        return 'skype'
