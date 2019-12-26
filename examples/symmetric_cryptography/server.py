"""
Defines the server model and the Flask app.
"""
import schedula as sh
from model import dsp as _model

dsp = _model.register().get_sub_dsp((
    'decrypt_message', 'encrypt_message', 'key', 'encrypted',
    'decrypted', 'generate_key', sh.START
))

app = dsp.web().site().app()

if __name__ == '__main__':
    app.run()
