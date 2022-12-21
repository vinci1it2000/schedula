import schedula as sh
from converter import converter

form = sh.BlueDispatcher(name='LengthConverterForm')


@sh.add_function(form, outputs=['inputs'])
def define_inputs(value_in, unit_in):
    return {unit_in: value_in}


@sh.add_function(form, outputs=['model'])
def define_model(units_out):
    return sh.SubDispatch(converter, units_out, output_type='list')


form.add_function(
    function=sh.run_model,
    inputs=['model', 'inputs'],
    outputs=['values_out']
)


@sh.add_function(form, outputs=['results'])
def return_results(units_out, values_out):
    return [
        {"unit_out": k, "value_out": v}
        for k, v in zip(units_out, values_out)
    ]


if __name__ == '__main__':
    import os.path as osp

    sites = set()
    form.register().form(
        directory=osp.abspath(osp.dirname(__file__)), sites=sites
    )
    sites
