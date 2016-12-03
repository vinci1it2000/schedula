#!/usr/b in/env python
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
Utilities for storing passwords in text-files and in memory, bound exclusively to the host hat generated them.

"""

import base64
import binascii
import logging
import string
from typing import Text, Tuple, Union

import functools as fnt


#: The "service-name" for accessing semi-secret keys from :mod:`keyring`.
KEYRING_ID = 'ec.jrc.co2mpas'
SALT_LEN = MAC_LEN = NONCE_LEN = 16
ENC_PREFIX = 'TRAITAES_1'  # version-like prefix for encrypted ciphers

log = logging.getLogger(__name__)


def store_host_btoken(tokenid: Text, token: bytes):
    """see :func:`store_host_token()`"""
    store_host_token(tokenid, binascii.hexlify(token).decode())
    

def store_host_token(tokenid: Text, token: Text):
    """
    Use :mod:`keyring` to store non-sensitive infos (i.e. salt or AES initialization-vectors) on local host.
    
    :param token:
        Since on *Windows* it uses Microsoft's DPPAPI so it must not be very big.
    """
    import keyring

    kr = keyring.get_keyring()
    kr.set_password(KEYRING_ID, tokenid, token)


def retrieve_host_btoken(tokenid: Text) -> bytes:
    """see :func:`retrieve_host_token()`"""
    try:
        token = retrieve_host_token(tokenid)
        if token:
            return binascii.unhexlify(token)
    except Exception as ex:
        log.warning('Failed retrieving host-token for %r, due to: %s', tokenid, ex)
    
    
def retrieve_host_token(tokenid: Text) -> Text:
    """
    Use :mod:`keyring` to store non-sensitive infos (i.e. salt or AES initialization-vectors) on local.
    """
    import keyring

    kr = keyring.get_keyring()
    return kr.get_password(KEYRING_ID, tokenid)


def retrieve_or_create_salt(pswdid: Text) -> bytes:
    from Crypto.Random import get_random_bytes
    
    salt = retrieve_host_btoken(pswdid)
    if not salt:
        salt = get_random_bytes(SALT_LEN)
        store_host_btoken(pswdid, salt)

    return salt


def derive_key(pswdid: Text, pswd: Text):
    """
    Generate encryption keys based on user passwords applying PBKDF2 and host-tokens.
    
    :param pswdid:
            Used to retrieve the salt from the host-token.
    :param pswd:
            the user password to hash
    """
    from Crypto.Protocol.KDF import PBKDF2
    
    salt = retrieve_or_create_salt(pswdid)
    key = PBKDF2(pswd, salt)

    return key


def encrypt(key: bytes, plainbytes: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Low-level AES-EAX encrypt `plainbytes` and return side plainbytes in a tuple.
    
    :param key:
        the encryption key (after pbkdf-ing user password).
    :return:
        a 3-tuple: ``(nonce(NONCE_LEN), mac(16), cipher)``
"""
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes

    nonce = get_random_bytes(NONCE_LEN)
    ## To reason mode, see http://blog.cryptographyengineering.com/2012/05/how-to-choose-authenticated-encryption.html
    cipher = AES.new(key, AES.MODE_EAX, nonce)
    cipherbytes, mac = cipher.encrypt_and_digest(plainbytes)
    assert len(mac) == MAC_LEN

    return (nonce, mac, cipherbytes)


def decrypt(key: bytes, nonce: bytes, mac: bytes, cipherbytes: bytes) -> bytes:
    """
    Low-level decrypt `tuplebytes` encrypted with :func:`encrypt()`.
    
    :param key:
        the decryption key (after pbkdf-ing user password).
    :param tuplebytes:
        must be a 3-section bytes: ``nonce(NONCE_LEN) +  mac(16) + cipher``
"""
    from Crypto.Cipher import AES

    cipher = AES.new(key, AES.MODE_EAX, nonce)
    plainbytes = cipher.decrypt_and_verify(cipherbytes, mac)

    return plainbytes


def _tuple2bytes(nonce: bytes, mac: bytes, cipherbytes: bytes) -> bytes:
    return nonce + mac + cipherbytes


def _bytes2tuple(tuplebytes: bytes) -> Tuple[bytes, bytes, bytes]:
    (nonce, mac, cipherbytes) = (tuplebytes[:NONCE_LEN],
                                 tuplebytes[NONCE_LEN:NONCE_LEN + MAC_LEN],
                                 tuplebytes[NONCE_LEN + MAC_LEN:])
    assert len(nonce) == NONCE_LEN and len(mac) == MAC_LEN, (
        len(nonce), len(mac))

    return nonce, mac, cipherbytes


def text_encrypt(pswdid: Text, pswd: Text, plainbytes: bytes) -> Text:
    """
    Encrypt `plainbytes` in a self-contained textual-form suitable to be stored in a file.

    The textual-format is shown below, and the prefix works as "version":
    
        TRAITAES_1: <base32(nonce(NONCE_LEN) + mac(16) + cipher)>

    The :func:`encrypt()` does the actual crypto.
    
    :param pswdid:
            Used to pbkdf the user-pswd--> encryption-key.
    """
    key = derive_key(pswdid, pswd)
    tpl = encrypt(key, plainbytes)
    tuplebytes = _tuple2bytes(*tpl)
    tuplebytes = base64.urlsafe_b64encode(tuplebytes)

    return "%s: %s" % (ENC_PREFIX, tuplebytes.decode())


def strip_text_encrypted(text_enc: Text) -> Text:
    """Returns the base64 body of the textual format or None. """
    if text_enc.startswith(ENC_PREFIX):
        return text_enc[len(ENC_PREFIX) + 1:].strip()  # +1 for ':' char


def text_decrypt(pswdid: Text, pswd: Text, text_enc: Text) -> bytes:
    """
    High-level decrypt `plainbytes` encrypted with :func:`text_encrypt()`.
    
    :return:
        none if `text_enc` not *TRAITAES_1* textual formatted
    """
    tupleb64 = strip_text_encrypted(text_enc)
    if tupleb64:
        tuplebytes = base64.urlsafe_b64decode(tupleb64)
        (nonce, mac, cipherbytes) = _bytes2tuple(tuplebytes)
        key = derive_key(pswdid, pswd)

        plainbytes = decrypt(key, nonce, mac, cipherbytes)

        return plainbytes


def rot_funcs(nrot: int=None) -> Text:
    """
    Naive scrambling to hide keys held in memory from the casual debugger (for long-running programs).
    
    :param nrot:
        If not an integer, a new one gets selected at random.
    :return: a pair of "rot-n" func used to encrypt/decrypt strings
    """
    ## Adapted from: http://stackoverflow.com/a/3269724/548792
    allchars = ' ' + string.ascii_letters + string.digits + string.punctuation
    clen = len(allchars)
    if nrot is None:
        import random
        nrot = random.randrange(1, clen)
    else:
        nrot %= clen
    rotchars = allchars[nrot:] + allchars[:nrot]

    t1 = str.maketrans(allchars, rotchars)
    t2 = str.maketrans(rotchars, allchars)
    
    def translate(s, table):
        ss = s.translate(table)
        assert len(s) == len(ss), (len(s), len(ss))

        return ss

    return (fnt.partial(translate, table=t1),
            fnt.partial(translate, table=t2))
