import os.path as osp
import schedula as sh

dsp = sh.Dispatcher(name='form')

# Add your model here.

app = dsp.form(
    directory=osp.join(osp.dirname(__file__), 'root'), run=False, view=False
).app()

if __name__ == '__main__':
    app.run(port=50000)
