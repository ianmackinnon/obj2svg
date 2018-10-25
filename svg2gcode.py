#!/usr/bin/env python3

# pylint: disable=logging-too-many-args,too-many-return-statements

import os
import sys
import math
import shutil
import logging
import argparse
from collections import defaultdict
from tempfile import NamedTemporaryFile

from common import color_log

from geo import svg2paths



DEFAULT_Z_SAFETY = 2.5



LOG = logging.getLogger("svg2gcode")



def paths_to_gcode(out, paths, offset):
    """
    Write paths in G-code format.

    out:  Stream object to write to.
    """

    out.write("""
M92   X160   Y80  Z800   E279  ; Set steps-per-unit
M201 X500 Y500  Z50 E10000  ; Set max print acceleration
M203  X300  Y300    Z30    E25  ; Set max feedrate
M204   P3500   R3500   T3500   ; Set default acceleration (Print, Retract, Travel)
M205   X15   Y15               ; Set jerk

M140 S0   ; Set bed temperature, don't wait
M104 S0   ; Set extruder temperature and wait
M107 ; disable fan

G21 ; set units to millimeters
G90 ; use absolute coordinates
M82 ; use absolute distances for extrusion

G28   ; Home all

M420 S1 Z5 V           ; Activate bed levelling with 5mm fade and print table

""")

    z_plot = offset["z"]
    z_move = z_plot + offset["z-safety"]

    out.write("G1 Z%0.3f F4000\n" % z_move)
    out.write("G1 X%0.3f Y%0.3f F4000\n" % (offset["x"], offset["y"]))

    for path in paths:
        out.write("G1 X%0.3f Y%0.3f F4000\n" % (
            offset["x"] + path[0][0], offset["y"] + path[0][1]))
        out.write("G1 Z%0.3f F4000\n" % z_plot)

        for vert in path[1:]:
            out.write("G0 X%0.3f Y%0.3f F4000\n" % (
                offset["x"] + vert[0], offset["y"] + vert[1]))

        out.write("G1 Z%0.3f F4000\n" % z_move)



def dist2d(a, b):
    return math.sqrt(pow(b[0] - a[0], 2) + pow(b[1] - a[1], 2))



def order_paths(path_list):
    index = defaultdict(list)

    for i, path in enumerate(path_list):
        if not path:
            continue

        start = tuple(path[0])
        end = tuple(path[-1])
        index[start].append({
            "i": i,
            "reverse": False
        })
        index[end].append({
            "i": i,
            "reverse": True
        })

    out_list = []
    cursor = (0, 0)

    def add_item(start):
        nonlocal index
        nonlocal cursor
        nonlocal out_list

        item = index[start].pop(0)
        if not index[start]:
            del index[start]
        i = item["i"]
        path = path_list[i]
        if item["reverse"]:
            path = path[::-1]
        end = tuple(path[-1])
        index[end] = [v for v in index[end] if v["i"] != i]
        if not index[end]:
            del index[end]

        out_list.append(path)
        cursor = path[-1]

    while index:
        lo_point = None
        lo_dist = None
        for point in index.keys():
            dist = dist2d(cursor, point)
            if lo_dist is None or dist < lo_dist:
                lo_dist = dist
                lo_point = point
        add_item(lo_point)

    return out_list



def svg2gcode(out, svg_file, offset):
    """
    Use millimeters for output unit.
    """

    paths = svg2paths(svg_file)
    paths = order_paths(paths)
    paths_to_gcode(out, paths, offset)



def main():
    log_geo = logging.getLogger("geo")
    for log in LOG, log_geo:
        log.addHandler(logging.StreamHandler())
        color_log(log)

    parser = argparse.ArgumentParser(
        description="Convert paths in an SVG file to "
        "G-code format for plotting.")
    parser.add_argument(
        "--verbose", "-v",
        action="count", default=0,
        help="Print verbose information for debugging.")
    parser.add_argument(
        "--quiet", "-q",
        action="count", default=0,
        help="Suppress warnings.")

    parser.add_argument(
        "--x-offset", "-x",
        action="store", default=0, type=float,
        help="X offset.")
    parser.add_argument(
        "--y-offset", "-y",
        action="store", default=0, type=float,
        help="X offset.")
    parser.add_argument(
        "--z-offset", "-z",
        action="store", default=0, type=float,
        help="X offset.")
    parser.add_argument(
        "--z-safety", "-Z",
        action="store", default=DEFAULT_Z_SAFETY, type=float,
        help="X offset.")

    parser.add_argument(
        "svg",
        metavar="SVG",
        help="Path to SVG file.")

    parser.add_argument(
        "gcode",
        metavar="GCODE",
        nargs="?",
        help="Path to G-code file.")

    args = parser.parse_args()

    level = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)[
        max(0, min(3, 1 + args.verbose - args.quiet))]
    for log in LOG, log_geo:
        log.setLevel(level)

    offset = {
        "x": args.x_offset,
        "y": args.y_offset,
        "z": args.z_offset,
        "z-safety": args.z_safety,
    }

    if args.gcode:
        out = NamedTemporaryFile("w", encoding="utf=8", delete=False)
        os.fchmod(out.fileno(), os.stat(args.svg).st_mode)
    else:
        out = sys.stdout

    with open(args.svg, "r", encoding="utf-8") as svg:
        svg2gcode(out, svg, offset)

    if args.gcode:
        out.close()
        shutil.move(out.name, args.gcode)




if __name__ == "__main__":
    main()
