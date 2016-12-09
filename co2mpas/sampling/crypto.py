#!/usr/bin/env python
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
Master-encrypt 3rdp passwords stored in text-files and try limiting decryption on the host that generated them.

The general idea is to use a ``master-password`` to securely store many passwords
( ``pswd-``, ``pswd-2``, etc), and always to require access to both places for
decrypting ``key`` & ``pswd``.

Key Generation::

    _\|/^
     (_oo    $master-pswd      .........     $salt    ---------------
      |   ------------------->( PBKDF2* )<-----------/ host keyring /
     /|\                       ''''|''''             ------^--------
      |                            |$ram-key              /
      LL   .-----. $priv-key   ....V....  $AES(priv-key) /
           | App |----------->( AES-EAX )---------------+
           '--+--'             '''''''''                 \
               \                                          \
                \               $pub-key             ------V--------
                 '--------------------------------->/  filesystem  /
                                                    ---------------

Encrypt 3rdp password::

    .-----.
    | App |                   ---------------
    '--+--'                  / host keyring /
       |$pswd-i              ---------------
     ..V..       $pub-key
    ( RSA )<----------------------.
     ''\''                         \
        \     $RSA(pswd-i)    ------+--------
         '------------------>/  filesystem  /
                             ---------------

Decrypt 3rdp password::

    _\|/^
     (_oo  $master-pswd .........       $salt
      |   ------------>( PBKDF2* )<----------------.
     /|\                ''''|''''                   \    ---------------
      |                     |$ram-key                +--/ host keyring /
      LL                ....V....   $AES(priv-key)  /   ---------------
                       ( AES-EAX )<----------------+
                        ''''|''''                   \    ---------------
                            |$priv-key               +--/  filesystem  /
                          ..V..     $RSA(pswd-i)    /   ---------------
                         ( RSA )<------------------'
                          ''|''
                            |$pswd-i
                            V

- Sensitive tokens are the following:
  ``master-pswd``, ``ram-key``, ``priv-key``, ``pswd``

- ``master-pswd`` is given once by user, and the generated ``ram-key`` stays in RAM,
  to avoid "easy" grabing of ``priv-key`` when debugging/grepping memory.

- the ``priv-key`` and the ``pswd`` are generated when needed, and immediately discarded.

- The point is always to need at least 2 sources (filesystem/host-keyring) for
  decryption ``key`` & ``pswd``.

- ``PBKDF2*`` means that the NIC's hwMAC address gets hashed into the bytes
  fed into *PBKDF2*, so as to require modification to the code if done on other machine.
"""
import base64
import binascii
import hashlib
import logging
import os
from typing import Text, Tuple, Union  # @UnusedImport


#: The "service-name" for accessing semi-secret keys from :mod:`keyring`.
KEYRING_ID = 'ec.jrc.co2mpas'
SALT_LEN = MAC_LEN = NONCE_LEN = 16
ENC_PREFIX = 'TRAES.1'  # version-like prefix for encrypted ciphers
#: Recommended by PY3: https://docs.python.org/3/library/hashlib.html
PBKDF_NITERS = 10000
PBKDF_MAC = 'sha256'

log = logging.getLogger(__name__)


def hash_bytes_with_hw_mac(rbytes: bytes):
    """
    Example::

        >>> hash_bytes_with_hw_mac(b'1') != b'1'     # Input indeed hashed..
        True
        >>> hash_bytes_with_hw_mac(b'')              # unless empty
        b''

        >>> hash_bytes_with_hw_mac(b'1') == hash_bytes_with_hw_mac(b'1')  # repetability
        True
        >>> len(hash_bytes_with_hw_mac(b'123'))      # length maintained
        3
    """
    import uuid

    h = hashlib.new(PBKDF_MAC, b'No sleeves')
    HASH_LEN = h.digest_size  # sha256-len: 32bytes

    blen = len(rbytes)
    nhashes = blen // HASH_LEN + bool(blen % HASH_LEN)

    hw_mac_bytes = uuid.getnode().to_bytes(5, 'big')  # NetworkMAC is 48bit long

    hashes = []
    for i in range(0, nhashes * HASH_LEN, HASH_LEN):
        h.update(h.digest() + rbytes[i:HASH_LEN] + hw_mac_bytes)
        hashes.append(h.digest())
    rbytes = b''.join(hashes)

    return rbytes[:blen]


def store_host_btoken(tokenid: Text, token: bytes):
    """see :func:`store_host_token()`"""
    store_host_token(tokenid, binascii.hexlify(token).decode())


def store_host_token(tokenid: Text, token: Text):
    """
    Use :mod:`keyring` to store non-sensitive infos on local host.

    Non-sensitive crypto-related data are:
    - salts
    - nonses
    - IVs
    - MACs
    - chiphertexts

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


def retrieve_or_create_salt(pswdid: Text, new_salt: bool=False) -> bytes:
    """
    Salts are created (if not exist) and stored in :mod:`keyring`, keyed by `pwsdid`.

    :param new_salt:
        When true, creates a new salt and overrides any old stored in keyring.
    """
    salt = None
    if not new_salt:
        salt = retrieve_host_btoken(pswdid)

    if not salt:
        salt = os.urandom(SALT_LEN)
        store_host_btoken(pswdid, salt)

    return salt


def derive_key(pswdid: Text,
               pswd: Union[bytes, Text],
               new_salt: bool=False):
    """
    Generate encryption keys based on user passwords + hwMAC applying PBKDF2 with salt from host-tokens.

    :param pswdid:
            Used to retrieve the salt from the host-token.
    :param pswd:
            the user password to hash
    """
    if not isinstance(pswd, bytes):
        pswd = pswd.encode(errors='surrogateescape')

    pswd = hash_bytes_with_hw_mac(pswd)

    salt = retrieve_or_create_salt(pswdid, new_salt)
    key = hashlib.pbkdf2_hmac(PBKDF_MAC, pswd, salt, PBKDF_NITERS)

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

    nonce = os.urandom(NONCE_LEN)
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


def tencrypt_any(pswdid: Text, pswd: Text, plainobj) -> Text:
    """
    Encrypt `plainobj` in a self-contained textual-form suitable to be stored in a file.

    The textual-format is shown below, and the prefix works as "version":

        TRAITAES_1: <base32(nonce(NONCE_LEN) + mac(16) + cipher)>

    The :func:`encrypt()` does the actual crypto.

    :param pswdid:
            Used to pbkdf the user-pswd--> encryption-key.
    """
    import dill

    plainbytes = dill.dumps(plainobj)
    key = derive_key(pswdid, pswd)
    tpl = encrypt(key, plainbytes)
    tuplebytes = _tuple2bytes(*tpl)
    tuplebytes = base64.urlsafe_b64encode(tuplebytes)

    return "$%s$%s" % (ENC_PREFIX, tuplebytes.decode())


def strip_text_encrypted(text_enc: Text) -> Text:
    """Returns the base64 body of the textual format or None. """
    if text_enc.startswith(ENC_PREFIX):
        return text_enc[len(ENC_PREFIX) + 1:].strip()  # +1 for ':' char


def tdecrypt_any(pswdid: Text, pswd: Text, text_enc: Text):
    """
    High-level decrypt `plainobj` encrypted with :func:`tencrypt_any()`.

    :return:
        none if `text_enc` not *TRAITAES_1* textual formatted
    """
    tupleb64 = strip_text_encrypted(text_enc)
    if tupleb64:
        import dill

        tuplebytes = base64.urlsafe_b64decode(tupleb64)
        (nonce, mac, cipherbytes) = _bytes2tuple(tuplebytes)
        key = derive_key(pswdid, pswd)

        plainbytes = decrypt(key, nonce, mac, cipherbytes)
        plainobj = dill.loads(plainbytes)

        return plainobj
