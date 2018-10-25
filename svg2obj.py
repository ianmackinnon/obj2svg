#!/usr/bin/env python3

# pylint: disable=logging-too-many-args

import os
import sys
import shutil
import logging
import argparse
from tempfile import NamedTemporaryFile

from common import color_log

from geo import svg2paths



LOG = logging.getLogger("svg2obj")



def svg2obj(out, svg_file):
    """
    Write paths in OBJ format.

    out:  Stream object to write to.

    Use millimeters for output unit.
    """

    paths = svg2paths(svg_file)
    write_obj(out, paths)



def write_obj(out, paths):
    """
    Vertex numbers start from 1.
    """

    vertex_list = []
    face_list = []

    for path in paths:
        face = []
        for vertex in path:
            vertex_list.append(vertex)
            v = len(vertex_list)
            face.append(v)
        face_list.append(face)

    out.write("g\n")
    for vertex in vertex_list:
        out.write("v %f %f 0\n" % (vertex[0], vertex[1]))
    for face in face_list:
        out.write("f %s\n" % " ".join(["%d" % v for v in face]))
    LOG.info("Wrote %d vertices and %d faces.",
             len(vertex_list), len(face_list))



def main():
    log_geo = logging.getLogger("geo")
    for log in LOG, log_geo:
        log.addHandler(logging.StreamHandler())
        color_log(log)

    parser = argparse.ArgumentParser(
        description="Convert paths in an SVG file to polygons in OBJ format.")
    parser.add_argument(
        "--verbose", "-v",
        action="count", default=0,
        help="Print verbose information for debugging.")
    parser.add_argument(
        "--quiet", "-q",
        action="count", default=0,
        help="Suppress warnings.")

    parser.add_argument(
        "svg",
        metavar="SVG",
        help="Path to SVG file.")

    parser.add_argument(
        "obj",
        metavar="OBJ",
        nargs="?",
        help="Path to OBJ file.")

    args = parser.parse_args()

    level = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)[
        max(0, min(3, 1 + args.verbose - args.quiet))]
    for log in LOG, log_geo:
        log.setLevel(level)

    if args.obj:
        out = NamedTemporaryFile("w", encoding="utf=8", delete=False)
        os.fchmod(out.fileno(), os.stat(args.svg).st_mode)
    else:
        out = sys.stdout

    with open(args.svg, "r", encoding="utf-8") as svg:
        svg2obj(out, svg)

    if args.obj:
        out.close()
        shutil.move(out.name, args.obj)




if __name__ == "__main__":
    main()
