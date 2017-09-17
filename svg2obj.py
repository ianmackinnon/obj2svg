#!/usr/bin/env python3

# pylint: disable=logging-too-many-args

import re
import sys
import logging
import argparse
from math import atan2

import numpy as np
from bs4 import BeautifulSoup



def color_log(log):
    color_red = '\033[91m'
    color_green = '\033[92m'
    color_yellow = '\033[93m'
    color_blue = '\033[94m'
    color_end = '\033[0m'

    level_colors = (
        ("error", color_red),
        ("warning", color_yellow),
        ("info", color_green),
        ("debug", color_blue),
    )

    safe = None
    color = None

    def xor(a, b):
        return bool(a) ^ bool(b)

    def _format(value):
        if isinstance(value, float):
            return "%0.3f"
        else:
            return "%s"

    def message_args(args):
        if not args:
            return "", []
        if (
                not isinstance(args[0], str) or
                xor(len(args) > 1, "%" in args[0])
        ):
            return " ".join([_format(v) for v in args]), args
        return args[0], args[1:]

    def _message(args, color):
        message, args = message_args(args)
        return "".join([color, message, color_end])

    def _args(args):
        args = message_args(args)[1]
        return args

    def build_lambda(safe, color):
        return lambda *args, **kwargs: getattr(log, safe)(
            _message(args, color), *_args(args), **kwargs)

    for (level, color) in level_colors:
        safe = "%s_" % level
        setattr(log, safe, getattr(log, level))
        setattr(log, level, build_lambda(safe, color))



LOG = logging.getLogger("svg2obj")
color_log(LOG)



RE_MATRIX = re.compile(r"""
matrix\(
(-?[0-9.]+),
(-?[0-9.]+),
(-?[0-9.]+),
(-?[0-9.]+),
(-?[0-9.]+),
(-?[0-9.]+)
\)
""", re.X)



def clean_whitespace(text):
    return re.sub(r"[\s]+", " ", text).strip()



def text_to_mm(text):
    text = text.strip().lower()

    match = re.compile(r"^([0-9.]+)\s*mm$", re.U).match(text)
    if match:
        return float(match.group(1))

    match = re.compile(r"^([0-9.]+)\s*cm$", re.U).match(text)
    if match:
        return float(match.group(1)) * 10

    match = re.compile(r"^([0-9.]+)\s*in$", re.U).match(text)
    if match:
        return float(match.group(1)) * 25.4

    LOG.error(
        "No conversion to millimeters found for '%s'.",
        text
    )


def bezier_points(cursor, segment, absolute):
    """
    Return absolute points
    """

    vertex_list = [tuple(cursor)]
    while segment:
        vertex = tuple(segment[:2])
        segment = segment[2:]

        if absolute:
            vertex_list.append(tuple(vertex))
        else:
            vertex_list.append((
                cursor[0] + vertex[0],
                cursor[1] + vertex[1]
            ))

    def point(p0, p1, p2, p3, t):
        return (
            p0 * pow((1 - t), 3) +
            p1 * 3 * pow((1 - t), 2) * t +
            p2 * 3 * (1 - t) * pow(t, 2) +
            p3 * pow(t, 3)
        )

    p = vertex_list

    a1 = atan2(p[1][1] - p[0][1], p[1][0] - p[0][0])
    a2 = atan2(p[2][1] - p[1][1], p[2][0] - p[1][0])
    a3 = atan2(p[3][1] - p[2][1], p[3][0] - p[2][0])

    d = abs(a2 - a1) + abs(a3 - a2)

    vertex_list = []
    n = 1 + int(10 * d)
    for i in range(n):
        t = float(i + 1) / n
        x = point(p[0][0], p[1][0], p[2][0], p[3][0], t)
        y = point(p[0][1], p[1][1], p[2][1], p[3][1], t)
        vertex_list.append((x, y))

    return vertex_list



