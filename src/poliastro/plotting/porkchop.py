"""
This is the script for porkchop plotting
"""

import matplotlib.pyplot as plt
import numpy as np
from astropy import coordinates as coord, units as u

from poliastro.bodies import (
    Earth,
    Jupiter,
    Mars,
    Mercury,
    Moon,
    Neptune,
    Pluto,
    Saturn,
    Sun,
    Uranus,
    Venus,
)
from poliastro.iod import lambert
from poliastro.util import norm


def _get_state(body, time):
    """ Computes the position of a body for a given time. """

    solar_system_bodies = [
        Sun,
        Mercury,
        Venus,
        Earth,
        Moon,
        Mars,
        Jupiter,
        Saturn,
        Uranus,
        Neptune,
        Pluto,
    ]

    # We check if body belongs to poliastro.bodies
    if body in solar_system_bodies:
        rr, vv = coord.get_body_barycentric_posvel(body.name, time)
    else:
        rr, vv = body.propagate(time).rv()
        rr = coord.CartesianRepresentation(rr)
        vv = coord.CartesianRepresentation(vv)

    return rr, vv


def _targetting(departure_body, target_body, t_launch, t_arrival):
    """This function returns the increment in departure and arrival velocities.

    """

    rr_dpt_body, vv_dpt_body = _get_state(departure_body, t_launch)
    rr_arr_body, vv_arr_body = _get_state(target_body, t_arrival)

    # Compute time of flight
    tof = t_arrival - t_launch

    if tof <= 0:
        return None, None, None, None, None

    try:
        (v_dpt, v_arr), = lambert(Sun.k, rr_dpt_body.xyz, rr_arr_body.xyz, tof)

        # Compute all the output variables
        dv_dpt = norm(v_dpt - vv_dpt_body.xyz)
        dv_arr = norm(v_arr - vv_arr_body.xyz)
        c3_launch = dv_dpt ** 2
        c3_arrival = dv_arr ** 2

        return (
            dv_dpt.to(u.km / u.s).value,
            dv_arr.to(u.km / u.s).value,
            c3_launch.to(u.km ** 2 / u.s ** 2).value,
            c3_arrival.to(u.km ** 2 / u.s ** 2).value,
            tof.jd,
        )

    except AssertionError:
        return None, None, None, None, None


# numpy.vectorize is amazing
targetting_vec = np.vectorize(
    _targetting,
    otypes=[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    excluded=["departure_body", "target_body"],
)


def porkchop(
    departure_body,
    target_body,
    launch_span,
    arrival_span,
    ax=None,
    tfl=True,
    vhp=True,
    max_c3=45.0 * u.km ** 2 / u.s ** 2,
    max_vhp=5 * u.km / u.s,
):
    """Plots porkchop between two bodies.

    Parameters
    ----------
    departure_body: poliastro.bodies.Body
        Body from which departure is done
    target_body: poliastro.bodies.Body
        Body for targetting
    launch_span: astropy.time.Time
        Time span for launch
    arrival_span: astropy.time.Time
        Time span for arrival
    ax: matplotlib.axes.Axes:
        For custom figures
    tfl: boolean
        For plotting time flight contour lines
    vhp: boolean
        For plotting arrival velocity contour lines
    max_c3: float
        Sets the maximum C3 value for porkchop
    max_vhp: float
        Sets the maximum arrival velocity for porkchop

    Returns
    -------
    c3_launch: np.ndarray
        Characteristic launch energy
    c3_arrrival: np.ndarray
        Characteristic arrival energy
    tof: np.ndarray
        Time of flight for each transfer

    Example
    -------
    >>> from poliastro.plotting.porkchop import porkchop
    >>> from poliastro.bodies import Earth, Mars
    >>> from poliastro.util import time_range
    >>> launch_span = time_range("2005-04-30", end="2005-10-07")
    >>> arrival_span = time_range("2005-11-16", end="2006-12-21")
    >>> dv_launch, dev_dpt, c3dpt, c3arr, tof = porkchop(Earth, Mars, launch_span, arrival_span)
    """

    dv_launch, dv_arrival, c3_launch, c3_arrival, tof = targetting_vec(
        departure_body,
        target_body,
        launch_span[np.newaxis, :],
        arrival_span[:, np.newaxis],
    )

    # Start drawing porkchop

    if ax is None:
        fig, ax = plt.subplots(figsize=(15, 15))
    else:
        fig = ax.figure

    c3_levels = np.linspace(0, max_c3.to(u.km ** 2 / u.s ** 2).value, 30)

    c = ax.contourf(
        [D.to_datetime() for D in launch_span],
        [A.to_datetime() for A in arrival_span],
        c3_launch,
        c3_levels,
    )

    line = ax.contour(
        [D.to_datetime() for D in launch_span],
        [A.to_datetime() for A in arrival_span],
        c3_launch,
        c3_levels,
        colors="black",
        linestyles="solid",
    )

    cbar = fig.colorbar(c)
    cbar.set_label("km2 / s2")
    ax.clabel(line, inline=1, fmt="%1.1f", colors="k", fontsize=10)

    if tfl:

        time_levels = np.linspace(100, 500, 5)

        tfl_contour = ax.contour(
            [D.to_datetime() for D in launch_span],
            [A.to_datetime() for A in arrival_span],
            tof,
            time_levels,
            colors="red",
            linestyles="dashed",
            linewidths=3.5,
        )

        ax.clabel(tfl_contour, inline=1, fmt="%1.1f", colors="r", fontsize=14)

    if vhp:

        vhp_levels = np.linspace(0, max_vhp.to(u.km / u.s).value, 5)

        vhp_contour = ax.contour(
            [D.to_datetime() for D in launch_span],
            [A.to_datetime() for A in arrival_span],
            dv_arrival,
            vhp_levels,
            colors="navy",
            linewidths=2.0,
        )

        ax.clabel(vhp_contour, inline=1, fmt="%1.1f", colors="navy", fontsize=12)

    ax.grid()
    fig.autofmt_xdate()

    if not hasattr(target_body, "name"):

        ax.set_title(
            "{} - {} for year {}, C3 Launch".format(
                departure_body.name, "Target Body", launch_span[0].datetime.year
            ),
            fontsize=14,
            fontweight="bold",
        )
    else:
        ax.set_title(
            "{} - {} for year {}, C3 Launch".format(
                departure_body.name, target_body.name, launch_span[0].datetime.year
            ),
            fontsize=14,
            fontweight="bold",
        )

    ax.set_xlabel("Launch date", fontsize=10, fontweight="bold")
    ax.set_ylabel("Arrival date", fontsize=10, fontweight="bold")

    return (
        dv_launch * u.km / u.s,
        dv_arrival * u.km / u.s,
        c3_launch * u.km ** 2 / u.s ** 2,
        c3_arrival * u.km ** 2 / u.s ** 2,
        tof * u.d,
    )
