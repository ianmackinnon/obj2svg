#!/usr/bin/env python3

import re
import sys
import logging
import argparse

Z_WARN_NON_ZERO = False



LOG = logging.getLogger("obj2svg")



def obj2svg(obj_file, unit=""):
    LOG.info(obj_file.name)

    obj_text = obj_file.read()

    vert_list = []
    face_list = []

    obj_text = re.compile(r"\s*\\\n\s*").sub(" ", obj_text)

    x_min = None
    y_min = None
    x_max = None
    y_max = None

    for line in obj_text.splitlines():
        line = re.sub("#.*$", "", line)
        line = line.strip()
        if not line:
            continue

        g_match = re.match("g", line)
        if g_match:
            continue

        vn_match = re.match("vn ([-0-9e.]+) ([-0-9e.]+) ([-0-9e.]+)", line)
        if vn_match:
            continue

        v_match = re.match("v ([-0-9e.]+) ([-0-9e.]+) ([-0-9e.]+)", line)
        if v_match:
            point = [float(v) for v in v_match.groups()]
            (x, y, z) = point
            x_min = x if x_min is None else min(x_min, x)
            y_min = y if y_min is None else min(y_min, y)
            x_max = x if x_max is None else max(x_max, x)
            y_max = y if y_max is None else max(y_max, y)
            if Z_WARN_NON_ZERO and z != 0:
                LOG.warning("Point is not in z-plane")
                sys.exit(1)
            vert_list.append(point)
            continue

        f_match = re.match("f( [-0-9e./]+)+$", line)
        if f_match:
            face = [int(v.split("/")[0]) for v in line.split()[1:]]
            face_list.append(face)
            continue

        LOG.error(line)
        sys.exit(1)

    width = x_max - x_min
    height = y_max - y_min

    sys.stdout.write('''<svg
  xmlns:svg="http://www.w3.org/2000/svg"
  xmlns="http://www.w3.org/2000/svg"
  width="%f%s"
  height="%f%s"
  viewBox="%f %f %f %f"
>
''' % (width, unit, height, unit, 0, 0, width, height))
    for face in face_list:
        sys.stdout.write('  <path d=\"')
        for i, v in enumerate(face):
            vert = vert_list[v - 1]
            sys.stdout.write(" %s%f %f" % (
                "M" if i == 0 else "L",
                vert[0],
                vert[1],
            ))
        sys.stdout.write(' Z"/>\n')
    sys.stdout.write('</svg>')

    LOG.info("%s faces.", len(face_list))



def main():
    LOG.addHandler(logging.StreamHandler())

    parser = argparse.ArgumentParser(
        description="Convert polygons in an OBJ file to paths in SVG format.")
    parser.add_argument(
        "--verbose", "-v",
        action="count", default=0,
        help="Print verbose information for debugging.")
    parser.add_argument(
        "--quiet", "-q",
        action="count", default=0,
        help="Suppress warnings.")

    parser.add_argument(
        "--unit", "-u",
        action="store", default="",
        help="Units, eg. “mm”, “px”.")

    parser.add_argument(
        "obj",
        metavar="OBJ",
        type=argparse.FileType("r", encoding="utf-8"),
        help="Path to OBJ file.")

    args = parser.parse_args()

    level = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)[
        max(0, min(3, 1 + args.verbose - args.quiet))]
    LOG.setLevel(level)

    obj2svg(args.obj, unit=args.unit)



if __name__ == "__main__":
    main()
