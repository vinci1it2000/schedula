"""
Defines the conversion functions of imperial system and the conversion model.
"""

import schedula as sh


# --------------------------------- FUNCTIONS ---------------------------------
def leagues2miles(lea):
    """
    Converts leagues to miles.

    :param lea:
        Length [lea].
    :type lea: float

    :return:
        Length [mi].
    :rtype: float
    """
    return lea * 3


def miles2furlongs(mi):
    """
    Converts miles to furlongs.

    :param mi:
        Length [mi].
    :type mi: float

    :return:
        Length [fur].
    :rtype: float
    """
    return mi * 8


def furlongs2chains(fur):
    """
    Converts furlongs to chains.

    :param fur:
        Length [fur].
    :type fur: float

    :return:
        Length [ch].
    :rtype: float
    """
    return fur * 10


def chains2yards(ch):
    """
    Converts chains to yards.

    :param ch:
        Length [ch].
    :type ch: float

    :return:
        Length [yd].
    :rtype: float
    """
    return ch * 22


def yards2feet(yd):
    """
    Converts yards to feet.

    :param yd:
        Length [yd].
    :type yd: float

    :return:
        Length [ft].
    :rtype: float
    """
    return yd * 3


def feet2inch(ft):
    """
    Converts feet to inch.

    :param ft:
        Length [ft].
    :type ft: float

    :return:
        Length [in].
    :rtype: float
    """
    return ft * 12


def inch2thou(inch):
    """
    Converts inches to thou.

    :param inch:
        Length [in].
    :type inch: float

    :return:
        Length [th].
    :rtype: float
    """
    return inch * 1000


def thou2leagues(th):
    """
    Converts leagues to thou.

    :param th:
        Length [th].
    :type th: float

    :return:
        Length [lea].
    :rtype: float
    """
    return th / 19008e4


# ----------------------------------- MODEL -----------------------------------
imperial = sh.BlueDispatcher(name='Imperial')
imperial.add_func(leagues2miles, outputs=['mi'])
imperial.add_func(miles2furlongs, outputs=['fur'])
imperial.add_func(furlongs2chains, outputs=['ch'])
imperial.add_func(chains2yards, outputs=['yd'])
imperial.add_func(yards2feet, outputs=['ft'])
imperial.add_func(feet2inch, outputs=['in'])
imperial.add_func(inch2thou, outputs=['th'], inputs=['in'])
imperial.add_func(thou2leagues, outputs=['lea'])

if __name__ == '__main__':
    # To plot the imperial model.
    imperial.register().plot(
        graph_attr={'ratio': '0.5'}, engine='neato', body={'style': 'filled'},
        index=True
    )
