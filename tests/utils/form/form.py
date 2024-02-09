import schedula as sh

form = sh.BlueDispatcher()
import requests

if __name__ == '__main__':
    import os.path as osp
    import subprocess

    process = subprocess.Popen(["stripe-mock", "-http-port", "8420"])


    import json
    if False:
        import stripe
        stripe.api_key = 'sk_test_12345'
        stripe.api_base = 'http://localhost:8420'
        product_id = stripe.Product.create(name="Schedula Credit").id
        price = stripe.Price.create(
            product=product_id, unit_amount=1000, currency="eur"
        ).id


        class Config:
            STRIPE_SECRET_KEY = stripe.api_key
            STRIPE_PUBLISHABLE_KEY = 'test_12345'
    else:
        price = 'price_1OIUXqJAYIcurulPrv1OcUOU'

        class Config:
            pass
    fpath = osp.join(
        osp.dirname(__file__), 'static/schedula/forms/index-ui.json'
    )
    with open(fpath) as f:
        data = json.load(f)
    data['ui:layout']['children'][0]['props']['items'][0][
        'price'
    ] = price
    with open(fpath, 'w') as f:
        json.dump(data, f)

    sites = set()
    form.register().form(
        directory=osp.abspath(osp.dirname(__file__)), sites=sites,
        basic_app_config=Config
    )
    process.terminate()
    sites
