"""
Defines the symmetric cryptography model.
"""
import os.path as osp
import schedula as sh
from cryptography.fernet import Fernet

dsp = sh.BlueDispatcher(name='symmetric_cryptography')


@sh.add_function(dsp, outputs=['key'], weight=2)
def generate_key():
    return Fernet.generate_key().decode()


@sh.add_function(dsp, outputs=['encrypted'])
def encrypt_message(key, decrypted):
    return Fernet(key.encode()).encrypt(decrypted.encode()).decode()


@sh.add_function(dsp, outputs=['decrypted'])
def decrypt_message(key, encrypted):
    return Fernet(key.encode()).decrypt(encrypted.encode()).decode()


@sh.add_function(dsp)
def write_key(key_fpath, key):
    with open(key_fpath, 'w') as f:
        f.write(key)


@sh.add_function(dsp, outputs=['key'], input_domain=osp.isfile)
def read_key(key_fpath):
    with open(key_fpath) as f:
        return f.read()


dsp.add_function(
    'read_decrypted', read_key, ['decrypted_fpath'], ['decrypted'],
    input_domain=osp.isfile
)
dsp.add_function(
    'read_encrypted', read_key, ['encrypted_fpath'], ['encrypted'],
    input_domain=osp.isfile
)
dsp.add_function('write_decrypted', write_key, ['decrypted_fpath', 'decrypted'])
dsp.add_function('write_encrypted', write_key, ['encrypted_fpath', 'encrypted'])

if __name__ == '__main__':
    dsp.register().plot(index=True)