def path_to_poly(path):
    path = clean_whitespace(path)
    path = re.sub("([A-Za-z])([0-9-])", r"\1 \2", path)
    path = re.sub(",", " ", path)

    LOG.debug("  Path: Convert '%s'", path)
    poly = []
    cursor = [0, 0]
    re_value = r" (-?[0-9.]+)"
    re_multi = "(?:" + re_value + ")+"
    while True:
        path = re.sub("^ ", "", path)
        if not path:
            break

        match = re.compile("[Cc]" + re_multi).match(path)
        if match:
            segment_list = [float(v) for v in match.group(0)[2:].split()]
            if not poly:
                poly.append(cursor)
            while segment_list:
                segment = segment_list[:6]
                segment_list = segment_list[6:]

                vertex_list = bezier_points(
                    cursor, segment, path.startswith("C"))

                for vertex in vertex_list:
                    cursor = list(vertex)
                    poly.append(cursor)
                LOG.debug(
                    "  Path: Draw Bézier curve segment to %s %s "
                    "using %d vertices.",
                    cursor[0], cursor[1], len(vertex_list))
            path = path[match.end():]
            continue

        match = re.compile("[Ll]" + re_multi).match(path)
        if match:
            segment_list = [float(v) for v in match.group(0)[2:].split()]
            if not poly:
                poly.append(cursor)
            while segment_list:
                segment = segment_list[:2]
                segment_list = segment_list[2:]

                if path.startswith("L"):
                    cursor = list(segment)
                else:
                    cursor[0] += segment[0]
                    cursor[1] += segment[1]
                poly.append(tuple(cursor))
                LOG.debug("  Path: Draw line segment to %s %s.",
                          cursor[0], cursor[1])
            path = path[match.end():]
            continue

        match = re.compile("[Mm]" + (re_value * 2)).match(path)
        if match:
            value = [float(v) for v in match.groups()]
            if path.startswith("M"):
                cursor[0] = value[0]
                cursor[1] = value[1]
            else:
                cursor[0] += value[0]
                cursor[1] += value[1]
            LOG.debug("  Path: Move to %s %s.", cursor[0], cursor[1])
            path = path[match.end():]
            continue

        match = re.compile("[Zz]").match(path)
        if match:
            LOG.debug("  Path: End\n")
            break

        LOG.error("No handler for path segment: ", path)
        break

    return poly



def transform_poly(poly, xform):
    return poly



def extract_paths(node, xform=None):
    if xform is None:
        xform = np.identity(3)

    paths = []

    if "transform" in node.attrs:
        xform_ = clean_whitespace(node["transform"])
        match = RE_MATRIX.match(xform_)
        if match:
            xform_ = [float(v) for v in match.groups()]
            xform_ = np.matrix((
                xform_[0:3],
                xform_[3:6],
                [0, 0, 1]
            ))
            xform = xform * xform_
        else:
            LOG.warning("No transform procedure defined for '%s'",
                      node["transform"])

    if node.name == "path":
        path = node.attrs["d"]
        poly = path_to_poly(path)
        transform_poly(poly, xform)
        paths.append(poly)

    elif not hasattr(node, "name"):
        LOG.warning("noname", node)

    elif node.name in ["svg", "g"]:
        for child in node:
            paths += extract_paths(child, xform)

    else:
        LOG.debug("Ignore node: %s", node.name)


    return paths



def svg2obj(svg_file):
    """
    Use millimeters for output unit.
    """

    LOG.info("Converting %s", svg_file.name)

    svg_text = svg_file.read()

    soup = BeautifulSoup(svg_text, "lxml")

    svg = soup.find("svg")

    width = svg["width"]
    height = svg["height"]

    width = text_to_mm(width)
    height = text_to_mm(height)

    LOG.info("Page size (mm): %0.3f x %0.3f", width, height)

    paths = extract_paths(svg)

    write_obj(paths)



def write_obj(paths):
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

    stream = sys.stdout

    stream.write("g\n")
    for vertex in vertex_list:
        stream.write("v %f %f 0\n" % (vertex[0], vertex[1]))
    for face in face_list:
        stream.write("f %s\n" % " ".join(["%d" % v for v in face]))
    LOG.info("Wrote %d vertices and %d faces.", len(vertex_list), len(face_list))



def main():
    LOG.addHandler(logging.StreamHandler())

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
        type=argparse.FileType("r", encoding="utf-8"),
        help="Path to SVG file.")

    args = parser.parse_args()

    level = (logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG)[
        max(0, min(3, 1 + args.verbose - args.quiet))]
    LOG.setLevel(level)

    svg2obj(args.svg)



if __name__ == "__main__":
    main()
