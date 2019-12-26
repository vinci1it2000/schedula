"""
Defines the conversion functions of metric system and the conversion model.
"""
import schedula as sh


# --------------------------------- FUNCTIONS ---------------------------------
def km2m(km):
    """
    Converts km to m.

    :param km:
        Length [km].
    :type km: float

    :return:
        Length [m].
    :rtype float
    """
    return km * 1e3


def m2dm(m):
    """
    Converts m to dm.

    :param m:
        Length [m].
    :type m: float

    :return:
        Length [dm].
    :rtype float
    """
    return m * 10


def dm2cm(dm):
    """
    Converts dm to cm.

    :param dm:
        Length [dm].
    :type dm: float

    :return:
        Length [cm].
    :rtype float
    """
    return dm * 10


def cm2mm(cm):
    """
    Converts cm 2 mm.

    :param cm:
        Length [cm].
    :type cm: float

    :return:
        Length [mm].
    :rtype float
    """
    return cm * 10


def mm2km(mm):
    """
    Converts mm to km.

    :param mm:
        Length [mm].
    :type mm: float

    :return:
        Length [km].
    :rtype float
    """
    return mm / 1e6


# ----------------------------------- MODEL -----------------------------------
metric = sh.BlueDispatcher(name='Metric')
metric.add_func(km2m, outputs=['m'])
metric.add_func(m2dm, outputs=['dm'])
metric.add_func(dm2cm, outputs=['cm'])
metric.add_func(cm2mm, outputs=['mm'])
metric.add_func(mm2km, outputs=['km'])

if __name__ == '__main__':
    # To plot the metric model.
    metric.register().plot(
        graph_attr={'ratio': '0.5'}, engine='neato', body={'style': 'filled'},
        index=True
    )
